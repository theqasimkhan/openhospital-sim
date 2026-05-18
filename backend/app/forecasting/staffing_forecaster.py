"""
StaffingForecaster – recommended staffing levels based on projected demand.

Rather than forecasting raw staff counts, this module converts projected
patient arrival rates into safe staffing recommendations using rule-based
capacity formulas derived from the simulation config defaults.

Staffing formulas
──────────────────
• doctors_needed = ceil(projected_arrivals × PATIENTS_PER_HOUR / DOCTOR_CAPACITY)
• nurses_needed  = ceil(projected_arrivals × PATIENTS_PER_HOUR / NURSE_CAPACITY)

These are conservative estimates; over-staffing is preferred to under-staffing.

The `ward_utilization` projection is also provided as a secondary metric
to detect bed pressure.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.forecasting.base import BaseForecaster, ForecastResult, TimeSeries


# ── Staffing recommendation ────────────────────────────────────────────────────

@dataclass
class StaffingRecommendation:
    step_ahead:       int
    sim_time_ahead:   float
    projected_arrivals: float
    doctors_needed:   int
    nurses_needed:    int
    confidence:       float

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_ahead":          self.step_ahead,
            "sim_time_ahead":      round(self.sim_time_ahead, 1),
            "projected_arrivals":  round(self.projected_arrivals, 2),
            "doctors_needed":      self.doctors_needed,
            "nurses_needed":       self.nurses_needed,
            "confidence":          round(self.confidence, 3),
        }


# ── Ward utilisation forecaster ────────────────────────────────────────────────

class WardUtilizationForecaster(BaseForecaster):
    model_name = "holt_exponential_smoothing"

    @property
    def metric_name(self) -> str:
        return "ward_utilization"

    def _extract(self, time_series: TimeSeries) -> list[float]:
        return [float(pt.get("ward_utilization", 0.0)) for pt in time_series]


# ── Staffing forecaster ────────────────────────────────────────────────────────

class StaffingForecaster:
    """
    Derives staffing recommendations from a projected arrivals ForecastResult.

    Capacity constants (tunable):
        DOCTOR_CAPACITY  – patients a single doctor can handle per step
        NURSE_CAPACITY   – patients a single nurse can handle per step
        SAFETY_MARGIN    – fraction to add on top of computed minimum
    """

    DOCTOR_CAPACITY: float = 4.0    # patients per step per doctor
    NURSE_CAPACITY:  float = 2.5    # patients per step per nurse
    SAFETY_MARGIN:   float = 0.20   # add 20 % headroom

    def recommend(
        self,
        demand_forecast: ForecastResult,
    ) -> list[StaffingRecommendation]:
        """
        Convert a DemandForecaster output into per-step staffing recommendations.
        """
        recommendations: list[StaffingRecommendation] = []

        for pt in demand_forecast.points:
            raw_arrivals = max(0.0, pt.value)

            doctors = math.ceil(
                raw_arrivals * (1 + self.SAFETY_MARGIN) / self.DOCTOR_CAPACITY
            )
            nurses = math.ceil(
                raw_arrivals * (1 + self.SAFETY_MARGIN) / self.NURSE_CAPACITY
            )

            # Ensure minimum viable staffing
            doctors = max(1, doctors)
            nurses  = max(2, nurses)

            recommendations.append(
                StaffingRecommendation(
                    step_ahead=pt.step_ahead,
                    sim_time_ahead=pt.sim_time_ahead,
                    projected_arrivals=raw_arrivals,
                    doctors_needed=doctors,
                    nurses_needed=nurses,
                    confidence=demand_forecast.confidence,
                )
            )

        return recommendations

    def peak_staffing(
        self,
        recommendations: list[StaffingRecommendation],
    ) -> dict[str, Any]:
        """Return the step with the highest projected staffing need."""
        if not recommendations:
            return {}
        peak = max(recommendations, key=lambda r: r.doctors_needed + r.nurses_needed)
        return {
            "step_ahead":    peak.step_ahead,
            "sim_time_ahead": peak.sim_time_ahead,
            "doctors_needed": peak.doctors_needed,
            "nurses_needed":  peak.nurses_needed,
            "confidence":     peak.confidence,
        }
