"""
Agent API endpoints.

Routes
──────
GET  /agents                       – list all agents with status + summary
GET  /agents/registry              – registry-level metadata and stats
GET  /agents/decisions/recent      – global decision log (filterable)
GET  /agents/forecast/timeseries   – ForecastingAgent time-series data
GET  /agents/{agent_id}            – single agent detail + internal state
GET  /agents/{agent_id}/logs       – decision log for one agent
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.agents.registry import get_registry, get_registry_lock
from app.core.logging import get_logger
from app.simulation.engine import get_engine

router = APIRouter(tags=["agents"])
logger = get_logger(__name__)


# ── Response wrapper ───────────────────────────────────────────────────────────

class AgentResponse(BaseModel):
    status: str
    simulation_time: float
    data: dict[str, Any]


# ── GET /agents ────────────────────────────────────────────────────────────────

@router.get(
    "",
    summary="List all simulation agents",
    description=(
        "Returns the current state, status, and reasoning summary for every "
        "registered hospital operations agent."
    ),
    status_code=status.HTTP_200_OK,
)
async def list_agents() -> AgentResponse:
    registry = get_registry()
    lock     = get_registry_lock()
    engine   = get_engine()

    async with lock:
        agents = registry.list_agents()
        info   = registry.get_registry_info()

    return AgentResponse(
        status="ok",
        simulation_time=engine.simulation_time,
        data={
            "registry": info,
            "agents":   agents,
        },
    )


# ── GET /agents/registry ───────────────────────────────────────────────────────

@router.get(
    "/registry",
    summary="Agent registry metadata",
    description="Returns high-level stats: agent count, total events processed, decisions made.",
    status_code=status.HTTP_200_OK,
)
async def get_registry_info() -> AgentResponse:
    registry = get_registry()
    lock     = get_registry_lock()
    engine   = get_engine()

    async with lock:
        info = registry.get_registry_info()

    return AgentResponse(
        status="ok",
        simulation_time=engine.simulation_time,
        data=info,
    )


# ── GET /agents/decisions/recent ──────────────────────────────────────────────

@router.get(
    "/decisions/recent",
    summary="Recent agent decisions (global log)",
    description=(
        "Query the global decision log across all agents. "
        "Supports filtering by agent_id, agent_type, priority level, "
        "and minimum simulation time. Results are most-recent-last."
    ),
    status_code=status.HTTP_200_OK,
)
async def get_recent_decisions(
    limit: int = Query(
        default=50,
        ge=1,
        le=1000,
        description="Maximum number of decisions to return",
    ),
    agent_id: str | None = Query(
        default=None,
        description="Filter to a specific agent (e.g. doctor-agent-001)",
    ),
    agent_type: str | None = Query(
        default=None,
        description=(
            "Filter by agent type: patient | doctor | nurse | admin | "
            "icu_manager | emergency_coordinator | forecasting"
        ),
    ),
    priority: str | None = Query(
        default=None,
        description="Filter by priority: info | low | medium | high | critical",
    ),
    since_sim_time: float | None = Query(
        default=None,
        ge=0.0,
        description="Only return decisions made at or after this simulation time",
    ),
) -> AgentResponse:
    registry = get_registry()
    lock     = get_registry_lock()
    engine   = get_engine()

    async with lock:
        decisions = registry.get_recent_decisions(
            limit=limit,
            agent_id=agent_id,
            agent_type=agent_type,
            priority=priority,
            since_sim_time=since_sim_time,
        )

    return AgentResponse(
        status="ok",
        simulation_time=engine.simulation_time,
        data={
            "count":   len(decisions),
            "decisions": decisions,
            "filters": {
                "limit":          limit,
                "agent_id":       agent_id,
                "agent_type":     agent_type,
                "priority":       priority,
                "since_sim_time": since_sim_time,
            },
        },
    )


# ── GET /agents/forecast/timeseries ───────────────────────────────────────────

@router.get(
    "/forecast/timeseries",
    summary="ForecastingAgent time-series data",
    description=(
        "Returns all per-step metrics collected by the ForecastingAgent: "
        "arrivals, ICU utilisation, ward utilisation, queue length, and outcomes."
    ),
    status_code=status.HTTP_200_OK,
)
async def get_forecast_timeseries() -> AgentResponse:
    registry = get_registry()
    lock     = get_registry_lock()
    engine   = get_engine()

    async with lock:
        series = registry.get_forecast_time_series()

    return AgentResponse(
        status="ok",
        simulation_time=engine.simulation_time,
        data={
            "data_points": len(series),
            "timeseries":  series,
        },
    )


# ── GET /agents/{agent_id} ────────────────────────────────────────────────────

@router.get(
    "/{agent_id}",
    summary="Single agent detail",
    description=(
        "Returns the full state of a specific agent including internal counters, "
        "current status, and the latest reasoning summary."
    ),
    status_code=status.HTTP_200_OK,
)
async def get_agent(agent_id: str) -> AgentResponse:
    registry = get_registry()
    lock     = get_registry_lock()
    engine   = get_engine()

    async with lock:
        agent_state = registry.get_agent_state(agent_id)

    if agent_state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found. "
                   "Call GET /agents to list all registered agent IDs.",
        )

    return AgentResponse(
        status="ok",
        simulation_time=engine.simulation_time,
        data=agent_state,
    )


# ── GET /agents/{agent_id}/logs ───────────────────────────────────────────────

@router.get(
    "/{agent_id}/logs",
    summary="Decision log for a specific agent",
    description=(
        "Returns the most recent structured decision logs emitted by the "
        "specified agent, ordered chronologically (most recent last). "
        "Each entry includes the decision text, reasoning, priority, "
        "confidence score, and triggering event metadata."
    ),
    status_code=status.HTTP_200_OK,
)
async def get_agent_logs(
    agent_id: str,
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of decision log entries to return",
    ),
) -> AgentResponse:
    registry = get_registry()
    lock     = get_registry_lock()
    engine   = get_engine()

    async with lock:
        logs = registry.get_agent_logs(agent_id, limit=limit)

    if logs is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found.",
        )

    return AgentResponse(
        status="ok",
        simulation_time=engine.simulation_time,
        data={
            "agent_id": agent_id,
            "count":    len(logs),
            "logs":     logs,
        },
    )
