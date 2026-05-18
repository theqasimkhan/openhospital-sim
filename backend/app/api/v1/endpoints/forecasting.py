"""
Forecasting API endpoints.

Routes
──────
POST /forecasting/run         – fit all forecasters and store a ForecastBundle
GET  /forecasting/latest      – retrieve the latest ForecastBundle
GET  /forecasting/surge-risk  – real-time surge risk assessment

The forecasting pipeline runs in O(n) where n = number of time-series data points.
Typical wall times are < 10 ms; no background workers are needed.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Body, HTTPException, status

from app.agents.registry import get_registry, get_registry_lock
from app.core.logging import get_logger
from app.forecasting.demand_forecaster import DemandForecaster
from app.forecasting.icu_forecaster import ICUForecaster
from app.forecasting.schemas import ForecastRunRequest
from app.forecasting.staffing_forecaster import StaffingForecaster, WardUtilizationForecaster
from app.forecasting.surge_detector import SurgeDetector
from app.simulation.engine import get_engine, get_engine_lock

router = APIRouter(tags=["forecasting"])
logger = get_logger(__name__)

# ── Module-level stores ───────────────────────────────────────────────────────
_latest_bundle:      dict[str, Any] | None = None
_latest_surge_risk:  dict[str, Any] | None = None
_store_lock: asyncio.Lock = asyncio.Lock()

# ── Singleton forecaster instances (stateless after each forecast call) ───────
_demand_fc    = DemandForecaster()
_icu_fc       = ICUForecaster()
_ward_fc      = WardUtilizationForecaster()
_staffing_fc  = StaffingForecaster()
_surge_det    = SurgeDetector()


# ── POST /forecasting/run ─────────────────────────────────────────────────────

@router.post(
    "/run",
    summary="Run all forecasters on current time-series data",
    description=(
        "Fits the statistical models (Holt's double exponential smoothing) on the "
        "time-series collected by the ForecastingAgent and projects forward "
        "`horizon_steps` simulation steps.\n\n"
        "Returns forecasts for:\n"
        "- `demand`           – arrivals per step\n"
        "- `icu_utilization`  – ICU bed occupancy fraction\n"
        "- `ward_utilization` – regular ward occupancy fraction\n"
        "- `staffing`         – recommended doctors and nurses per step\n"
        "- `surge_risk`       – surge risk assessment\n\n"
        "Requires at least 2 simulation steps of data. "
        "Returns degraded (flat) forecasts with low confidence if fewer data points exist."
    ),
    status_code=status.HTTP_200_OK,
)
async def run_forecasting(
    body: ForecastRunRequest = Body(default_factory=ForecastRunRequest),
) -> dict[str, Any]:
    global _latest_bundle, _latest_surge_risk

    registry    = get_registry()
    reg_lock    = get_registry_lock()
    engine      = get_engine()
    engine_lock = get_engine_lock()

    # Fetch time series + current state atomically
    async with reg_lock, engine_lock:
        time_series = registry.get_forecast_time_series()
        snapshot    = engine.get_state_snapshot()

    n = len(time_series)
    sim_time = snapshot.simulation_time

    # ── Run each forecaster ───────────────────────────────────────────────────
    demand_fc  = _demand_fc.forecast(time_series, body.horizon_steps, body.step_duration_min)
    icu_fc     = _icu_fc.forecast(time_series, body.horizon_steps, body.step_duration_min)
    ward_fc    = _ward_fc.forecast(time_series, body.horizon_steps, body.step_duration_min)
    staffing   = _staffing_fc.recommend(demand_fc)
    surge      = _surge_det.assess(time_series, snapshot)

    # ── Build staffing forecast dict ──────────────────────────────────────────
    staffing_dict = {
        "metric":           "staffing_recommendations",
        "model":            "demand_derived",
        "horizon_steps":    body.horizon_steps,
        "step_duration_min": body.step_duration_min,
        "confidence":       demand_fc.confidence,
        "trend":            demand_fc.trend,
        "peak":             _staffing_fc.peak_staffing(staffing),
        "recommendations":  [r.to_dict() for r in staffing],
    }

    # ── ICU saturation risk enrichment ────────────────────────────────────────
    steps_to_sat = _icu_fc.steps_to_saturation(icu_fc)
    sat_prob     = _icu_fc.saturation_probability(icu_fc)
    icu_dict = icu_fc.to_dict()
    icu_dict["steps_to_saturation"]     = steps_to_sat
    icu_dict["saturation_probability"]  = round(sat_prob, 4)

    # ── Overall confidence ────────────────────────────────────────────────────
    overall_confidence = (
        demand_fc.confidence * 0.4
        + icu_fc.confidence * 0.3
        + ward_fc.confidence * 0.3
    )

    bundle_dict: dict[str, Any] = {
        "run_id":                str(uuid.uuid4()),
        "sim_time_at_forecast":  sim_time,
        "data_points_available": n,
        "horizon_steps":         body.horizon_steps,
        "step_duration_min":     body.step_duration_min,
        "overall_confidence":    round(overall_confidence, 3),
        "forecasts": {
            "demand":           demand_fc.to_dict(),
            "icu_utilization":  icu_dict,
            "ward_utilization": ward_fc.to_dict(),
            "staffing":         staffing_dict,
        },
        "surge_risk": surge.to_dict(),
    }

    surge_dict = surge.to_dict()

    async with _store_lock:
        _latest_bundle     = bundle_dict
        _latest_surge_risk = surge_dict

    logger.info(
        "forecasting_run",
        data_points=n,
        horizon_steps=body.horizon_steps,
        demand_trend=demand_fc.trend,
        icu_trend=icu_fc.trend,
        surge_level=surge.risk_level,
        overall_confidence=round(overall_confidence, 3),
    )

    return {
        "status":  "ok",
        "message": f"Forecasting complete. {n} data points used.",
        "bundle":  bundle_dict,
    }


# ── GET /forecasting/latest ───────────────────────────────────────────────────

@router.get(
    "/latest",
    summary="Latest forecast bundle",
    description=(
        "Returns the full ForecastBundle from the most recent POST /forecasting/run. "
        "Returns 404 if no forecast has been run this session."
    ),
    status_code=status.HTTP_200_OK,
)
async def get_latest_forecast() -> dict[str, Any]:
    async with _store_lock:
        bundle = _latest_bundle

    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No forecast available. "
                "Run POST /forecasting/run to generate one. "
                "Requires at least one completed simulation step."
            ),
        )

    return {"status": "ok", "bundle": bundle}


# ── GET /forecasting/surge-risk ────────────────────────────────────────────────

@router.get(
    "/surge-risk",
    summary="Current surge risk assessment",
    description=(
        "Returns the surge risk assessment from the most recent forecast run. "
        "Includes risk level (low/medium/high/critical), composite risk score, "
        "contributing signals, and recommended actions.\n\n"
        "Call POST /forecasting/run first to populate this endpoint."
    ),
    status_code=status.HTTP_200_OK,
)
async def get_surge_risk() -> dict[str, Any]:
    global _latest_surge_risk

    async with _store_lock:
        surge = _latest_surge_risk

    if surge is None:
        # Fallback: compute a live surge assessment from the current state
        registry    = get_registry()
        reg_lock    = get_registry_lock()
        engine      = get_engine()
        engine_lock = get_engine_lock()

        async with reg_lock, engine_lock:
            time_series = registry.get_forecast_time_series()
            snapshot    = engine.get_state_snapshot()

        surge = _surge_det.assess(time_series, snapshot).to_dict()

        async with _store_lock:
            _latest_surge_risk = surge

    return {"status": "ok", "surge_risk": surge}
