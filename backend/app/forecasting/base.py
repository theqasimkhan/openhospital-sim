"""
Forecasting engine base types and shared statistical utilities.

Statistical baseline: Holt's two-parameter exponential smoothing (level + trend).
This is a proven, lightweight method that outperforms simple moving averages on
trended data and can be upgraded to Holt-Winters (seasonality) or replaced with
Prophet / ARIMA / XGBoost by subclassing BaseForecaster.

Time-series format (from ForecastingAgent.get_time_series())
─────────────────────────────────────────────────────────────
Each data point is a dict with at minimum:
    step              : int   – simulation step number
    simulation_time   : float – simulated clock (minutes)
    arrivals          : int   – patients that arrived this step
    icu_utilization   : float – fraction 0–1
    ward_utilization  : float – fraction 0–1
    emergency_queue   : int
    discharged_total  : int
    deceased_total    : int

Upgrading to Prophet / ARIMA / XGBoost
────────────────────────────────────────
1. Subclass BaseForecaster.
2. Override _fit_model(values) and _predict(horizon) with your library calls.
3. Keep the return type ForecastResult – no API changes needed.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np

TimeSeries = list[dict[str, Any]]   # raw output from ForecastingAgent


# ── Output types ───────────────────────────────────────────────────────────────

@dataclass
class ForecastPoint:
    """Single forecasted value at one future step."""
    step_ahead:       int     # 1-based index into the future
    sim_time_ahead:   float   # estimated simulation time of this future step
    value:            float
    lower_ci:         float   # 80 % prediction interval lower bound
    upper_ci:         float   # 80 % prediction interval upper bound

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_ahead":     self.step_ahead,
            "sim_time_ahead": round(self.sim_time_ahead, 1),
            "value":          round(self.value, 4),
            "lower_ci":       round(self.lower_ci, 4),
            "upper_ci":       round(self.upper_ci, 4),
        }


@dataclass
class ForecastResult:
    """All forecasted points for one metric."""
    metric:            str
    model:             str
    data_points_used:  int
    horizon_steps:     int
    step_duration_min: float
    confidence:        float       # 0.0–1.0, increases with more data
    trend:             str         # "increasing" | "decreasing" | "stable" | "unknown"
    last_value:        float
    mean_forecast:     float
    points:            list[ForecastPoint]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric":            self.metric,
            "model":             self.model,
            "data_points_used":  self.data_points_used,
            "horizon_steps":     self.horizon_steps,
            "step_duration_min": self.step_duration_min,
            "confidence":        round(self.confidence, 3),
            "trend":             self.trend,
            "last_value":        round(self.last_value, 4),
            "mean_forecast":     round(self.mean_forecast, 4),
            "points":            [p.to_dict() for p in self.points],
        }


@dataclass
class ForecastBundle:
    """All forecasts from a single forecasting run."""
    run_id:                str
    sim_time_at_forecast:  float
    data_points_available: int
    horizon_steps:         int
    step_duration_min:     float
    overall_confidence:    float
    forecasts:             dict[str, ForecastResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id":                self.run_id,
            "sim_time_at_forecast":  self.sim_time_at_forecast,
            "data_points_available": self.data_points_available,
            "horizon_steps":         self.horizon_steps,
            "step_duration_min":     self.step_duration_min,
            "overall_confidence":    round(self.overall_confidence, 3),
            "forecasts":             {k: v.to_dict() for k, v in self.forecasts.items()},
        }


# ── Abstract base forecaster ───────────────────────────────────────────────────

class BaseForecaster(ABC):
    model_name: str = "base"

    def __init__(self) -> None:
        self._fitted = False
        self._values: list[float] = []
        self._level: float = 0.0
        self._trend: float = 0.0
        self._residual_std: float = 1.0

    def forecast(
        self,
        time_series: TimeSeries,
        horizon_steps: int,
        step_duration_min: float = 60.0,
    ) -> ForecastResult:
        """
        Fit the model on `time_series` and predict `horizon_steps` ahead.
        Falls back gracefully when < 2 data points are available.
        """
        values = self._extract(time_series)

        if len(values) < 2:
            return self._empty_result(horizon_steps, step_duration_min, values)

        self._fit(values)
        points = self._predict(
            horizon=horizon_steps,
            step_duration_min=step_duration_min,
            last_sim_time=time_series[-1].get("simulation_time", 0.0) if time_series else 0.0,
        )
        confidence = self._confidence(len(values))
        trend = self._classify_trend(values)
        mean_fc = sum(p.value for p in points) / max(1, len(points))

        return ForecastResult(
            metric=self.metric_name,
            model=self.model_name,
            data_points_used=len(values),
            horizon_steps=horizon_steps,
            step_duration_min=step_duration_min,
            confidence=confidence,
            trend=trend,
            last_value=values[-1],
            mean_forecast=mean_fc,
            points=points,
        )

    # ── Subclass interface ─────────────────────────────────────────────────────

    @property
    @abstractmethod
    def metric_name(self) -> str:
        """Name of the metric being forecast (used in ForecastResult.metric)."""
        ...

    @abstractmethod
    def _extract(self, time_series: TimeSeries) -> list[float]:
        """Pull the relevant numeric column from the raw time series."""
        ...

    # ── Holt exponential smoothing (shared baseline) ──────────────────────────

    def _fit(self, values: list[float], alpha: float = 0.30, beta: float = 0.15) -> None:
        """
        Holt's linear (double) exponential smoothing.
            level_t = α·x_t + (1−α)·(level_{t-1} + trend_{t-1})
            trend_t = β·(level_t − level_{t-1}) + (1−β)·trend_{t-1}
        """
        level = values[0]
        b = values[1] - values[0]
        residuals: list[float] = []

        for x in values[1:]:
            level_prev = level
            level = alpha * x + (1 - alpha) * (level + b)
            b = beta * (level - level_prev) + (1 - beta) * b
            residuals.append(x - (level_prev + b))

        self._level = level
        self._trend  = b
        self._values = list(values)
        self._fitted = True
        # 80 % prediction interval multiplier ≈ 1.28σ
        self._residual_std = float(np.std(residuals)) if residuals else 1.0

    def _predict(
        self,
        horizon: int,
        step_duration_min: float,
        last_sim_time: float,
    ) -> list[ForecastPoint]:
        """
        Project forward using Holt's level + trend extrapolation.
        Prediction intervals widen with √h (standard time-series practice).
        """
        points: list[ForecastPoint] = []
        for h in range(1, horizon + 1):
            value   = self._level + h * self._trend
            value   = max(0.0, value)  # non-negativity constraint
            ci_half = 1.28 * self._residual_std * math.sqrt(h)
            lower   = max(0.0, value - ci_half)
            upper   = value + ci_half
            points.append(
                ForecastPoint(
                    step_ahead=h,
                    sim_time_ahead=last_sim_time + h * step_duration_min,
                    value=value,
                    lower_ci=lower,
                    upper_ci=upper,
                )
            )
        return points

    # ── Shared utilities ───────────────────────────────────────────────────────

    @staticmethod
    def _confidence(n_points: int) -> float:
        """More data → higher confidence, capped at 0.92."""
        return min(0.92, 0.35 + n_points * 0.057)

    @staticmethod
    def _classify_trend(values: list[float]) -> str:
        if len(values) < 3:
            return "unknown"
        # Compare last third of series vs first third
        n = len(values)
        first = sum(values[: n // 3]) / max(1, n // 3)
        last  = sum(values[-(n // 3) :]) / max(1, n // 3)
        delta = (last - first) / max(1e-9, abs(first))
        if delta > 0.10:
            return "increasing"
        if delta < -0.10:
            return "decreasing"
        return "stable"

    def _empty_result(
        self,
        horizon_steps: int,
        step_duration_min: float,
        values: list[float],
    ) -> ForecastResult:
        last = values[-1] if values else 0.0
        points = [
            ForecastPoint(
                step_ahead=h,
                sim_time_ahead=h * step_duration_min,
                value=last,
                lower_ci=max(0.0, last * 0.5),
                upper_ci=last * 1.5,
            )
            for h in range(1, horizon_steps + 1)
        ]
        return ForecastResult(
            metric=self.metric_name,
            model=f"{self.model_name}_fallback",
            data_points_used=len(values),
            horizon_steps=horizon_steps,
            step_duration_min=step_duration_min,
            confidence=0.15,
            trend="unknown",
            last_value=last,
            mean_forecast=last,
            points=points,
        )
