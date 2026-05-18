"""
Simulation API endpoints.

All routes are synchronous with the SimPy engine but exposed via async
FastAPI handlers. An asyncio.Lock serialises concurrent requests to
prevent race conditions on the shared engine state.

Routes
──────
POST  /simulation/start   – initialise and start the simulation
POST  /simulation/step    – advance the clock by N simulated minutes
POST  /simulation/reset   – tear down and return to idle
GET   /simulation/state   – current state snapshot
GET   /simulation/events  – filtered event log query
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from app.agents.registry import get_registry, get_registry_lock
from app.core.logging import get_logger
from app.observability.metrics import record_step_metrics, update_state_metrics
from app.replay.store import get_replay_store
from app.simulation.config import SimulationConfig
from app.simulation.engine import EngineStatus, get_engine, get_engine_lock

router = APIRouter(tags=["simulation"])
logger = get_logger(__name__)


# ── Request / response schemas ─────────────────────────────────────────────────

class SimConfigOverride(BaseModel):
    """Optional overrides for simulation parameters on /start."""

    seed: int | None = Field(None, ge=0, description="Random seed for determinism")
    icu_beds: int | None = Field(None, ge=1, le=500)
    regular_beds: int | None = Field(None, ge=1, le=2000)
    num_doctors: int | None = Field(None, ge=1, le=500)
    num_nurses: int | None = Field(None, ge=1, le=2000)
    num_equipment_units: int | None = Field(None, ge=1, le=1000)
    mean_inter_arrival_minutes: float | None = Field(None, gt=0.0)
    spike_interval_mean: float | None = Field(None, gt=0.0)
    shortage_interval_mean: float | None = Field(None, gt=0.0)
    default_step_minutes: float | None = Field(None, gt=0.0)
    max_simulation_time: float | None = Field(None, gt=0.0)


class StartRequest(BaseModel):
    config: SimConfigOverride = Field(default_factory=SimConfigOverride)


class StepRequest(BaseModel):
    step_minutes: float = Field(
        default=60.0,
        gt=0.0,
        le=10_080.0,
        description="Simulated minutes to advance per step (default 60 = 1 hour)",
    )


class SimulationResponse(BaseModel):
    """Generic wrapper for simulation endpoint responses."""
    status: str
    simulation_time: float
    engine_status: str
    data: dict[str, Any]


# ── Helper: build SimulationConfig from optional overrides ─────────────────────

def _build_config(override: SimConfigOverride) -> SimulationConfig:
    cfg = SimulationConfig()
    for field_name, value in override.model_dump(exclude_none=True).items():
        setattr(cfg, field_name, value)
    cfg.validate()
    return cfg


# ── POST /simulation/start ─────────────────────────────────────────────────────

@router.post(
    "/start",
    summary="Start the simulation",
    description=(
        "Initialise and start the hospital simulation engine. "
        "Optionally supply configuration overrides. "
        "Returns the initial hospital state snapshot."
    ),
    status_code=status.HTTP_200_OK,
)
async def start_simulation(
    body: StartRequest = Body(default_factory=StartRequest),
) -> SimulationResponse:
    engine   = get_engine()
    engine_lock = get_engine_lock()
    registry = get_registry()
    reg_lock = get_registry_lock()

    replay_store = get_replay_store()

    async with engine_lock, reg_lock:
        try:
            cfg = _build_config(body.config)
            registry.reset()
            # Finish any previously recording run
            replay_store.finish_run(completed=False)
            snapshot = engine.start(cfg)
            # Dispatch the SIMULATION_STARTED event to all agents
            initial_events = engine.get_raw_events(since_index=0)
            registry.process_events(initial_events, snapshot)
            # Begin a new replay run
            run_id = replay_store.begin_run(
                config=engine.get_config(),
                initial_state=snapshot.to_dict(),
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    update_state_metrics(snapshot.to_dict())

    logger.info(
        "simulation_started",
        seed=cfg.seed,
        icu_beds=cfg.icu_beds,
        regular_beds=cfg.regular_beds,
        run_id=run_id,
    )

    return SimulationResponse(
        status="started",
        simulation_time=engine.simulation_time,
        engine_status=engine.status.value,
        data={
            "state":   snapshot.to_dict(),
            "config":  engine.get_config(),
            "run_id":  run_id,
        },
    )


# ── POST /simulation/step ──────────────────────────────────────────────────────

@router.post(
    "/step",
    summary="Advance the simulation clock",
    description=(
        "Run the SimPy event loop for `step_minutes` of simulated time. "
        "Returns all events produced during the step plus the updated state."
    ),
    status_code=status.HTTP_200_OK,
)
async def step_simulation(
    body: StepRequest = Body(default_factory=StepRequest),
) -> SimulationResponse:
    engine      = get_engine()
    engine_lock = get_engine_lock()
    registry    = get_registry()
    reg_lock    = get_registry_lock()

    replay_store = get_replay_store()

    async with engine_lock, reg_lock:
        try:
            events_before = engine.event_count
            result        = engine.step(step_minutes=body.step_minutes)
            # Dispatch new raw events to agents
            new_raw_events = engine.get_raw_events(since_index=events_before)
            snapshot       = engine.get_state_snapshot()
            agent_decisions = registry.process_events(new_raw_events, snapshot)
        except RuntimeError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    decisions_dicts = [d.to_dict() for d in agent_decisions]

    # Record step into replay store
    replay_store.record_step(
        step_number=result.step_number,
        simulation_time_before=result.simulation_time_before,
        simulation_time_after=result.simulation_time_after,
        step_minutes=result.step_minutes,
        events=result.new_events,
        state_snapshot=snapshot.to_dict(),
        agent_decisions=decisions_dicts,
    )

    # If simulation reached COMPLETED, close the recording
    if result.status == EngineStatus.COMPLETED:
        replay_store.finish_run(completed=True)

    # Update Prometheus metrics
    record_step_metrics(result.new_events, decisions_dicts, snapshot.to_dict())

    logger.info(
        "simulation_stepped",
        step=result.step_number,
        sim_time_before=result.simulation_time_before,
        sim_time_after=result.simulation_time_after,
        new_events=len(result.new_events),
        agent_decisions=len(agent_decisions),
    )

    step_data = result.to_dict()
    step_data["agent_decisions_count"] = len(agent_decisions)
    step_data["agent_decisions"]       = decisions_dicts

    return SimulationResponse(
        status="stepped",
        simulation_time=result.simulation_time_after,
        engine_status=result.status.value,
        data=step_data,
    )


# ── POST /simulation/reset ────────────────────────────────────────────────────

@router.post(
    "/reset",
    summary="Reset the simulation to idle",
    description=(
        "Tear down the running simulation and return the engine to IDLE. "
        "All patient, event, and state data is cleared. "
        "Call /start to begin a new run."
    ),
    status_code=status.HTTP_200_OK,
)
async def reset_simulation() -> SimulationResponse:
    engine      = get_engine()
    engine_lock = get_engine_lock()
    registry    = get_registry()
    reg_lock    = get_registry_lock()

    replay_store = get_replay_store()

    async with engine_lock, reg_lock:
        replay_store.finish_run(completed=False)
        snapshot = engine.reset()
        registry.reset()

    logger.info("simulation_reset")

    return SimulationResponse(
        status="reset",
        simulation_time=0.0,
        engine_status=engine.status.value,
        data={"state": snapshot.to_dict()},
    )


# ── GET /simulation/state ─────────────────────────────────────────────────────

@router.get(
    "/state",
    summary="Get current simulation state",
    description=(
        "Returns a point-in-time snapshot of all hospital metrics: "
        "ICU/ward occupancy, staff availability, equipment utilisation, "
        "patient counts, and throughput."
    ),
    status_code=status.HTTP_200_OK,
)
async def get_simulation_state() -> SimulationResponse:
    engine = get_engine()
    lock   = get_engine_lock()

    async with lock:
        snapshot  = engine.get_state_snapshot()
        resources = engine.get_resources_snapshot()

    return SimulationResponse(
        status="ok",
        simulation_time=engine.simulation_time,
        engine_status=engine.status.value,
        data={
            "state":     snapshot.to_dict(),
            "resources": resources,
        },
    )


# ── GET /simulation/events ────────────────────────────────────────────────────

@router.get(
    "/events",
    summary="Query simulation event log",
    description=(
        "Returns the replay-ready event log. Supports filtering by simulation "
        "time, step number, and event type. Use `limit` to page large logs."
    ),
    status_code=status.HTTP_200_OK,
)
async def get_simulation_events(
    since_time: float | None = Query(
        default=None,
        ge=0.0,
        description="Only return events at or after this simulation time",
    ),
    since_step: int | None = Query(
        default=None,
        ge=0,
        description="Only return events from this step number onward",
    ),
    event_type: str | None = Query(
        default=None,
        description=(
            "Filter by event type. Valid values: "
            "patient_arrived, triage_complete, doctor_assigned, treatment_started, "
            "icu_transfer, discharge, patient_death, emergency_spike, "
            "staff_shortage, staff_restored, simulation_started, "
            "simulation_stepped, simulation_reset"
        ),
    ),
    limit: int | None = Query(
        default=200,
        ge=1,
        le=5000,
        description="Maximum number of events to return (most recent if filtered)",
    ),
) -> SimulationResponse:
    engine = get_engine()
    lock   = get_engine_lock()

    async with lock:
        events = engine.get_events(
            since_time=since_time,
            since_step=since_step,
            event_type=event_type,
            limit=limit,
        )

    return SimulationResponse(
        status="ok",
        simulation_time=engine.simulation_time,
        engine_status=engine.status.value,
        data={
            "count":  len(events),
            "events": events,
            "filters": {
                "since_time": since_time,
                "since_step": since_step,
                "event_type": event_type,
                "limit":      limit,
            },
        },
    )
