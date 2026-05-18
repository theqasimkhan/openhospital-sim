"""
Simulation configuration – all tunable parameters in one place.

All time values are in simulation minutes unless noted otherwise.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SimulationConfig:
    # ── Reproducibility ───────────────────────────────────────────────────────
    seed: int = 42

    # ── Hospital capacity ─────────────────────────────────────────────────────
    icu_beds: int = 20
    regular_beds: int = 80
    num_doctors: int = 15
    num_nurses: int = 40
    num_equipment_units: int = 30

    # ── Patient arrivals ──────────────────────────────────────────────────────
    # Exponential inter-arrival; ~6 patients/hour at 10-min mean
    mean_inter_arrival_minutes: float = 10.0

    # ── Triage durations (exponential mean) ───────────────────────────────────
    triage_duration_mean: float = 5.0

    # ── Treatment durations (exponential mean) ────────────────────────────────
    treatment_duration_mean: float = 120.0      # regular ward: 2 hours
    icu_treatment_duration_mean: float = 2880.0  # ICU: 2 days

    # ── Triage level probabilities (must sum to 1.0) ──────────────────────────
    prob_critical: float = 0.05
    prob_high: float = 0.20
    prob_medium: float = 0.45
    prob_low: float = 0.30

    # ── ICU transfer probability (from regular ward mid-treatment) ────────────
    prob_icu_transfer: float = 0.08

    # ── Mortality probabilities per triage level ──────────────────────────────
    prob_death_critical: float = 0.15
    prob_death_high: float = 0.05
    prob_death_medium: float = 0.01
    prob_death_low: float = 0.001

    # ── Emergency spike process ───────────────────────────────────────────────
    spike_interval_mean: float = 480.0   # one spike every ~8 hours
    spike_size_min: int = 3
    spike_size_max: int = 10

    # ── Staff shortage process ────────────────────────────────────────────────
    shortage_interval_mean: float = 1440.0   # roughly once per day
    shortage_duration_mean: float = 120.0    # lasts ~2 hours
    shortage_staff_fraction: float = 0.30    # 30 % of staff unavailable

    # ── Simulation stepping ───────────────────────────────────────────────────
    default_step_minutes: float = 60.0       # 1 simulated hour per API step
    max_simulation_time: float = 10_080.0    # 1 simulated week cap

    # ── Derived: total beds ───────────────────────────────────────────────────
    @property
    def total_beds(self) -> int:
        return self.icu_beds + self.regular_beds

    def validate(self) -> None:
        """Raise ValueError on obviously invalid config."""
        prob_sum = self.prob_critical + self.prob_high + self.prob_medium + self.prob_low
        if not (0.999 < prob_sum < 1.001):
            raise ValueError(f"Triage probabilities must sum to 1.0, got {prob_sum:.4f}")
        if self.icu_beds < 1 or self.regular_beds < 1:
            raise ValueError("Hospital must have at least 1 ICU and 1 regular bed")
        if self.num_doctors < 1 or self.num_nurses < 1:
            raise ValueError("Hospital must have at least 1 doctor and 1 nurse")


# Module-level default – used when no override is supplied
DEFAULT_CONFIG = SimulationConfig()
