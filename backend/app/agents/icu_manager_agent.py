"""
ICUManagerAgent – ICU resource allocation and constraint management.

Operational decisions
──────────────────────
  • ICU admission approval (capacity-gated)
  • Capacity warning at 80 % utilisation
  • Critical capacity alert at 95 % utilisation
  • Step-down recommendation when stable ICU patients could transfer to ward
  • Queue management when ICU beds unavailable
"""
from __future__ import annotations

from collections import deque
from typing import Any

from app.agents.base import AgentType, BaseAgent, DecisionLog, DecisionPriority
from app.simulation.events import SimEvent, SimEventType
from app.simulation.state import StateSnapshot


class ICUManagerAgent(BaseAgent):
    agent_type = AgentType.ICU_MANAGER

    _WARNING_THRESHOLD  = 0.80
    _CRITICAL_THRESHOLD = 0.95
    _STEP_DOWN_TRIGGER  = 0.75   # recommend step-down when above this and discharge event fires

    def __init__(self) -> None:
        super().__init__("icu-manager-001", "ICU Resource Manager")

        # Admission tracking
        self._total_admissions: int = 0
        self._direct_admissions: int = 0      # from triage
        self._transfer_admissions: int = 0    # deterioration from ward
        self._discharges_from_icu: int = 0
        self._deaths_in_icu: int = 0

        # Capacity state
        self._current_utilization: float = 0.0
        self._capacity_warnings: int = 0
        self._critical_alerts: int = 0
        self._step_down_recommendations: int = 0

        # Queue pressure (patients waiting for an ICU bed)
        self._icu_wait_queue: deque[str] = deque()  # patient IDs
        self._total_icu_waits: int = 0

        # Alert flags
        self._warning_active: bool = False
        self._critical_active: bool = False

    # ── Event handler ──────────────────────────────────────────────────────────

    def on_event(self, event: SimEvent, snapshot: StateSnapshot) -> list[DecisionLog]:
        decisions: list[DecisionLog] = []
        t = event.simulation_time
        et = event.event_type

        self._current_utilization = snapshot.icu_occupancy / max(1, snapshot.total_icu_beds)

        if et == SimEventType.ICU_TRANSFER:
            reason = event.metadata.get("reason", "direct_admission")
            self._total_admissions += 1
            if reason == "direct_admission":
                self._direct_admissions += 1
            else:
                self._transfer_admissions += 1

            decisions.extend(self._check_admission(t, snapshot, event))

        elif et == SimEventType.DISCHARGE:
            if event.metadata.get("location") == "icu":
                self._discharges_from_icu += 1
                self._icu_wait_queue.clear()   # simplification: queue re-evaluated
                decisions.extend(self._check_step_down(t, snapshot, event))

        elif et == SimEventType.PATIENT_DEATH:
            if event.metadata.get("location") == "icu":
                self._deaths_in_icu += 1

        # Capacity threshold checks on every event
        decisions.extend(self._check_capacity_thresholds(t, snapshot, event))
        return decisions

    # ── Decision checks ────────────────────────────────────────────────────────

    def _check_admission(
        self, t: float, snapshot: StateSnapshot, event: SimEvent
    ) -> list[DecisionLog]:
        avail = snapshot.available_icu_beds
        reason = event.metadata.get("reason", "direct_admission")
        patient_id = event.patient_id or "unknown"
        triage = event.metadata.get("triage_level", "unknown")

        if avail > 0:
            return [self._decide(
                t,
                decision=f"ICU admission approved for {patient_id} ({reason})",
                reasoning=(
                    f"ICU bed allocated: {snapshot.icu_occupancy + 1}/{snapshot.total_icu_beds} "
                    f"(utilisation {self._current_utilization:.1%} after admission). "
                    f"Admission reason: {reason}. Triage: {triage}. "
                    f"Remaining available beds: {avail - 1}."
                ),
                priority=DecisionPriority.MEDIUM if avail > 3 else DecisionPriority.HIGH,
                confidence=0.99,
                trigger_event=event,
                tags=["icu", "admission", reason],
                patient_id=patient_id,
                available_before=avail,
                total_admissions=self._total_admissions,
            )]
        else:
            self._icu_wait_queue.append(patient_id)
            self._total_icu_waits += 1
            return [self._decide(
                t,
                decision=f"ICU full – patient {patient_id} queued (wait #{self._total_icu_waits})",
                reasoning=(
                    f"ICU at 100 % capacity ({snapshot.icu_occupancy}/{snapshot.total_icu_beds}). "
                    f"Patient {patient_id} (triage: {triage}) placed in ICU queue. "
                    "Step-down candidates being reviewed; ward escalation in progress."
                ),
                priority=DecisionPriority.CRITICAL,
                confidence=0.99,
                trigger_event=event,
                tags=["icu", "queue", "full"],
                patient_id=patient_id,
                queue_position=len(self._icu_wait_queue),
                total_icu_waits=self._total_icu_waits,
            )]

    def _check_capacity_thresholds(
        self, t: float, snapshot: StateSnapshot, event: SimEvent
    ) -> list[DecisionLog]:
        util = self._current_utilization
        decisions: list[DecisionLog] = []

        if util >= self._CRITICAL_THRESHOLD and not self._critical_active:
            self._critical_active = True
            self._critical_alerts += 1
            decisions.append(self._decide(
                t,
                decision=f"ICU CRITICAL capacity alert #{self._critical_alerts}",
                reasoning=(
                    f"ICU utilisation at {util:.1%} "
                    f"({snapshot.icu_occupancy}/{snapshot.total_icu_beds} beds occupied). "
                    "CRITICAL threshold exceeded. Initiating: "
                    "(1) Step-down review for all stable ICU patients, "
                    "(2) Defer all non-emergency ICU transfers, "
                    "(3) Escalate to AdminAgent for mutual-aid request."
                ),
                priority=DecisionPriority.CRITICAL,
                confidence=0.99,
                trigger_event=event,
                tags=["icu", "critical", "capacity"],
                utilization=round(util, 3),
                occupancy=snapshot.icu_occupancy,
                total_beds=snapshot.total_icu_beds,
                alert_number=self._critical_alerts,
            ))

        elif util >= self._WARNING_THRESHOLD and not self._warning_active:
            self._warning_active = True
            self._capacity_warnings += 1
            decisions.append(self._decide(
                t,
                decision=f"ICU capacity warning #{self._capacity_warnings} at {util:.1%}",
                reasoning=(
                    f"ICU utilisation crossed 80 % warning threshold "
                    f"({snapshot.icu_occupancy}/{snapshot.total_icu_beds}). "
                    "Proactive measures: begin step-down eligibility review, "
                    "notify ward coordinator, prepare overflow contingency."
                ),
                priority=DecisionPriority.HIGH,
                confidence=0.95,
                trigger_event=event,
                tags=["icu", "warning", "capacity"],
                utilization=round(util, 3),
                warning_number=self._capacity_warnings,
            ))

        if util < self._WARNING_THRESHOLD:
            self._warning_active = False
            self._critical_active = False

        return decisions

    def _check_step_down(
        self, t: float, snapshot: StateSnapshot, event: SimEvent
    ) -> list[DecisionLog]:
        util = self._current_utilization
        if util >= self._STEP_DOWN_TRIGGER and snapshot.available_regular_beds > 5:
            self._step_down_recommendations += 1
            return [self._decide(
                t,
                decision=f"Step-down recommendation #{self._step_down_recommendations}",
                reasoning=(
                    f"ICU at {util:.1%} and a bed just freed by discharge. "
                    f"Ward has {snapshot.available_regular_beds} available beds. "
                    "Recommend clinical review of stable ICU patients for step-down "
                    "to the regular ward to maximise ICU throughput."
                ),
                priority=DecisionPriority.MEDIUM,
                confidence=0.82,
                trigger_event=event,
                tags=["step-down", "icu", "throughput"],
                icu_utilization=round(util, 3),
                available_ward_beds=snapshot.available_regular_beds,
                recommendation_number=self._step_down_recommendations,
            )]
        return []

    # ── BaseAgent interface ────────────────────────────────────────────────────

    def get_internal_state(self) -> dict[str, Any]:
        return {
            "current_utilization":         round(self._current_utilization, 4),
            "total_admissions":            self._total_admissions,
            "direct_admissions":           self._direct_admissions,
            "transfer_admissions":         self._transfer_admissions,
            "discharges_from_icu":         self._discharges_from_icu,
            "deaths_in_icu":               self._deaths_in_icu,
            "capacity_warnings":           self._capacity_warnings,
            "critical_alerts":             self._critical_alerts,
            "step_down_recommendations":   self._step_down_recommendations,
            "icu_queue_length":            len(self._icu_wait_queue),
            "total_icu_waits":             self._total_icu_waits,
            "warning_active":              self._warning_active,
            "critical_active":             self._critical_active,
        }

    def get_reasoning_summary(self) -> str:
        parts = [
            f"ICU utilisation: {self._current_utilization:.1%}. "
            f"Admissions: {self._total_admissions} "
            f"({self._direct_admissions} direct, {self._transfer_admissions} transfers)."
        ]
        if self._critical_active:
            parts.append("CRITICAL: ICU at/above 95 %.")
        elif self._warning_active:
            parts.append("WARNING: ICU above 80 %.")
        if len(self._icu_wait_queue) > 0:
            parts.append(f"{len(self._icu_wait_queue)} patients in ICU queue.")
        return " ".join(parts)

    def on_reset(self) -> None:
        self._total_admissions = self._direct_admissions = self._transfer_admissions = 0
        self._discharges_from_icu = self._deaths_in_icu = 0
        self._current_utilization = 0.0
        self._capacity_warnings = self._critical_alerts = 0
        self._step_down_recommendations = 0
        self._icu_wait_queue.clear()
        self._total_icu_waits = 0
        self._warning_active = self._critical_active = False
