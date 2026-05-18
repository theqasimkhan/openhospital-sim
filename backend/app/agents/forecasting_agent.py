"""
ForecastingAgent – collects time-series metrics for demand prediction.

This agent is a data-collection and trend-analysis layer. It does not make
clinical predictions; it prepares structured operational forecast signals:

  • Arrival rate trend (decreasing / stable / increasing / surge)
  • ICU and ward occupancy trends
  • Simple moving-average demand comparison
  • Peak demand period detection
  • Early-warning signal when rate is accelerating
"""
from __future__ import annotations

from collections import deque
from typing import Any

from app.agents.base import AgentType, BaseAgent, DecisionLog, DecisionPriority
from app.simulation.events import SimEvent, SimEventType
from app.simulation.state import StateSnapshot


class ForecastingAgent(BaseAgent):
    agent_type = AgentType.FORECASTING

    _WINDOW_SIZE         = 10   # data points for moving average
    _SURGE_RATE_FACTOR   = 1.8  # rate > 1.8× MA → surge prediction
    _TREND_CHANGE_FACTOR = 1.25  # rate > 1.25× MA → increasing trend

    def __init__(self) -> None:
        super().__init__("forecasting-agent-001", "Demand Forecasting Agent")

        # Time-series buckets (one entry per simulation step)
        self._step_metrics: list[dict[str, Any]] = []

        # Arrivals per step (rolling)
        self._arrivals_this_step: int = 0
        self._current_step: int = 0

        # Moving average
        self._arrival_ma_window: deque[int] = deque(maxlen=self._WINDOW_SIZE)

        # Trend state
        self._demand_trend: str = "stable"       # decreasing | stable | increasing | surge
        self._last_trend: str = "stable"
        self._peak_step: int | None = None
        self._peak_arrivals: int = 0

        # Occupancy tracking
        self._icu_util_history: deque[float] = deque(maxlen=self._WINDOW_SIZE)
        self._ward_util_history: deque[float] = deque(maxlen=self._WINDOW_SIZE)

        # Forecast confidence
        self._forecast_confidence: float = 0.5
        self._data_points: int = 0

    # ── Event handler ──────────────────────────────────────────────────────────

    def on_event(self, event: SimEvent, snapshot: StateSnapshot) -> list[DecisionLog]:
        decisions: list[DecisionLog] = []
        t = event.simulation_time
        et = event.event_type

        if et == SimEventType.PATIENT_ARRIVED:
            self._arrivals_this_step += 1

        elif et == SimEventType.SIMULATION_STEPPED:
            decisions.extend(self._process_step_end(t, snapshot, event))

        elif et == SimEventType.EMERGENCY_SPIKE:
            spike_size = event.metadata.get("spike_size", 0)
            decisions.extend(self._handle_spike_signal(t, spike_size, snapshot, event))

        return decisions

    # ── Step-end processing ────────────────────────────────────────────────────

    def _process_step_end(
        self, t: float, snapshot: StateSnapshot, event: SimEvent
    ) -> list[DecisionLog]:
        step_num = event.metadata.get("step_number", self._current_step + 1)
        self._current_step = step_num
        self._data_points += 1
        arrivals = self._arrivals_this_step
        self._arrivals_this_step = 0

        icu_util  = snapshot.icu_occupancy / max(1, snapshot.total_icu_beds)
        ward_util = snapshot.regular_bed_occupancy / max(1, snapshot.total_regular_beds)

        # Record data point
        self._step_metrics.append({
            "step":             step_num,
            "simulation_time":  t,
            "arrivals":         arrivals,
            "icu_utilization":  round(icu_util, 4),
            "ward_utilization": round(ward_util, 4),
            "emergency_queue":  snapshot.emergency_queue_length,
            "discharged_total": snapshot.discharged_count,
            "deceased_total":   snapshot.deceased_count,
        })

        # Update peak
        if arrivals > self._peak_arrivals:
            self._peak_arrivals = arrivals
            self._peak_step = step_num

        # Update rolling collections
        self._arrival_ma_window.append(arrivals)
        self._icu_util_history.append(icu_util)
        self._ward_util_history.append(ward_util)

        # Enough data → compute trend
        decisions: list[DecisionLog] = []
        if len(self._arrival_ma_window) >= 3:
            decisions.extend(self._compute_trend(t, arrivals, snapshot, event))

        # Improve confidence with data
        self._forecast_confidence = min(0.90, 0.40 + self._data_points * 0.05)

        return decisions

    def _compute_trend(
        self,
        t: float,
        arrivals: int,
        snapshot: StateSnapshot,
        event: SimEvent,
    ) -> list[DecisionLog]:
        history = list(self._arrival_ma_window)
        ma = sum(history) / len(history)

        # Determine trend
        if ma < 0.5:
            new_trend = "stable"
        elif arrivals > ma * self._SURGE_RATE_FACTOR:
            new_trend = "surge"
        elif arrivals > ma * self._TREND_CHANGE_FACTOR:
            new_trend = "increasing"
        elif arrivals < ma * (2.0 - self._TREND_CHANGE_FACTOR):
            new_trend = "decreasing"
        else:
            new_trend = "stable"

        decisions: list[DecisionLog] = []
        if new_trend != self._last_trend:
            self._demand_trend = new_trend
            old_trend = self._last_trend
            self._last_trend = new_trend
            priority = {
                "surge":      DecisionPriority.HIGH,
                "increasing": DecisionPriority.MEDIUM,
                "decreasing": DecisionPriority.LOW,
                "stable":     DecisionPriority.INFO,
            }.get(new_trend, DecisionPriority.INFO)

            decisions.append(self._decide(
                t,
                decision=f"Demand trend changed: {old_trend.upper()} → {new_trend.upper()}",
                reasoning=(
                    f"Step {self._current_step}: {arrivals} arrivals vs "
                    f"{ma:.1f} moving-average over last {len(history)} steps. "
                    f"ICU trend: {self._trend_direction(self._icu_util_history)}. "
                    f"Ward trend: {self._trend_direction(self._ward_util_history)}. "
                    f"Forecast confidence: {self._forecast_confidence:.0%}."
                ),
                priority=priority,
                confidence=self._forecast_confidence,
                trigger_event=event,
                tags=["trend", "demand", new_trend],
                step=self._current_step,
                arrivals_this_step=arrivals,
                moving_average=round(ma, 2),
                old_trend=old_trend,
                new_trend=new_trend,
                icu_utilization=round(snapshot.icu_occupancy / max(1, snapshot.total_icu_beds), 3),
                ward_utilization=round(snapshot.regular_bed_occupancy / max(1, snapshot.total_regular_beds), 3),
            ))

        return decisions

    def _handle_spike_signal(
        self,
        t: float,
        spike_size: int,
        snapshot: StateSnapshot,
        event: SimEvent,
    ) -> list[DecisionLog]:
        # Spike significantly above moving average → early warning
        if len(self._arrival_ma_window) < 2:
            return []
        ma = sum(self._arrival_ma_window) / len(self._arrival_ma_window)
        excess = spike_size / max(1.0, ma)

        return [self._decide(
            t,
            decision=f"Emergency spike early-warning signal – {excess:.1f}× above moving average",
            reasoning=(
                f"Spike of {spike_size} emergency patients is {excess:.1f}× the "
                f"{ma:.1f} arrival/step moving average. "
                f"If arrival surge continues, ICU capacity of {snapshot.total_icu_beds} "
                f"may be exhausted within "
                f"{self._estimate_icu_saturation(snapshot, spike_size):.0f} minutes. "
                f"Forecast confidence: {self._forecast_confidence:.0%}."
            ),
            priority=DecisionPriority.HIGH if excess > 3 else DecisionPriority.MEDIUM,
            confidence=min(0.90, self._forecast_confidence + 0.10),
            trigger_event=event,
            tags=["spike", "forecast", "early-warning"],
            spike_size=spike_size,
            moving_average=round(ma, 2),
            excess_factor=round(excess, 2),
            estimated_icu_saturation_minutes=self._estimate_icu_saturation(snapshot, spike_size),
        )]

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _trend_direction(self, series: deque[float]) -> str:
        if len(series) < 2:
            return "unknown"
        first_half = list(series)[: len(series) // 2]
        second_half = list(series)[len(series) // 2 :]
        avg1 = sum(first_half) / max(1, len(first_half))
        avg2 = sum(second_half) / max(1, len(second_half))
        delta = avg2 - avg1
        if delta > 0.05:
            return "rising"
        if delta < -0.05:
            return "falling"
        return "stable"

    def _estimate_icu_saturation(
        self, snapshot: StateSnapshot, spike_size: int
    ) -> float:
        """Rough linear estimate: how many minutes until ICU full at current rate."""
        available = snapshot.available_icu_beds
        if available <= 0:
            return 0.0
        # Assume fraction of spike ends up in ICU (~30 % of high-acuity)
        icu_demand_per_step = max(1.0, spike_size * 0.30)
        return max(0.0, available / icu_demand_per_step * 60.0)   # convert to minutes

    # ── BaseAgent interface ────────────────────────────────────────────────────

    def get_internal_state(self) -> dict[str, Any]:
        history = list(self._arrival_ma_window)
        ma = sum(history) / len(history) if history else 0.0
        return {
            "data_points_collected":  self._data_points,
            "current_step":           self._current_step,
            "demand_trend":           self._demand_trend,
            "forecast_confidence":    round(self._forecast_confidence, 3),
            "arrivals_moving_average": round(ma, 2),
            "peak_arrivals_per_step": self._peak_arrivals,
            "peak_step":              self._peak_step,
            "icu_util_trend":         self._trend_direction(self._icu_util_history),
            "ward_util_trend":        self._trend_direction(self._ward_util_history),
            "total_steps_tracked":    len(self._step_metrics),
            "recent_metrics":         self._step_metrics[-5:] if self._step_metrics else [],
        }

    def get_reasoning_summary(self) -> str:
        history = list(self._arrival_ma_window)
        ma = sum(history) / len(history) if history else 0.0
        parts = [
            f"Demand trend: {self._demand_trend.upper()}. "
            f"Arrivals MA: {ma:.1f}/step. "
            f"Confidence: {self._forecast_confidence:.0%}."
        ]
        if self._peak_step:
            parts.append(f"Peak: {self._peak_arrivals} arrivals at step {self._peak_step}.")
        parts.append(
            f"ICU trend: {self._trend_direction(self._icu_util_history)}, "
            f"ward trend: {self._trend_direction(self._ward_util_history)}."
        )
        return " ".join(parts)

    def get_time_series(self) -> list[dict[str, Any]]:
        """Return all collected step metrics for external consumers."""
        return list(self._step_metrics)

    def on_reset(self) -> None:
        self._step_metrics.clear()
        self._arrivals_this_step = 0
        self._current_step = 0
        self._arrival_ma_window.clear()
        self._demand_trend = "stable"
        self._last_trend = "stable"
        self._peak_step = None
        self._peak_arrivals = 0
        self._icu_util_history.clear()
        self._ward_util_history.clear()
        self._forecast_confidence = 0.5
        self._data_points = 0
