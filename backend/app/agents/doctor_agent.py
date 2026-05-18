"""
DoctorAgent – monitors doctor workload, schedule pressure, and fatigue.

Operational decisions (never clinical)
────────────────────────────────────────
  • Overload alert when any doctor carries > threshold concurrent patients
  • Critical-patient prioritisation flag when CRITICAL triage patients wait
  • Fatigue escalation when workload has been sustained > threshold duration
  • Staff-shortage response coordination
"""
from __future__ import annotations

from typing import Any

from app.agents.base import AgentType, BaseAgent, DecisionLog, DecisionPriority
from app.simulation.events import SimEvent, SimEventType
from app.simulation.state import StateSnapshot


class DoctorAgent(BaseAgent):
    agent_type = AgentType.DOCTOR

    _OVERLOAD_PATIENT_THRESHOLD = 4    # patients per doctor before overload flag
    _WORKLOAD_HIGH_THRESHOLD    = 0.80  # 80 % system-wide doctor utilisation
    _WORKLOAD_CRITICAL_THRESHOLD = 0.95
    _FATIGUE_DECAY              = 0.02  # fatigue drops per event tick when not overloaded
    _FATIGUE_RISE               = 0.10  # fatigue rises per overload event

    def __init__(self) -> None:
        super().__init__("doctor-agent-001", "Doctor Workload Manager")

        # Per-doctor assignment tracking
        self._assignments: dict[str, int] = {}    # doctor_id → active patient count
        self._total_assignments: int = 0
        self._total_releases: int = 0

        # Fatigue model (0.0 = fresh, 1.0 = exhausted)
        self._fatigue: float = 0.0
        self._overload_count: int = 0

        # Shortage tracking
        self._shortage_events: int = 0
        self._shortage_active: bool = False
        self._doctors_affected: int = 0

        # Flags
        self._high_workload_alerted: bool = False
        self._critical_prioritization_count: int = 0

    # ── Event handler ──────────────────────────────────────────────────────────

    def on_event(self, event: SimEvent, snapshot: StateSnapshot) -> list[DecisionLog]:
        decisions: list[DecisionLog] = []
        t = event.simulation_time
        et = event.event_type

        if et == SimEventType.DOCTOR_ASSIGNED:
            doc_id = event.metadata.get("doctor_id", "unknown")
            triage = event.metadata.get("triage_level", "medium")
            self._assignments[doc_id] = self._assignments.get(doc_id, 0) + 1
            self._total_assignments += 1
            decisions.extend(self._check_doctor_overload(t, doc_id, event))
            if triage == "critical":
                self._critical_prioritization_count += 1
                decisions.append(self._decide(
                    t,
                    decision=f"Critical-patient prioritisation: {doc_id} assigned to CRITICAL patient",
                    reasoning=(
                        f"CRITICAL triage patient assigned to {doc_id}. "
                        "Doctor queue reshuffled – CRITICAL cases bypass MEDIUM/LOW waiters."
                    ),
                    priority=DecisionPriority.HIGH,
                    confidence=0.95,
                    trigger_event=event,
                    tags=["critical", "priority", "assignment"],
                    doctor_id=doc_id,
                    triage_level=triage,
                ))

        elif et == SimEventType.DISCHARGE:
            doc_id = event.metadata.get("doctor_id") or self._find_doctor_by_load()
            if doc_id and doc_id in self._assignments:
                self._assignments[doc_id] = max(0, self._assignments[doc_id] - 1)
                if self._assignments[doc_id] == 0:
                    del self._assignments[doc_id]
            self._total_releases += 1
            self._decay_fatigue()

        elif et == SimEventType.PATIENT_DEATH:
            self._total_releases += 1
            self._decay_fatigue()

        elif et == SimEventType.STAFF_SHORTAGE:
            self._shortage_events += 1
            self._shortage_active = True
            self._doctors_affected = event.metadata.get("doctors_affected", 0)
            decisions.append(self._decide(
                t,
                decision="Activate shortage protocol – redistribute critical patients first",
                reasoning=(
                    f"Staff shortage event #{self._shortage_events}: "
                    f"{self._doctors_affected} doctors unavailable "
                    f"({event.metadata.get('staff_fraction', 0):.0%} of roster). "
                    "Recommend rescheduling non-urgent consultations and "
                    "prioritising CRITICAL/HIGH triage patients for remaining staff."
                ),
                priority=DecisionPriority.CRITICAL,
                confidence=0.90,
                trigger_event=event,
                tags=["shortage", "schedule", "critical"],
                doctors_affected=self._doctors_affected,
                shortage_number=self._shortage_events,
            ))
            self._fatigue = min(1.0, self._fatigue + self._FATIGUE_RISE * 2)

        elif et == SimEventType.STAFF_RESTORED:
            self._shortage_active = False
            self._doctors_affected = 0
            decisions.append(self._decide(
                t,
                decision="Shortage resolved – restore normal scheduling",
                reasoning="Staff availability returned to baseline. Normal scheduling can resume.",
                priority=DecisionPriority.LOW,
                confidence=0.99,
                trigger_event=event,
                tags=["shortage-resolved", "schedule"],
            ))
            self._fatigue = max(0.0, self._fatigue - 0.15)

        # Workload level check on every event
        decisions.extend(self._check_system_workload(t, snapshot, event))
        return decisions

    # ── Decision checks ────────────────────────────────────────────────────────

    def _check_doctor_overload(
        self, t: float, doctor_id: str, event: SimEvent
    ) -> list[DecisionLog]:
        count = self._assignments.get(doctor_id, 0)
        if count >= self._OVERLOAD_PATIENT_THRESHOLD:
            self._fatigue = min(1.0, self._fatigue + self._FATIGUE_RISE)
            self._overload_count += 1
            return [self._decide(
                t,
                decision=f"Overload flag: {doctor_id} has {count} concurrent patients",
                reasoning=(
                    f"{doctor_id} now carries {count} active patients "
                    f"(threshold: {self._OVERLOAD_PATIENT_THRESHOLD}). "
                    f"Cumulative fatigue index: {self._fatigue:.2f}. "
                    "Recommend redistributing next incoming assignment."
                ),
                priority=DecisionPriority.HIGH,
                confidence=0.88,
                trigger_event=event,
                tags=["overload", "doctor", "fatigue"],
                doctor_id=doctor_id,
                patient_count=count,
                fatigue_index=round(self._fatigue, 3),
            )]
        return []

    def _check_system_workload(
        self, t: float, snapshot: StateSnapshot, event: SimEvent
    ) -> list[DecisionLog]:
        workload = snapshot.doctor_workload
        if workload >= self._WORKLOAD_CRITICAL_THRESHOLD and not self._high_workload_alerted:
            self._high_workload_alerted = True
            return [self._decide(
                t,
                decision="Doctor system workload critical – escalate to admin",
                reasoning=(
                    f"System-wide doctor workload at {workload:.1%}. "
                    f"Available doctors: {snapshot.staff.available_doctors}/"
                    f"{snapshot.staff.total_doctors}. "
                    "Immediate escalation to AdminAgent for staff coordination."
                ),
                priority=DecisionPriority.CRITICAL,
                confidence=0.92,
                trigger_event=event,
                tags=["workload", "critical", "escalate"],
                workload=round(workload, 3),
                available_doctors=snapshot.staff.available_doctors,
            )]
        if workload < self._WORKLOAD_HIGH_THRESHOLD:
            self._high_workload_alerted = False
        return []

    def _decay_fatigue(self) -> None:
        self._fatigue = max(0.0, self._fatigue - self._FATIGUE_DECAY)

    def _find_doctor_by_load(self) -> str | None:
        if not self._assignments:
            return None
        return max(self._assignments, key=lambda d: self._assignments[d])

    # ── BaseAgent interface ────────────────────────────────────────────────────

    def get_internal_state(self) -> dict[str, Any]:
        return {
            "active_doctors":          len(self._assignments),
            "total_assignments":       self._total_assignments,
            "total_releases":          self._total_releases,
            "active_assignments":      dict(self._assignments),
            "fatigue_index":           round(self._fatigue, 4),
            "overload_events":         self._overload_count,
            "shortage_active":         self._shortage_active,
            "shortage_events":         self._shortage_events,
            "doctors_on_leave":        self._doctors_affected,
            "critical_prioritizations": self._critical_prioritization_count,
            "high_workload_alerted":   self._high_workload_alerted,
        }

    def get_reasoning_summary(self) -> str:
        active = len(self._assignments)
        parts = [f"Tracking {active} active doctor(s) across {self._total_assignments} assignments."]
        if self._shortage_active:
            parts.append(f"SHORTAGE ACTIVE: {self._doctors_affected} doctors unavailable.")
        if self._fatigue > 0.6:
            parts.append(f"Fatigue index elevated: {self._fatigue:.2f}.")
        parts.append(f"Critical prioritizations: {self._critical_prioritization_count}.")
        return " ".join(parts)

    def on_reset(self) -> None:
        self._assignments.clear()
        self._total_assignments = self._total_releases = 0
        self._fatigue = 0.0
        self._overload_count = self._shortage_events = 0
        self._shortage_active = False
        self._doctors_affected = 0
        self._critical_prioritization_count = 0
        self._high_workload_alerted = False
