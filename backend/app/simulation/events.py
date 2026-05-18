"""
Event types and replay-ready event log for the simulation.

Design goals
────────────
• Every state-changing action produces a SimEvent with full metadata.
• The EventLog is append-only and serialisable → enables event sourcing /
  replay by re-running the engine with the same seed and replaying events.
• Snapshots stored alongside the log support rollback-ready inspection.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any


# ── Event taxonomy ─────────────────────────────────────────────────────────────

class SimEventType(str, Enum):
    # Patient lifecycle
    PATIENT_ARRIVED     = "patient_arrived"
    TRIAGE_COMPLETE     = "triage_complete"
    DOCTOR_ASSIGNED     = "doctor_assigned"
    TREATMENT_STARTED   = "treatment_started"
    ICU_TRANSFER        = "icu_transfer"
    DISCHARGE           = "discharge"
    PATIENT_DEATH       = "patient_death"

    # Operational events
    EMERGENCY_SPIKE     = "emergency_spike"
    STAFF_SHORTAGE      = "staff_shortage"
    STAFF_RESTORED      = "staff_restored"

    # Engine lifecycle
    SIMULATION_STARTED  = "simulation_started"
    SIMULATION_STEPPED  = "simulation_stepped"
    SIMULATION_RESET    = "simulation_reset"


# ── Immutable event record ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class SimEvent:
    """A single timestamped simulation event, suitable for replay and audit."""

    id: str                      # UUID4 – unique across the log
    simulation_time: float       # seconds into simulated time (minutes in our unit)
    step_number: int             # which engine step produced this event (0-indexed)
    event_type: SimEventType
    patient_id: str | None       # None for non-patient events
    metadata: dict[str, Any]     # arbitrary key-value context

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "simulation_time": self.simulation_time,
            "step_number": self.step_number,
            "event_type": self.event_type.value,
            "patient_id": self.patient_id,
            "metadata": self.metadata,
        }


# ── Append-only event log ──────────────────────────────────────────────────────

class EventLog:
    """
    Append-only, replay-ready event store.

    Thread-safety note: designed for single-threaded SimPy execution;
    all access is serialised by the engine-level asyncio.Lock.
    """

    def __init__(self) -> None:
        self._events: list[SimEvent] = []
        self._step_number: int = 0

    # ── Write ──────────────────────────────────────────────────────────────────

    def record(
        self,
        sim_time: float,
        event_type: SimEventType,
        patient_id: str | None = None,
        **metadata: Any,
    ) -> SimEvent:
        event = SimEvent(
            id=str(uuid.uuid4()),
            simulation_time=sim_time,
            step_number=self._step_number,
            event_type=event_type,
            patient_id=patient_id,
            metadata=dict(metadata),
        )
        self._events.append(event)
        return event

    def advance_step(self) -> None:
        """Called by the engine at the start of each step."""
        self._step_number += 1

    # ── Read ───────────────────────────────────────────────────────────────────

    def all(self) -> list[SimEvent]:
        return list(self._events)

    def since_time(self, sim_time: float) -> list[SimEvent]:
        return [e for e in self._events if e.simulation_time >= sim_time]

    def since_step(self, step: int) -> list[SimEvent]:
        return [e for e in self._events if e.step_number >= step]

    def by_type(self, event_type: SimEventType) -> list[SimEvent]:
        return [e for e in self._events if e.event_type == event_type]

    def by_patient(self, patient_id: str) -> list[SimEvent]:
        return [e for e in self._events if e.patient_id == patient_id]

    @property
    def count(self) -> int:
        return len(self._events)

    @property
    def current_step(self) -> int:
        return self._step_number

    # ── Snapshot / restore (for rollback-ready structure) ──────────────────────

    def snapshot(self) -> list[SimEvent]:
        """Return a shallow copy of the current event list for snapshotting."""
        return list(self._events)

    def restore(self, snapshot: list[SimEvent], step_number: int) -> None:
        """Restore the log to a previously snapshotted state."""
        self._events = list(snapshot)
        self._step_number = step_number

    def clear(self) -> None:
        self._events = []
        self._step_number = 0
