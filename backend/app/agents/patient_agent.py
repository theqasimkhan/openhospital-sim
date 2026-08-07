"""
PatientAgent – monitors patient population status across the hospital.

Tracks the full patient census in aggregate (not individual clinical state)
and emits operational decisions when thresholds are crossed.

Tracks
──────
  waiting · in_triage · admitted (regular ward) · in_icu
  treated (completed treatment) · discharged · deceased_simulation

Emits decisions on
──────────────────
  • Arrival surge (>2× rolling baseline in last hour-equivalent)
  • High-acuity ratio (CRITICAL+HIGH > 30 % of triaged patients)
  • Elevated mortality signal (deceased > 5 % of total handled)
  • ICU census spike
"""
from __future__ import annotations

from collections import deque
from typing import Any

from app.agents.base import AgentType, BaseAgent, DecisionLog, DecisionPriority
from app.simulation.events import SimEvent, SimEventType
from app.simulation.state import StateSnapshot


class PatientAgent(BaseAgent):
    agent_type = AgentType.PATIENT

    # Thresholds for operational decisions
    _SURGE_MULTIPLIER        = 2.0   # current rate > 2× baseline → surge
    _HIGH_ACUITY_THRESHOLD   = 0.30  # 30 % CRITICAL/HIGH triage
    _MORTALITY_THRESHOLD     = 0.05  # 5 % of resolved patients deceased
    _ICU_SPIKE_THRESHOLD     = 0.85  # 85 % ICU occupancy triggers alert
    _ROLLING_WINDOW          = 12    # last N arrivals for baseline comparison

    def __init__(self) -> None:
        super().__init__("patient-agent-001", "Patient Flow Monitor")

        # Aggregate census counters
        self.waiting:    int = 0
        self.in_triage:  int = 0
        self.admitted:   int = 0   # regular ward
        self.in_icu:     int = 0
        self.discharged: int = 0
        self.deceased:   int = 0   # simulation deaths (not clinical)
        self.total_arrivals: int = 0

        # Triage breakdown
        self._triage_counts: dict[str, int] = {
            "critical": 0, "high": 0, "medium": 0, "low": 0
        }
        self._total_triaged: int = 0

        # Arrival-rate tracking (timestamps for rolling window)
        self._arrival_times: deque[float] = deque(maxlen=200)
        self._baseline_rate: float | None = None   # arrivals per sim-minute

        # Flags (prevent re-alerting until resolved)
        self._surge_active:   bool = False
        self._icu_spike_active: bool = False

    # ── Event handler ──────────────────────────────────────────────────────────

    def on_event(self, event: SimEvent, snapshot: StateSnapshot) -> list[DecisionLog]:
        decisions: list[DecisionLog] = []
        t = event.simulation_time
        et = event.event_type

        if et == SimEventType.PATIENT_ARRIVED:
            self.waiting += 1
            self.total_arrivals += 1
            self._arrival_times.append(t)
            decisions.extend(self._check_surge(t, snapshot, event))

        elif et == SimEventType.TRIAGE_COMPLETE:
            self.waiting = max(0, self.waiting - 1)
            self.in_triage = max(0, self.in_triage - 1)
            level = event.metadata.get("triage_level", "medium")
            self._triage_counts[level] = self._triage_counts.get(level, 0) + 1
            self._total_triaged += 1
            decisions.extend(self._check_acuity_ratio(t, event))

        elif et == SimEventType.TREATMENT_STARTED:
            location = event.metadata.get("location", "regular_ward")
            if location == "regular_ward":
                self.admitted += 1

        elif et == SimEventType.ICU_TRANSFER:
            if event.metadata.get("reason") == "direct_admission" or event.metadata.get("reason") == "deterioration":
                self.admitted = max(0, self.admitted - 1)
            self.in_icu += 1
            decisions.extend(self._check_icu_spike(t, snapshot, event))

        elif et == SimEventType.DISCHARGE:
            loc = event.metadata.get("location", "regular_ward")
            if loc == "icu":
                self.in_icu = max(0, self.in_icu - 1)
            else:
                self.admitted = max(0, self.admitted - 1)
            self.discharged += 1
            # Reset ICU spike flag when pressure subsides
            if snapshot.icu_occupancy / max(1, snapshot.total_icu_beds) < 0.70:
                self._icu_spike_active = False

        elif et == SimEventType.PATIENT_DEATH:
            loc = event.metadata.get("location", "regular_ward")
            if loc == "icu":
                self.in_icu = max(0, self.in_icu - 1)
            else:
                self.admitted = max(0, self.admitted - 1)
            self.deceased += 1
            decisions.extend(self._check_mortality(t, event))

        # Update status based on snapshot
        self._sync_status(snapshot)
        return decisions

    # ── Decision checks ────────────────────────────────────────────────────────

    def _check_surge(
        self,
        t: float,
        snapshot: StateSnapshot,
        event: SimEvent,
    ) -> list[DecisionLog]:
        if len(self._arrival_times) < self._ROLLING_WINDOW:
            return []

        recent = list(self._arrival_times)[-self._ROLLING_WINDOW:]
        window_span = max(1.0, recent[-1] - recent[0])
        current_rate = (self._ROLLING_WINDOW - 1) / window_span   # per minute

        if self._baseline_rate is None:
            self._baseline_rate = current_rate
            return []

        # Update baseline with slow decay
        self._baseline_rate = 0.95 * self._baseline_rate + 0.05 * current_rate

        if current_rate > self._baseline_rate * self._SURGE_MULTIPLIER and not self._surge_active:
            self._surge_active = True
            self._status = self._agent_status_from_snapshot(snapshot)
            return [self._decide(
                t,
                decision="Flag patient arrival surge – escalate triage capacity",
                reasoning=(
                    f"Arrival rate {current_rate:.2f}/min is "
                    f"{current_rate / self._baseline_rate:.1f}× the "
                    f"{self._baseline_rate:.2f}/min baseline. "
                    f"Emergency queue: {snapshot.emergency_queue_length}. "
                    "Recommending additional triage resource allocation."
                ),
                priority=DecisionPriority.HIGH,
                confidence=0.85,
                trigger_event=event,
                tags=["surge", "triage", "capacity"],
                current_rate_per_min=round(current_rate, 3),
                baseline_rate_per_min=round(self._baseline_rate, 3),
                total_arrivals=self.total_arrivals,
            )]

        if current_rate <= self._baseline_rate * 1.1 and self._surge_active:
            self._surge_active = False

        return []

    def _check_acuity_ratio(self, t: float, event: SimEvent) -> list[DecisionLog]:
        if self._total_triaged < 10:
            return []
        high_acuity = self._triage_counts.get("critical", 0) + self._triage_counts.get("high", 0)
        ratio = high_acuity / max(1, self._total_triaged)
        if ratio > self._HIGH_ACUITY_THRESHOLD:
            return [self._decide(
                t,
                decision="High-acuity patient ratio elevated – prioritise ICU readiness",
                reasoning=(
                    f"{high_acuity} of {self._total_triaged} triaged patients "
                    f"({ratio:.1%}) are CRITICAL or HIGH severity. "
                    "ICU and specialist resources should be pre-positioned."
                ),
                priority=DecisionPriority.HIGH,
                confidence=0.80,
                trigger_event=event,
                tags=["acuity", "icu", "triage"],
                critical_count=self._triage_counts.get("critical", 0),
                high_count=self._triage_counts.get("high", 0),
                total_triaged=self._total_triaged,
                acuity_ratio=round(ratio, 3),
            )]
        return []

    def _check_icu_spike(
        self,
        t: float,
        snapshot: StateSnapshot,
        event: SimEvent,
    ) -> list[DecisionLog]:
        util = snapshot.icu_occupancy / max(1, snapshot.total_icu_beds)
        if util >= self._ICU_SPIKE_THRESHOLD and not self._icu_spike_active:
            self._icu_spike_active = True
            return [self._decide(
                t,
                decision="ICU near capacity – restrict non-critical ICU admissions",
                reasoning=(
                    f"ICU utilisation at {util:.1%} "
                    f"({snapshot.icu_occupancy}/{snapshot.total_icu_beds} beds). "
                    "Non-critical transfers should be deferred; step-down options reviewed."
                ),
                priority=DecisionPriority.CRITICAL,
                confidence=0.95,
                trigger_event=event,
                tags=["icu", "capacity", "critical"],
                icu_occupancy=snapshot.icu_occupancy,
                total_icu_beds=snapshot.total_icu_beds,
                utilization=round(util, 3),
            )]
        return []

    def _check_mortality(self, t: float, event: SimEvent) -> list[DecisionLog]:
        total_handled = self.discharged + self.deceased
        if total_handled < 10:
            return []
        rate = self.deceased / total_handled
        if rate > self._MORTALITY_THRESHOLD:
            return [self._decide(
                t,
                decision="Simulation mortality rate elevated – review resource allocation",
                reasoning=(
                    f"{self.deceased} of {total_handled} resolved patients "
                    f"({rate:.1%}) did not survive. "
                    "Operational review: consider ICU capacity, staff availability, "
                    "and triage throughput as contributing factors."
                ),
                priority=DecisionPriority.HIGH,
                confidence=0.75,
                trigger_event=event,
                tags=["mortality", "audit"],
                deceased=self.deceased,
                total_handled=total_handled,
                mortality_rate=round(rate, 3),
            )]
        return []

    def _sync_status(self, snapshot: StateSnapshot) -> None:
        icu_util = snapshot.icu_occupancy / max(1, snapshot.total_icu_beds)
        if icu_util > 0.9 or self._surge_active:
            self._status_field = "overloaded"
        elif icu_util > 0.7:
            self._status_field = "alert"

    def _agent_status_from_snapshot(self, snapshot: StateSnapshot):
        from app.agents.base import AgentStatus
        icu_util = snapshot.icu_occupancy / max(1, snapshot.total_icu_beds)
        return AgentStatus.OVERLOADED if icu_util > 0.9 else AgentStatus.ALERT

    # ── BaseAgent interface ────────────────────────────────────────────────────

    def get_internal_state(self) -> dict[str, Any]:
        total_handled = self.discharged + self.deceased
        return {
            "census": {
                "waiting":    self.waiting,
                "in_triage":  self.in_triage,
                "admitted":   self.admitted,
                "in_icu":     self.in_icu,
                "discharged": self.discharged,
                "deceased":   self.deceased,
            },
            "total_arrivals":      self.total_arrivals,
            "total_triaged":       self._total_triaged,
            "triage_breakdown":    self._triage_counts,
            "mortality_rate":      round(self.deceased / max(1, total_handled), 4),
            "acuity_ratio":        round(
                (self._triage_counts.get("critical", 0) + self._triage_counts.get("high", 0))
                / max(1, self._total_triaged),
                4,
            ),
            "surge_active":        self._surge_active,
            "icu_spike_active":    self._icu_spike_active,
            "baseline_rate_per_min": round(self._baseline_rate, 4) if self._baseline_rate else None,
        }

    def get_reasoning_summary(self) -> str:
        total_handled = self.discharged + self.deceased
        parts = [
            f"Monitoring {self.total_arrivals} total arrivals; "
            f"{self.admitted} in ward, {self.in_icu} in ICU."
        ]
        if self._surge_active:
            parts.append("SURGE ACTIVE: arrival rate above 2× baseline.")
        if self._icu_spike_active:
            parts.append("ICU near capacity.")
        if total_handled > 0:
            rate = self.deceased / total_handled
            parts.append(f"Simulation mortality rate: {rate:.1%}.")
        return " ".join(parts)

    def on_reset(self) -> None:
        self.waiting = self.in_triage = self.admitted = 0
        self.in_icu = self.discharged = self.deceased = 0
        self.total_arrivals = self._total_triaged = 0
        self._triage_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        self._arrival_times.clear()
        self._baseline_rate = None
        self._surge_active = self._icu_spike_active = False
