"""
ICUForecaster – ICU bed utilisation projection.

Projects ICU occupancy fraction using Holt's smoothing on the
`icu_utilization` field. A dedicated saturation-risk helper returns
how many steps until utilisation is expected to cross 90 % and 100 %.

Saturation risk
───────────────
If the projected utilisation crosses the critical threshold at any point
in the forecast horizon, `steps_to_saturation` returns the first such step.
A value of None means no saturation is projected in the horizon.
"""
from __future__ import annotations

from app.forecasting.base import BaseForecaster, ForecastResult, TimeSeries


class ICUForecaster(BaseForecaster):
    model_name = "holt_exponential_smoothing"

    SATURATION_THRESHOLD = 0.90   # ICU considered "at risk" above this
    CRITICAL_THRESHOLD   = 1.00   # full capacity

    @property
    def metric_name(self) -> str:
        return "icu_utilization"

    def _extract(self, time_series: TimeSeries) -> list[float]:
        return [float(pt.get("icu_utilization", 0.0)) for pt in time_series]

    def steps_to_saturation(
        self,
        forecast: ForecastResult,
        threshold: float | None = None,
    ) -> int | None:
        """
        Return the first step_ahead index where the forecast value exceeds
        `threshold`, or None if no saturation is projected.
        """
        t = threshold if threshold is not None else self.SATURATION_THRESHOLD
        for pt in forecast.points:
            if pt.value >= t:
                return pt.step_ahead
        return None

    def saturation_probability(self, forecast: ForecastResult) -> float:
        """
        Fraction of forecast points whose upper_ci exceeds the saturation
        threshold – used as a rough probability that saturation will occur.
        """
        if not forecast.points:
            return 0.0
        over = sum(1 for p in forecast.points if p.upper_ci >= self.SATURATION_THRESHOLD)
        return over / len(forecast.points)
