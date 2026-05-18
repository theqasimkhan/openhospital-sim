"""
BaseAgent – abstract foundation for all hospital operations agents.

Design principles
─────────────────
• Agents are stateful observers: they receive simulation events and
  update internal bookkeeping, then emit DecisionLog entries.
• Decisions are purely operational (scheduling, routing, resource
  allocation). No medical diagnosis or clinical advice.
• Every decision carries a structured reasoning string so the system
  is fully explainable and auditable.
• Agents are synchronous (all SimPy / engine interaction is sync).
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.simulation.events import SimEvent, SimEventType
from app.simulation.state import StateSnapshot


# ── Enumerations ───────────────────────────────────────────────────────────────

class AgentType(str, Enum):
    PATIENT               = "patient"
    DOCTOR                = "doctor"
    NURSE                 = "nurse"
    ADMIN                 = "admin"
    ICU_MANAGER           = "icu_manager"
    EMERGENCY_COORDINATOR = "emergency_coordinator"
    FORECASTING           = "forecasting"


class AgentStatus(str, Enum):
    IDLE       = "idle"
    ACTIVE     = "active"
    OVERLOADED = "overloaded"
    STANDBY    = "standby"
    ALERT      = "alert"


class DecisionPriority(str, Enum):
    INFO     = "info"
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


# ── Decision log entry ─────────────────────────────────────────────────────────

@dataclass
class DecisionLog:
    """
    Structured, serialisable record of one agent decision.

    `reasoning` is a plain-English explanation of why the decision was made.
    `confidence` (0.0–1.0) reflects how certain the agent is.
    """
    id:                  str
    agent_id:            str
    agent_type:          str
    agent_name:          str
    simulation_time:     float
    wall_time:           float
    trigger_event_id:    str | None
    trigger_event_type:  str | None
    decision:            str               # what action / recommendation
    reasoning:           str               # why (explainable)
    priority:            DecisionPriority
    confidence:          float             # 0.0–1.0
    tags:                list[str]
    metadata:            dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id":                 self.id,
            "agent_id":           self.agent_id,
            "agent_type":         self.agent_type,
            "agent_name":         self.agent_name,
            "simulation_time":    self.simulation_time,
            "wall_time":          self.wall_time,
            "trigger_event_id":   self.trigger_event_id,
            "trigger_event_type": self.trigger_event_type,
            "decision":           self.decision,
            "reasoning":          self.reasoning,
            "priority":           self.priority.value,
            "confidence":         round(self.confidence, 3),
            "tags":               self.tags,
            "metadata":           self.metadata,
        }


# ── Abstract base agent ────────────────────────────────────────────────────────

class BaseAgent(ABC):
    """
    Abstract base for all simulation agents.

    Subclasses implement:
      • on_event()          – react to a single SimEvent
      • get_internal_state() – return agent-specific state dict
      • get_reasoning_summary() – return a human-readable status summary
    """

    agent_type: AgentType  # must be set on each subclass

    def __init__(self, agent_id: str, name: str) -> None:
        self.agent_id   = agent_id
        self.name       = name
        self._status    = AgentStatus.IDLE
        self._decision_log: list[DecisionLog] = []
        self._last_sim_time: float = 0.0
        self._events_processed: int = 0
        self._created_wall_time: float = time.time()

    # ── Public dispatch ────────────────────────────────────────────────────────

    def process_event(
        self,
        event: SimEvent,
        snapshot: StateSnapshot,
    ) -> list[DecisionLog]:
        """
        Called by the registry for every new simulation event.
        Updates bookkeeping then delegates to on_event().
        """
        self._events_processed += 1
        self._last_sim_time = event.simulation_time
        if self._status == AgentStatus.IDLE:
            self._status = AgentStatus.ACTIVE

        decisions = self.on_event(event, snapshot)
        self._decision_log.extend(decisions)
        return decisions

    # ── Subclass interface ─────────────────────────────────────────────────────

    @abstractmethod
    def on_event(
        self,
        event: SimEvent,
        snapshot: StateSnapshot,
    ) -> list[DecisionLog]:
        """React to a simulation event. Return any decisions made."""

    @abstractmethod
    def get_internal_state(self) -> dict[str, Any]:
        """Return agent-specific bookkeeping as a JSON-safe dict."""

    @abstractmethod
    def get_reasoning_summary(self) -> str:
        """Return a single human-readable sentence describing current status."""

    # ── Decision factory ───────────────────────────────────────────────────────

    def _decide(
        self,
        sim_time: float,
        decision: str,
        reasoning: str,
        priority: DecisionPriority = DecisionPriority.MEDIUM,
        confidence: float = 0.8,
        trigger_event: SimEvent | None = None,
        tags: list[str] | None = None,
        **metadata: Any,
    ) -> DecisionLog:
        return DecisionLog(
            id=str(uuid.uuid4()),
            agent_id=self.agent_id,
            agent_type=self.agent_type.value,
            agent_name=self.name,
            simulation_time=sim_time,
            wall_time=time.time(),
            trigger_event_id=trigger_event.id if trigger_event else None,
            trigger_event_type=trigger_event.event_type.value if trigger_event else None,
            decision=decision,
            reasoning=reasoning,
            priority=priority,
            confidence=confidence,
            tags=tags or [],
            metadata=dict(metadata),
        )

    # ── Public read API ────────────────────────────────────────────────────────

    def get_state(self) -> dict[str, Any]:
        """Full serialisable agent state for the API."""
        return {
            "agent_id":           self.agent_id,
            "name":               self.name,
            "agent_type":         self.agent_type.value,
            "status":             self._status.value,
            "last_sim_time":      self._last_sim_time,
            "events_processed":   self._events_processed,
            "decisions_made":     len(self._decision_log),
            "reasoning_summary":  self.get_reasoning_summary(),
            "internal_state":     self.get_internal_state(),
        }

    def get_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent decisions (chronological, most-recent last)."""
        return [d.to_dict() for d in self._decision_log[-limit:]]

    @property
    def status(self) -> AgentStatus:
        return self._status

    @property
    def decision_count(self) -> int:
        return len(self._decision_log)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def reset(self) -> None:
        self._decision_log.clear()
        self._status = AgentStatus.IDLE
        self._last_sim_time = 0.0
        self._events_processed = 0
        self.on_reset()

    def on_reset(self) -> None:
        """Subclasses may override to reset their own internal state."""
