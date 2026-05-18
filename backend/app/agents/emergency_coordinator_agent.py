"""
EmergencyCoordinatorAgent – detects and coordinates responses to emergency spikes.

Operational decisions
──────────────────────
  • Spike detection and severity classification
  • Alert level escalation / de-escalation (normal → elevated → high → critical)
  • Response protocol activation with specific action lists
  • Double-trouble detection (shortage + spike simultaneously)
  • All-clear declaration when pressure subsides
"""
from __future__ import annotations

from typing import Any

from app.agents.base import AgentType, BaseAgent, DecisionLog, DecisionPriority
from app.simulation.events import SimEvent, SimEventType
from app.simulation.state import StateSnapshot


class EmergencyCoordinatorAgent(BaseAgent):
    agent_type = AgentType.EMERGENCY_COORDINATOR

    # Spike severity classification by patient count
    _SEVERITY_MINOR    = 4
    _SEVERITY_MODERATE = 7
    _SEVERITY_MAJOR    = 10

    # Time after spike (sim minutes) before declaring all-clear
    _ALL_CLEAR_WINDOW  = 60.0

    def __init__(self) -> None:
        super().__init__("emergency-coord-001", "Emergency Coordinator")

        # Spike history
        self._total_spikes: int = 0
        self._spike_severities: dict[str, int] = {"minor": 0, "moderate": 0, "major": 0}
        self._current_spike_active: bool = False
        self._current_spike_number: int = 0
        self._current_spike_size: int = 0
        self._current_spike_time: float | None = None
        self._current_severity: str = "none"

        # Alert level
        self._alert_level: str = "normal"   # normal | elevated | high | critical

        # Concurrent conditions
        self._shortage_active: bool = False
        self._double_trouble_alerted: bool = False

        # Response tracking
        self._protocols_activated: int = 0
        self._all_clears_declared: int = 0
        self._response_actions: list[str] = []

    # ── Event handler ──────────────────────────────────────────────────────────

    def on_event(self, event: SimEvent, snapshot: StateSnapshot) -> list[DecisionLog]:
        decisions: list[DecisionLog] = []
        t = event.simulation_time
        et = event.event_type

        if et == SimEventType.EMERGENCY_SPIKE:
            decisions.extend(self._handle_spike(t, snapshot, event))

        elif et == SimEventType.STAFF_SHORTAGE:
            self._shortage_active = True
            if self._current_spike_active and not self._double_trouble_alerted:
                self._double_trouble_alerted = True
                decisions.append(self._decide(
                    t,
                    decision="DOUBLE-TROUBLE: Emergency spike + staff shortage simultaneously",
                    reasoning=(
                        f"Staff shortage coincides with active emergency spike "
                        f"#{self._current_spike_number} ({self._current_spike_size} patients). "
                        f"{event.metadata.get('doctors_affected', 0)} doctors and "
                        f"{event.metadata.get('nurses_affected', 0)} nurses unavailable. "
                        "Immediate escalation: mutual aid from neighbouring hospitals, "
                        "all non-emergency admissions suspended."
                    ),
                    priority=DecisionPriority.CRITICAL,
                    confidence=1.0,
                    trigger_event=event,
                    tags=["double-trouble", "spike", "shortage", "escalation"],
                    spike_number=self._current_spike_number,
                    spike_size=self._current_spike_size,
                    doctors_affected=event.metadata.get("doctors_affected", 0),
                    nurses_affected=event.metadata.get("nurses_affected", 0),
                ))

        elif et == SimEventType.STAFF_RESTORED:
            self._shortage_active = False
            self._double_trouble_alerted = False

        elif et == SimEventType.SIMULATION_STEPPED:
            decisions.extend(self._check_all_clear(t, snapshot, event))

        elif et == SimEventType.DISCHARGE:
            decisions.extend(self._check_de_escalation(t, snapshot, event))

        return decisions

    # ── Spike handling ─────────────────────────────────────────────────────────

    def _handle_spike(
        self, t: float, snapshot: StateSnapshot, event: SimEvent
    ) -> list[DecisionLog]:
        spike_size   = event.metadata.get("spike_size", 0)
        spike_number = event.metadata.get("spike_number", self._total_spikes + 1)
        self._total_spikes += 1
        self._current_spike_active = True
        self._current_spike_number = spike_number
        self._current_spike_size   = spike_size
        self._current_spike_time   = t
        self._protocols_activated += 1

        severity, priority, actions = self._classify_spike(spike_size, snapshot)
        self._current_severity = severity
        self._spike_severities[severity] = self._spike_severities.get(severity, 0) + 1
        self._alert_level = self._severity_to_alert(severity)
        self._response_actions = actions

        return [self._decide(
            t,
            decision=(
                f"{severity.upper()} emergency spike #{spike_number} – "
                f"response protocol #{self._protocols_activated} activated"
            ),
            reasoning=(
                f"{spike_size} patients arrived simultaneously at t={t:.1f} min. "
                f"Severity: {severity}. Current hospital status: "
                f"ICU {snapshot.icu_occupancy}/{snapshot.total_icu_beds}, "
                f"ward {snapshot.regular_bed_occupancy}/{snapshot.total_regular_beds}, "
                f"queue {snapshot.emergency_queue_length}. "
                f"Response actions: {'; '.join(actions)}."
            ),
            priority=priority,
            confidence=0.97,
            trigger_event=event,
            tags=["spike", severity, "response"],
            spike_size=spike_size,
            severity=severity,
            alert_level=self._alert_level,
            response_actions=actions,
            icu_utilization=round(snapshot.icu_occupancy / max(1, snapshot.total_icu_beds), 3),
            ward_utilization=round(snapshot.regular_bed_occupancy / max(1, snapshot.total_regular_beds), 3),
        )]

    def _classify_spike(
        self,
        spike_size: int,
        snapshot: StateSnapshot,
    ) -> tuple[str, DecisionPriority, list[str]]:
        icu_pressure = snapshot.icu_occupancy / max(1, snapshot.total_icu_beds) > 0.80

        if spike_size >= self._SEVERITY_MAJOR or (spike_size >= self._SEVERITY_MODERATE and icu_pressure):
            return "major", DecisionPriority.CRITICAL, [
                "Activate mass-casualty protocol",
                "Call all on-call staff immediately",
                "Open overflow triage area",
                "Contact external hospitals for mutual aid",
                "Suspend all elective admissions",
            ]
        if spike_size >= self._SEVERITY_MODERATE:
            return "moderate", DecisionPriority.HIGH, [
                "Activate surge protocol",
                "Call on-call nursing staff",
                "Open additional triage bays",
                "Prepare ICU overflow plan",
            ]
        return "minor", DecisionPriority.MEDIUM, [
            "Alert triage staff",
            "Pre-position extra triage nurses",
            "Monitor ICU availability",
        ]

    def _severity_to_alert(self, severity: str) -> str:
        return {"minor": "elevated", "moderate": "high", "major": "critical"}.get(severity, "normal")

    # ── De-escalation / all-clear ──────────────────────────────────────────────

    def _check_all_clear(
        self, t: float, snapshot: StateSnapshot, event: SimEvent
    ) -> list[DecisionLog]:
        if not self._current_spike_active or self._current_spike_time is None:
            return []
        if t - self._current_spike_time < self._ALL_CLEAR_WINDOW:
            return []
        # Pressure has subsided if queue is manageable
        queue_ok  = snapshot.emergency_queue_length <= 3
        icu_ok    = snapshot.icu_occupancy / max(1, snapshot.total_icu_beds) < 0.85
        if queue_ok and icu_ok:
            self._current_spike_active = False
            self._current_severity = "none"
            self._alert_level = "normal"
            self._all_clears_declared += 1
            return [self._decide(
                t,
                decision=f"All-clear #{self._all_clears_declared} – returning to normal operations",
                reasoning=(
                    f"Emergency spike #{self._current_spike_number} contained. "
                    f"Queue: {snapshot.emergency_queue_length} (≤3). "
                    f"ICU: {snapshot.icu_occupancy}/{snapshot.total_icu_beds} (<85 %). "
                    "Releasing surge resources; stand-down on-call staff; "
                    "resuming normal admission scheduling."
                ),
                priority=DecisionPriority.LOW,
                confidence=0.90,
                trigger_event=event,
                tags=["all-clear", "de-escalation"],
                spike_number=self._current_spike_number,
                all_clear_number=self._all_clears_declared,
                queue_length=snapshot.emergency_queue_length,
                icu_occupancy=snapshot.icu_occupancy,
            )]
        return []

    def _check_de_escalation(
        self, t: float, snapshot: StateSnapshot, event: SimEvent
    ) -> list[DecisionLog]:
        if not self._current_spike_active:
            return []
        icu_util = snapshot.icu_occupancy / max(1, snapshot.total_icu_beds)
        new_alert = "elevated" if icu_util < 0.70 else self._alert_level
        if new_alert != self._alert_level and self._alert_level != "normal":
            old = self._alert_level
            self._alert_level = new_alert
            return [self._decide(
                t,
                decision=f"Alert level de-escalated: {old.upper()} → {new_alert.upper()}",
                reasoning=(
                    f"Hospital pressure reducing. ICU at {icu_util:.1%}, "
                    f"queue at {snapshot.emergency_queue_length}. "
                    "Gradually releasing surge resources."
                ),
                priority=DecisionPriority.LOW,
                confidence=0.85,
                trigger_event=event,
                tags=["de-escalation", "alert-level"],
                old_alert_level=old,
                new_alert_level=new_alert,
            )]
        return []

    # ── BaseAgent interface ────────────────────────────────────────────────────

    def get_internal_state(self) -> dict[str, Any]:
        return {
            "alert_level":              self._alert_level,
            "current_spike_active":     self._current_spike_active,
            "current_spike_number":     self._current_spike_number,
            "current_spike_size":       self._current_spike_size,
            "current_spike_time":       self._current_spike_time,
            "current_severity":         self._current_severity,
            "total_spikes":             self._total_spikes,
            "spike_severities":         self._spike_severities,
            "shortage_active":          self._shortage_active,
            "double_trouble_alerted":   self._double_trouble_alerted,
            "protocols_activated":      self._protocols_activated,
            "all_clears_declared":      self._all_clears_declared,
            "last_response_actions":    self._response_actions,
        }

    def get_reasoning_summary(self) -> str:
        parts = [f"Alert level: {self._alert_level.upper()}."]
        if self._current_spike_active:
            parts.append(
                f"Active {self._current_severity} spike #{self._current_spike_number} "
                f"({self._current_spike_size} patients at t={self._current_spike_time:.0f})."
            )
        parts.append(
            f"History: {self._total_spikes} spikes total, "
            f"{self._protocols_activated} protocols activated."
        )
        if self._shortage_active and self._current_spike_active:
            parts.append("DOUBLE-TROUBLE: simultaneous spike + shortage.")
        return " ".join(parts)

    def on_reset(self) -> None:
        self._total_spikes = 0
        self._spike_severities = {"minor": 0, "moderate": 0, "major": 0}
        self._current_spike_active = False
        self._current_spike_number = 0
        self._current_spike_size = 0
        self._current_spike_time = None
        self._current_severity = "none"
        self._alert_level = "normal"
        self._shortage_active = False
        self._double_trouble_alerted = False
        self._protocols_activated = 0
        self._all_clears_declared = 0
        self._response_actions = []
