"""
SurgeDetector – real-time emergency surge risk assessment.

Detection logic
───────────────
1. Z-score of the most recent N arrivals vs the historical distribution.
   z = (x_recent − μ_historical) / max(ε, σ_historical)

2. Queue pressure: normalised emergency queue length.

3. ICU pressure: current utilisation relative to saturation threshold.

4. Trend acceleration: is the arrival trend steepening? (second derivative)

5. Recent spike events: count of EMERGENCY_SPIKE entries in last W steps.

Risk levels
───────────
    LOW      z < 1.0  and no other elevated signals
    MEDIUM   1.0 ≤ z < 2.0  OR single elevated signal
    HIGH     2.0 ≤ z < 3.0  OR multiple elevated signals
    CRITICAL z ≥ 3.0  OR ICU utilisation > 90 %

Upgrade path
────────────
Replace z-score with an LSTM anomaly score or Isolation Forest score
by overriding _arrival_zscore(); the rest of the pipeline stays intact.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from app.forecasting.base import TimeSeries
from app.simulation.state import StateSnapshot

RiskLevel = Literal["low", "medium", "high", "critical"]


@dataclass
class SurgeSignalDetail:
    arrival_zscore:      float
    queue_length:        int
    queue_trend:         str       # "increasing" | "stable" | "decreasing"
    icu_utilization:     float
    icu_trend:           str       # "rising" | "stable" | "falling"
    recent_spike_events: int
    data_points:         int

    def to_dict(self) -> dict[str, Any]:
        return {
            "arrival_zscore":      round(self.arrival_zscore, 3),
            "queue_length":        self.queue_length,
            "queue_trend":         self.queue_trend,
            "icu_utilization":     round(self.icu_utilization, 4),
            "icu_trend":           self.icu_trend,
            "recent_spike_events": self.recent_spike_events,
            "data_points":         self.data_points,
        }


@dataclass
class SurgeRiskResult:
    simulation_time:     float
    risk_level:          RiskLevel
    risk_score:          float          # composite [0, 1]
    arrival_trend:       str
    confidence:          float
    signals:             SurgeSignalDetail
    message:             str
    recommended_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "simulation_time":    self.simulation_time,
            "risk_level":         self.risk_level,
            "risk_score":         round(self.risk_score, 4),
            "arrival_trend":      self.arrival_trend,
            "confidence":         round(self.confidence, 3),
            "signals":            self.signals.to_dict(),
            "message":            self.message,
            "recommended_actions": self.recommended_actions,
        }


class SurgeDetector:
    """
    Analyses the ForecastingAgent time series + current StateSnapshot
    and produces a structured SurgeRiskResult.
    """

    # Thresholds
    _ZSCORE_MEDIUM   = 1.0
    _ZSCORE_HIGH     = 2.0
    _ZSCORE_CRITICAL = 3.0
    _ICU_HIGH        = 0.80
    _ICU_CRITICAL    = 0.90
    _QUEUE_MEDIUM    = 5
    _QUEUE_HIGH      = 10
    _SPIKE_WINDOW    = 5   # look-back window (steps) for spike counting

    def assess(
        self,
        time_series: TimeSeries,
        state: StateSnapshot,
    ) -> SurgeRiskResult:
        n = len(time_series)
        arrivals = [float(pt.get("arrivals", 0)) for pt in time_series]
        icu_utils = [float(pt.get("icu_utilization", 0.0)) for pt in time_series]

        # ── Signal 1: Z-score of recent vs historical arrivals ─────────────────
        zscore = self._arrival_zscore(arrivals)

        # ── Signal 2: Queue pressure ──────────────────────────────────────────
        queue = state.emergency_queue_length
        queue_trend = self._series_trend(
            [pt.get("emergency_queue", 0) for pt in time_series[-self._SPIKE_WINDOW:]]
        )

        # ── Signal 3: ICU pressure ────────────────────────────────────────────
        icu_util = state.icu_occupancy / max(1, state.total_icu_beds)
        icu_trend = self._series_trend(icu_utils[-self._SPIKE_WINDOW:])

        # ── Signal 4: Recent spike events ─────────────────────────────────────
        # Spike appears as a big jump in arrivals (> 2× step average)
        spike_count = self._count_spikes(arrivals[-self._SPIKE_WINDOW:]) if n >= 2 else 0

        # ── Arrival trend ─────────────────────────────────────────────────────
        arrival_trend = self._classify_trend(arrivals)

        # ── Composite risk score ──────────────────────────────────────────────
        risk_score = self._composite_score(zscore, queue, icu_util, spike_count)
        risk_level = self._risk_level(zscore, icu_util, risk_score)
        confidence = min(0.92, 0.30 + n * 0.062)

        signals = SurgeSignalDetail(
            arrival_zscore=zscore,
            queue_length=queue,
            queue_trend=queue_trend,
            icu_utilization=icu_util,
            icu_trend=icu_trend,
            recent_spike_events=spike_count,
            data_points=n,
        )

        message = self._build_message(risk_level, zscore, icu_util, queue)
        actions = self._recommended_actions(risk_level, signals)

        return SurgeRiskResult(
            simulation_time=state.simulation_time,
            risk_level=risk_level,
            risk_score=risk_score,
            arrival_trend=arrival_trend,
            confidence=confidence,
            signals=signals,
            message=message,
            recommended_actions=actions,
        )

    # ── Signal calculations ────────────────────────────────────────────────────

    def _arrival_zscore(self, arrivals: list[float]) -> float:
        if len(arrivals) < 3:
            return 0.0
        historical = arrivals[:-1]
        mu  = float(np.mean(historical))
        std = float(np.std(historical))
        recent = arrivals[-1]
        return (recent - mu) / max(1e-6, std)

    def _composite_score(
        self,
        zscore:      float,
        queue:       int,
        icu_util:    float,
        spike_count: int,
    ) -> float:
        # Normalise each signal to [0, 1]
        z_score_norm  = min(1.0, max(0.0, zscore)        / self._ZSCORE_CRITICAL)
        queue_norm    = min(1.0, max(0, queue - self._QUEUE_MEDIUM) / 15.0)
        icu_norm      = min(1.0, max(0.0, icu_util - self._ICU_HIGH) / 0.20)
        spike_norm    = min(1.0, spike_count / 3.0)

        # Weighted average (z-score and ICU are most predictive)
        composite = (
            z_score_norm * 0.35
            + queue_norm  * 0.20
            + icu_norm    * 0.30
            + spike_norm  * 0.15
        )
        return round(composite, 4)

    def _risk_level(
        self, zscore: float, icu_util: float, composite: float
    ) -> RiskLevel:
        if zscore >= self._ZSCORE_CRITICAL or icu_util >= self._ICU_CRITICAL:
            return "critical"
        if zscore >= self._ZSCORE_HIGH or composite >= 0.60:
            return "high"
        if zscore >= self._ZSCORE_MEDIUM or composite >= 0.30:
            return "medium"
        return "low"

    # ── Trend helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _series_trend(values: list[Any]) -> str:
        floats = [float(v) for v in values if v is not None]
        if len(floats) < 2:
            return "stable"
        delta = floats[-1] - floats[0]
        scale = max(1e-6, abs(floats[0]))
        if delta / scale > 0.10:
            return "increasing"
        if delta / scale < -0.10:
            return "decreasing"
        return "stable"

    @staticmethod
    def _classify_trend(arrivals: list[float]) -> str:
        if len(arrivals) < 3:
            return "unknown"
        n = len(arrivals)
        first = sum(arrivals[: n // 3]) / max(1, n // 3)
        last  = sum(arrivals[-(n // 3):]) / max(1, n // 3)
        delta = (last - first) / max(1e-9, abs(first))
        if delta > 0.15:
            return "increasing"
        if delta < -0.15:
            return "decreasing"
        return "stable"

    @staticmethod
    def _count_spikes(arrivals: list[float]) -> int:
        """Count steps where arrivals are > 2× the window average."""
        if len(arrivals) < 2:
            return 0
        mean = sum(arrivals) / len(arrivals)
        return sum(1 for a in arrivals if a > mean * 2.0)

    # ── Message & actions ──────────────────────────────────────────────────────

    def _build_message(
        self,
        level: RiskLevel,
        zscore: float,
        icu_util: float,
        queue: int,
    ) -> str:
        if level == "critical":
            primary = (
                f"CRITICAL surge risk: arrival rate {zscore:.1f}σ above baseline"
                if zscore >= self._ZSCORE_CRITICAL
                else f"CRITICAL ICU pressure: {icu_util:.0%} utilisation"
            )
            return f"{primary}. Immediate action required."
        if level == "high":
            return (
                f"High surge risk: arrival rate {zscore:.1f}σ above baseline, "
                f"emergency queue at {queue}."
            )
        if level == "medium":
            return (
                f"Moderate surge risk: arrival rate {zscore:.1f}σ above baseline. "
                "Monitor closely."
            )
        return "Surge risk is LOW. Hospital operating within normal parameters."

    @staticmethod
    def _recommended_actions(
        level: RiskLevel,
        signals: SurgeSignalDetail,
    ) -> list[str]:
        actions: list[str] = []

        if level == "critical":
            actions += [
                "Activate mass-casualty incident (MCI) protocol immediately.",
                "Call in off-duty medical staff.",
                "Initiate inter-hospital transfer arrangements for stable ICU patients.",
                "Halt elective admissions to free ward capacity.",
            ]
        elif level == "high":
            actions += [
                "Pre-position additional nursing staff for next shift.",
                "Review ICU discharge candidates to free beds.",
                "Notify senior administrators of developing surge.",
            ]
        elif level == "medium":
            actions += [
                "Monitor arrival rate over the next 2 simulation steps.",
                "Prepare contingency staffing schedule.",
            ]

        if signals.icu_utilization >= 0.85:
            actions.append(
                f"ICU at {signals.icu_utilization:.0%} capacity. "
                "Expedite discharge reviews for stable ICU patients."
            )

        if signals.queue_trend == "increasing" and signals.queue_length > 3:
            actions.append(
                f"Emergency queue growing ({signals.queue_length} patients). "
                "Consider opening overflow triage area."
            )

        return actions
