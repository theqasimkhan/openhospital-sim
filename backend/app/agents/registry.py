"""
AgentRegistry – manages all simulation agents and dispatches events.

Design
──────
• Singleton instance per process (mirrors engine pattern).
• Agents are pre-registered with fixed IDs; registry is immutable at runtime.
• process_events() is the hot path called after every simulation step.
• Global decision log accumulates all decisions from all agents.
• reset() forwards to all agents and clears the global log.
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.agents.admin_agent import AdminAgent
from app.agents.base import BaseAgent, DecisionLog
from app.agents.doctor_agent import DoctorAgent
from app.agents.emergency_coordinator_agent import EmergencyCoordinatorAgent
from app.agents.forecasting_agent import ForecastingAgent
from app.agents.icu_manager_agent import ICUManagerAgent
from app.agents.nurse_agent import NurseAgent
from app.agents.patient_agent import PatientAgent
from app.simulation.events import SimEvent
from app.simulation.state import StateSnapshot


class AgentRegistry:
    """
    Central registry for all hospital simulation agents.

    All public methods are synchronous (SimPy / engine interaction is sync).
    The FastAPI layer serialises concurrent access via the asyncio.Lock
    returned by get_registry_lock().
    """

    def __init__(self) -> None:
        # Ordered so that downstream agents (e.g. Admin) see upstream state
        self._agents: dict[str, BaseAgent] = {}
        self._global_log: list[DecisionLog] = []
        self._total_events_processed: int = 0
        self._total_decisions: int = 0
        self._register_default_agents()

    # ── Agent registration ─────────────────────────────────────────────────────

    def _register_default_agents(self) -> None:
        for agent in [
            PatientAgent(),
            DoctorAgent(),
            NurseAgent(),
            ICUManagerAgent(),
            EmergencyCoordinatorAgent(),
            ForecastingAgent(),
            AdminAgent(),          # Admin last; it reacts to aggregate pressure
        ]:
            self._agents[agent.agent_id] = agent

    # ── Event dispatch ─────────────────────────────────────────────────────────

    def process_events(
        self,
        events: list[SimEvent],
        snapshot: StateSnapshot,
    ) -> list[DecisionLog]:
        """
        Dispatch all events to all registered agents.

        Called after each simulation step. Returns newly produced decisions.
        Agents are visited in insertion order (deterministic).
        """
        step_decisions: list[DecisionLog] = []

        for event in events:
            self._total_events_processed += 1
            for agent in self._agents.values():
                decisions = agent.process_event(event, snapshot)
                step_decisions.extend(decisions)
                self._global_log.extend(decisions)

        self._total_decisions += len(step_decisions)
        return step_decisions

    # ── Query API ──────────────────────────────────────────────────────────────

    def list_agents(self) -> list[dict[str, Any]]:
        """Return the public state of all agents, ordered by type."""
        return [a.get_state() for a in self._agents.values()]

    def get_agent(self, agent_id: str) -> BaseAgent | None:
        return self._agents.get(agent_id)

    def get_agent_state(self, agent_id: str) -> dict[str, Any] | None:
        agent = self._agents.get(agent_id)
        return agent.get_state() if agent else None

    def get_agent_logs(
        self,
        agent_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]] | None:
        agent = self._agents.get(agent_id)
        return agent.get_logs(limit=limit) if agent else None

    def get_recent_decisions(
        self,
        limit: int = 50,
        agent_id: str | None = None,
        agent_type: str | None = None,
        priority: str | None = None,
        since_sim_time: float | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return recent decisions across all agents with optional filters.
        Results are always chronologically ordered (most recent last).
        """
        log = self._global_log

        if agent_id is not None:
            log = [d for d in log if d.agent_id == agent_id]
        if agent_type is not None:
            log = [d for d in log if d.agent_type == agent_type]
        if priority is not None:
            log = [d for d in log if d.priority.value == priority]
        if since_sim_time is not None:
            log = [d for d in log if d.simulation_time >= since_sim_time]

        return [d.to_dict() for d in log[-limit:]]

    # ── Forecasting time-series (special case) ─────────────────────────────────

    def get_forecast_time_series(self) -> list[dict[str, Any]]:
        agent = self._agents.get("forecasting-agent-001")
        if isinstance(agent, ForecastingAgent):
            return agent.get_time_series()
        return []

    # ── Registry metadata ──────────────────────────────────────────────────────

    def get_registry_info(self) -> dict[str, Any]:
        return {
            "agent_count":            len(self._agents),
            "total_events_processed": self._total_events_processed,
            "total_decisions":        self._total_decisions,
            "global_log_size":        len(self._global_log),
            "agents": [
                {
                    "agent_id":   a.agent_id,
                    "name":       a.name,
                    "agent_type": a.agent_type.value,
                    "status":     a.status.value,
                    "decisions":  a.decision_count,
                }
                for a in self._agents.values()
            ],
        }

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Reset all agents and clear the global decision log."""
        for agent in self._agents.values():
            agent.reset()
        self._global_log.clear()
        self._total_events_processed = 0
        self._total_decisions = 0


# ── Global singleton + asyncio lock ───────────────────────────────────────────

_registry: AgentRegistry = AgentRegistry()
_registry_lock: asyncio.Lock = asyncio.Lock()


def get_registry() -> AgentRegistry:
    """Return the process-global agent registry singleton."""
    return _registry


def get_registry_lock() -> asyncio.Lock:
    """Return the asyncio.Lock that serialises API access to the registry."""
    return _registry_lock
