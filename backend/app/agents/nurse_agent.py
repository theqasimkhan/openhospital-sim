"""
NurseAgent – monitors nurse workload and queue-support activations.

Operational decisions
──────────────────────
  • Workload critical alert when nurse-to-patient ratio degrades
  • Queue support activation when emergency queue grows
  • ICU nursing pressure when ICU occupancy is high
  • Shortage coverage when staff shortage reduces nurse availability
"""
from __future__ import annotations

from typing import Any

from app.agents.base import AgentType, BaseAgent, DecisionLog, DecisionPriority
from app.simulation.events import SimEvent, SimEventType
from app.simulation.state import StateSnapshot


class NurseAgent(BaseAgent):
    agent_type = AgentType.NURSE

    _WORKLOAD_WARNING_THRESHOLD  = 0.70
    _WORKLOAD_CRITICAL_THRESHOLD = 0.90
    _QUEUE_SUPPORT_THRESHOLD     = 5    # emergency queue length
    _ICU_NURSING_PRESSURE        = 0.80  # ICU utilisation → elevated nursing load

    def __init__(self) -> None:
        super().__init__("nurse-agent-001", "Nurse Workload Coordinator")

        self._current_patient_load: int = 0      # patients nurse staff is actively supporting
        self._queue_support_activations: int = 0
        self._shortage_coverage_events: int = 0
        self._shortage_active: bool = False
        self._nurses_affected: int = 0

        # Alert flags
        self._workload_critical_alerted: bool = False
        self._queue_support_active: bool = False
        self._icu_pressure_alerted: bool = False

    # ── Event handler ──────────────────────────────────────────────────────────

    def on_event(self, event: SimEvent, snapshot: StateSnapshot) -> list[DecisionLog]:
        decisions: list[DecisionLog] = []
        t = event.simulation_time
        et = event.event_type

        if et == SimEventType.TREATMENT_STARTED:
            self._current_patient_load += 1

        elif et in (SimEventType.DISCHARGE, SimEventType.PATIENT_DEATH):
            self._current_patient_load = max(0, self._current_patient_load - 1)

        elif et == SimEventType.PATIENT_ARRIVED:
            decisions.extend(self._check_queue_support(t, snapshot, event))

        elif et == SimEventType.STAFF_SHORTAGE:
            self._shortage_active = True
            self._nurses_affected = event.metadata.get("nurses_affected", 0)
            self._shortage_coverage_events += 1
            decisions.append(self._decide(
                t,
                decision="Shortage coverage mode – redistribute nursing assignments",
                reasoning=(
                    f"{self._nurses_affected} nurses unavailable "
                    f"(shortage event #{self._shortage_coverage_events}). "
                    "Recommend cross-training reallocation: ward nurses to support "
                    "ICU overflow; reduce non-essential administrative nursing tasks."
                ),
                priority=DecisionPriority.HIGH,
                confidence=0.88,
                trigger_event=event,
                tags=["shortage", "coverage", "reallocation"],
                nurses_affected=self._nurses_affected,
            ))

        elif et == SimEventType.STAFF_RESTORED:
            self._shortage_active = False
            self._nurses_affected = 0
            decisions.append(self._decide(
                t,
                decision="Nursing roster restored – return to standard assignments",
                reasoning="Staff shortage resolved; nursing team back to full complement.",
                priority=DecisionPriority.LOW,
                confidence=0.99,
                trigger_event=event,
                tags=["shortage-resolved"],
            ))

        # Periodic workload checks
        decisions.extend(self._check_workload(t, snapshot, event))
        decisions.extend(self._check_icu_pressure(t, snapshot, event))
        return decisions

    # ── Decision checks ────────────────────────────────────────────────────────

    def _check_workload(
        self, t: float, snapshot: StateSnapshot, event: SimEvent
    ) -> list[DecisionLog]:
        workload = snapshot.nurse_workload
        if workload >= self._WORKLOAD_CRITICAL_THRESHOLD and not self._workload_critical_alerted:
            self._workload_critical_alerted = True
            self._status_override("overloaded")
            return [self._decide(
                t,
                decision="Nurse workload critical – request on-call staff activation",
                reasoning=(
                    f"Nurse workload at {workload:.1%} "
                    f"({snapshot.staff.available_nurses} available nurses, "
                    f"{snapshot.icu_occupancy + snapshot.regular_bed_occupancy} bedded patients). "
                    "On-call nurses should be activated immediately to maintain safe ratios."
                ),
                priority=DecisionPriority.CRITICAL,
                confidence=0.93,
                trigger_event=event,
                tags=["workload", "critical", "on-call"],
                nurse_workload=round(workload, 3),
                available_nurses=snapshot.staff.available_nurses,
                total_bedded=snapshot.icu_occupancy + snapshot.regular_bed_occupancy,
            )]
        if workload < self._WORKLOAD_WARNING_THRESHOLD and self._workload_critical_alerted:
            self._workload_critical_alerted = False
            self._status_override("active")
        return []

    def _check_queue_support(
        self, t: float, snapshot: StateSnapshot, event: SimEvent
    ) -> list[DecisionLog]:
        q = snapshot.emergency_queue_length
        if q >= self._QUEUE_SUPPORT_THRESHOLD and not self._queue_support_active:
            self._queue_support_active = True
            self._queue_support_activations += 1
            return [self._decide(
                t,
                decision="Queue support activated – nurses deployed to triage assist",
                reasoning=(
                    f"Emergency queue length {q} reached threshold "
                    f"({self._QUEUE_SUPPORT_THRESHOLD}). "
                    "Nurses assigned to triage-assist duties to speed patient throughput."
                ),
                priority=DecisionPriority.MEDIUM,
                confidence=0.82,
                trigger_event=event,
                tags=["queue", "triage", "support"],
                queue_length=q,
                activation_number=self._queue_support_activations,
            )]
        if q < 2 and self._queue_support_active:
            self._queue_support_active = False
        return []

    def _check_icu_pressure(
        self, t: float, snapshot: StateSnapshot, event: SimEvent
    ) -> list[DecisionLog]:
        icu_util = snapshot.icu_occupancy / max(1, snapshot.total_icu_beds)
        if icu_util >= self._ICU_NURSING_PRESSURE and not self._icu_pressure_alerted:
            self._icu_pressure_alerted = True
            return [self._decide(
                t,
                decision="ICU nursing pressure elevated – assign extra support nurses",
                reasoning=(
                    f"ICU at {icu_util:.1%} capacity "
                    f"({snapshot.icu_occupancy}/{snapshot.total_icu_beds} beds). "
                    "ICU patients require higher nurse-to-patient ratios. "
                    "Recommend routing 2 ward nurses to ICU support."
                ),
                priority=DecisionPriority.HIGH,
                confidence=0.87,
                trigger_event=event,
                tags=["icu", "nursing", "pressure"],
                icu_occupancy=snapshot.icu_occupancy,
                icu_utilization=round(icu_util, 3),
            )]
        if icu_util < 0.60 and self._icu_pressure_alerted:
            self._icu_pressure_alerted = False
        return []

    def _status_override(self, status_str: str) -> None:
        from app.agents.base import AgentStatus
        mapping = {
            "overloaded": AgentStatus.OVERLOADED,
            "active": AgentStatus.ACTIVE,
            "alert": AgentStatus.ALERT,
        }
        self._status = mapping.get(status_str, AgentStatus.ACTIVE)

    # ── BaseAgent interface ────────────────────────────────────────────────────

    def get_internal_state(self) -> dict[str, Any]:
        return {
            "current_patient_load":      self._current_patient_load,
            "queue_support_activations": self._queue_support_activations,
            "queue_support_active":      self._queue_support_active,
            "shortage_coverage_events":  self._shortage_coverage_events,
            "shortage_active":           self._shortage_active,
            "nurses_on_leave":           self._nurses_affected,
            "workload_critical_alerted": self._workload_critical_alerted,
            "icu_pressure_alerted":      self._icu_pressure_alerted,
        }

    def get_reasoning_summary(self) -> str:
        parts = [f"Tracking {self._current_patient_load} patients under nursing care."]
        if self._shortage_active:
            parts.append(f"SHORTAGE: {self._nurses_affected} nurses unavailable.")
        if self._workload_critical_alerted:
            parts.append("Workload CRITICAL – on-call activation recommended.")
        if self._queue_support_active:
            parts.append("Queue support mode active.")
        if self._icu_pressure_alerted:
            parts.append("ICU nursing pressure elevated.")
        return " ".join(parts)

    def on_reset(self) -> None:
        self._current_patient_load = 0
        self._queue_support_activations = 0
        self._shortage_coverage_events = 0
        self._shortage_active = False
        self._nurses_affected = 0
        self._workload_critical_alerted = False
        self._queue_support_active = False
        self._icu_pressure_alerted = False
