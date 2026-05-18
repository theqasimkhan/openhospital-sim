"""
AdminAgent – hospital-wide bed and staff coordination.

Operational decisions
──────────────────────
  • Bed reallocation when ICU or ward occupancy is critically high
  • Staff coordination during shortage events
  • Emergency protocol activation on spikes
  • Periodic audit of overall operational health
  • Escalation when multiple pressure signals coincide
"""
from __future__ import annotations

from typing import Any

from app.agents.base import AgentType, BaseAgent, DecisionLog, DecisionPriority
from app.simulation.events import SimEvent, SimEventType
from app.simulation.state import StateSnapshot


class AdminAgent(BaseAgent):
    agent_type = AgentType.ADMIN

    _ICU_REALLOC_THRESHOLD    = 0.80   # recommend bed reallocation
    _WARD_REALLOC_THRESHOLD   = 0.90
    _AUDIT_EVERY_STEPS        = 5      # periodic audit cadence
    _COMBINED_PRESSURE_SCORE  = 2      # how many simultaneous pressure flags trigger escalation

    def __init__(self) -> None:
        super().__init__("admin-agent-001", "Hospital Administrator")

        # Operational counters
        self._bed_reallocation_events: int = 0
        self._staff_coordination_events: int = 0
        self._emergency_protocols_activated: int = 0
        self._audit_count: int = 0
        self._steps_since_audit: int = 0
        self._escalations: int = 0

        # Current alert flags
        self._icu_realloc_active: bool = False
        self._ward_realloc_active: bool = False
        self._emergency_protocol_active: bool = False
        self._alert_level: str = "normal"   # normal | elevated | high | critical

        # Pressure tracking for combined escalation
        self._pressure_flags: set[str] = set()

    # ── Event handler ──────────────────────────────────────────────────────────

    def on_event(self, event: SimEvent, snapshot: StateSnapshot) -> list[DecisionLog]:
        decisions: list[DecisionLog] = []
        t = event.simulation_time
        et = event.event_type

        if et == SimEventType.EMERGENCY_SPIKE:
            decisions.extend(self._handle_emergency_spike(t, snapshot, event))

        elif et == SimEventType.STAFF_SHORTAGE:
            decisions.extend(self._handle_staff_shortage(t, snapshot, event))

        elif et == SimEventType.STAFF_RESTORED:
            self._pressure_flags.discard("staff_shortage")
            self._update_alert_level()

        elif et == SimEventType.ICU_TRANSFER:
            decisions.extend(self._check_icu_capacity(t, snapshot, event))

        elif et == SimEventType.DISCHARGE:
            # Capacity might have improved
            icu_util = snapshot.icu_occupancy / max(1, snapshot.total_icu_beds)
            if icu_util < 0.65 and self._icu_realloc_active:
                self._icu_realloc_active = False
                self._pressure_flags.discard("icu_pressure")
                self._update_alert_level()

        elif et == SimEventType.SIMULATION_STEPPED:
            decisions.extend(self._periodic_audit(t, snapshot, event))

        # Combined pressure escalation check
        decisions.extend(self._check_escalation(t, snapshot, event))

        # Ward capacity check on each bed-consuming event
        if et in (SimEventType.TREATMENT_STARTED, SimEventType.PATIENT_ARRIVED):
            decisions.extend(self._check_ward_capacity(t, snapshot, event))

        return decisions

    # ── Decision handlers ──────────────────────────────────────────────────────

    def _handle_emergency_spike(
        self, t: float, snapshot: StateSnapshot, event: SimEvent
    ) -> list[DecisionLog]:
        spike_size = event.metadata.get("spike_size", 0)
        self._emergency_protocols_activated += 1
        self._emergency_protocol_active = True
        self._pressure_flags.add("emergency_spike")
        self._update_alert_level()

        return [self._decide(
            t,
            decision=(
                f"Emergency protocol #{self._emergency_protocols_activated} activated "
                f"– surge of {spike_size} patients"
            ),
            reasoning=(
                f"Emergency spike #{event.metadata.get('spike_number', '?')} detected: "
                f"{spike_size} patients arriving simultaneously. "
                f"Current ICU: {snapshot.icu_occupancy}/{snapshot.total_icu_beds}, "
                f"Ward: {snapshot.regular_bed_occupancy}/{snapshot.total_regular_beds}. "
                "Actions: hold elective admissions, call in on-call staff, "
                "prepare overflow beds, brief all department heads."
            ),
            priority=DecisionPriority.CRITICAL,
            confidence=0.98,
            trigger_event=event,
            tags=["emergency", "protocol", "surge"],
            spike_size=spike_size,
            protocol_number=self._emergency_protocols_activated,
            alert_level=self._alert_level,
        )]

    def _handle_staff_shortage(
        self, t: float, snapshot: StateSnapshot, event: SimEvent
    ) -> list[DecisionLog]:
        self._staff_coordination_events += 1
        self._pressure_flags.add("staff_shortage")
        self._update_alert_level()
        doctors_affected = event.metadata.get("doctors_affected", 0)
        nurses_affected  = event.metadata.get("nurses_affected", 0)

        return [self._decide(
            t,
            decision="Staff coordination initiated – shortage mitigation plan activated",
            reasoning=(
                f"Shortage event #{self._staff_coordination_events}: "
                f"{doctors_affected} doctors, {nurses_affected} nurses unavailable "
                f"for ~{event.metadata.get('duration_minutes', '?'):.0f} min. "
                "Mitigation: cross-train nurses for triage assist, freeze non-urgent "
                "elective procedures, activate agency staff request."
            ),
            priority=DecisionPriority.HIGH,
            confidence=0.90,
            trigger_event=event,
            tags=["shortage", "coordination", "mitigation"],
            doctors_affected=doctors_affected,
            nurses_affected=nurses_affected,
            coordination_event_number=self._staff_coordination_events,
        )]

    def _check_icu_capacity(
        self, t: float, snapshot: StateSnapshot, event: SimEvent
    ) -> list[DecisionLog]:
        icu_util = snapshot.icu_occupancy / max(1, snapshot.total_icu_beds)
        if icu_util >= self._ICU_REALLOC_THRESHOLD and not self._icu_realloc_active:
            self._icu_realloc_active = True
            self._bed_reallocation_events += 1
            self._pressure_flags.add("icu_pressure")
            self._update_alert_level()
            return [self._decide(
                t,
                decision=f"ICU bed reallocation #{self._bed_reallocation_events} – convert step-down beds",
                reasoning=(
                    f"ICU at {icu_util:.1%} capacity "
                    f"({snapshot.icu_occupancy}/{snapshot.total_icu_beds}). "
                    "Recommend converting 5 high-dependency ward beds to ICU-equivalent. "
                    "Step-down criteria to be reviewed for eligible ICU patients."
                ),
                priority=DecisionPriority.HIGH,
                confidence=0.88,
                trigger_event=event,
                tags=["icu", "reallocation", "beds"],
                icu_util=round(icu_util, 3),
                reallocation_number=self._bed_reallocation_events,
            )]
        return []

    def _check_ward_capacity(
        self, t: float, snapshot: StateSnapshot, event: SimEvent
    ) -> list[DecisionLog]:
        ward_util = snapshot.regular_bed_occupancy / max(1, snapshot.total_regular_beds)
        if ward_util >= self._WARD_REALLOC_THRESHOLD and not self._ward_realloc_active:
            self._ward_realloc_active = True
            self._pressure_flags.add("ward_pressure")
            self._update_alert_level()
            return [self._decide(
                t,
                decision="Ward capacity critical – activate overflow management",
                reasoning=(
                    f"Regular ward at {ward_util:.1%} "
                    f"({snapshot.regular_bed_occupancy}/{snapshot.total_regular_beds} beds). "
                    "Overflow protocol: expedite discharges for stable patients, "
                    "open overflow ward section, reduce scheduled admissions."
                ),
                priority=DecisionPriority.CRITICAL,
                confidence=0.91,
                trigger_event=event,
                tags=["ward", "overflow", "capacity"],
                ward_util=round(ward_util, 3),
            )]
        if ward_util < 0.70 and self._ward_realloc_active:
            self._ward_realloc_active = False
            self._pressure_flags.discard("ward_pressure")
            self._update_alert_level()
        return []

    def _periodic_audit(
        self, t: float, snapshot: StateSnapshot, event: SimEvent
    ) -> list[DecisionLog]:
        self._steps_since_audit += 1
        if self._steps_since_audit < self._AUDIT_EVERY_STEPS:
            return []
        self._steps_since_audit = 0
        self._audit_count += 1

        icu_util  = snapshot.icu_occupancy / max(1, snapshot.total_icu_beds)
        ward_util = snapshot.regular_bed_occupancy / max(1, snapshot.total_regular_beds)
        priority  = (
            DecisionPriority.INFO if max(icu_util, ward_util) < 0.6
            else DecisionPriority.LOW if max(icu_util, ward_util) < 0.8
            else DecisionPriority.MEDIUM
        )

        return [self._decide(
            t,
            decision=f"Operational audit #{self._audit_count} – status {self._alert_level.upper()}",
            reasoning=(
                f"Step {event.metadata.get('step_number', '?')} audit: "
                f"ICU {icu_util:.1%}, ward {ward_util:.1%}, "
                f"queue {snapshot.emergency_queue_length}, "
                f"doctors {snapshot.staff.available_doctors}/{snapshot.staff.total_doctors}, "
                f"nurses {snapshot.staff.available_nurses}/{snapshot.staff.total_nurses}. "
                f"Alert level: {self._alert_level}."
            ),
            priority=priority,
            confidence=1.0,
            trigger_event=event,
            tags=["audit", "periodic"],
            icu_utilization=round(icu_util, 3),
            ward_utilization=round(ward_util, 3),
            alert_level=self._alert_level,
            active_pressures=list(self._pressure_flags),
        )]

    def _check_escalation(
        self, t: float, snapshot: StateSnapshot, event: SimEvent
    ) -> list[DecisionLog]:
        if len(self._pressure_flags) >= self._COMBINED_PRESSURE_SCORE:
            self._escalations += 1
            flags = list(self._pressure_flags)
            return [self._decide(
                t,
                decision=f"Multi-system escalation #{self._escalations} – hospital command activated",
                reasoning=(
                    f"{len(flags)} simultaneous pressure signals: {', '.join(flags)}. "
                    "All department heads convened. Hospital incident command structure activated. "
                    "External mutual-aid request being considered."
                ),
                priority=DecisionPriority.CRITICAL,
                confidence=0.97,
                trigger_event=event,
                tags=["escalation", "command", "multi-system"],
                pressure_flags=flags,
                escalation_number=self._escalations,
            )]
        return []

    def _update_alert_level(self) -> None:
        n = len(self._pressure_flags)
        if n == 0:
            self._alert_level = "normal"
        elif n == 1:
            self._alert_level = "elevated"
        elif n == 2:
            self._alert_level = "high"
        else:
            self._alert_level = "critical"

    # ── BaseAgent interface ────────────────────────────────────────────────────

    def get_internal_state(self) -> dict[str, Any]:
        return {
            "alert_level":                   self._alert_level,
            "active_pressure_flags":         list(self._pressure_flags),
            "bed_reallocation_events":        self._bed_reallocation_events,
            "staff_coordination_events":      self._staff_coordination_events,
            "emergency_protocols_activated":  self._emergency_protocols_activated,
            "audit_count":                    self._audit_count,
            "escalations":                    self._escalations,
            "icu_realloc_active":             self._icu_realloc_active,
            "ward_realloc_active":            self._ward_realloc_active,
            "emergency_protocol_active":      self._emergency_protocol_active,
        }

    def get_reasoning_summary(self) -> str:
        parts = [f"Hospital alert level: {self._alert_level.upper()}."]
        if self._pressure_flags:
            parts.append(f"Active pressures: {', '.join(self._pressure_flags)}.")
        parts.append(
            f"Stats: {self._bed_reallocation_events} realloc events, "
            f"{self._emergency_protocols_activated} emergency protocols, "
            f"{self._audit_count} audits completed."
        )
        return " ".join(parts)

    def on_reset(self) -> None:
        self._bed_reallocation_events = 0
        self._staff_coordination_events = 0
        self._emergency_protocols_activated = 0
        self._audit_count = self._steps_since_audit = 0
        self._escalations = 0
        self._icu_realloc_active = False
        self._ward_realloc_active = False
        self._emergency_protocol_active = False
        self._alert_level = "normal"
        self._pressure_flags.clear()
