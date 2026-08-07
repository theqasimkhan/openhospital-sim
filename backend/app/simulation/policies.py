"""
Operational policies governing patient flow decisions.

No medical diagnosis logic – all decisions are probability-based and
driven by the SimulationConfig. Policies are stateless callables.
"""
from __future__ import annotations

import numpy as np

from app.simulation.config import SimulationConfig
from app.simulation.state import TriageLevel

# ── Triage policy ──────────────────────────────────────────────────────────────

class TriagePolicy:
    """
    Assigns a triage level to an arriving patient.

    Emergency patients have a skewed distribution toward higher severity;
    non-emergency arrivals follow the configured baseline probabilities.
    """

    # Multipliers applied to base probabilities for emergency arrivals
    _EMERGENCY_WEIGHT = {
        TriageLevel.CRITICAL: 3.5,
        TriageLevel.HIGH:     2.0,
        TriageLevel.MEDIUM:   0.7,
        TriageLevel.LOW:      0.2,
    }

    def assess(
        self,
        rng: np.random.Generator,
        config: SimulationConfig,
        is_emergency: bool = False,
    ) -> TriageLevel:
        levels = [
            TriageLevel.CRITICAL,
            TriageLevel.HIGH,
            TriageLevel.MEDIUM,
            TriageLevel.LOW,
        ]
        base_probs = [
            config.prob_critical,
            config.prob_high,
            config.prob_medium,
            config.prob_low,
        ]

        if is_emergency:
            weights = [self._EMERGENCY_WEIGHT[lv] for lv in levels]
            probs = [p * w for p, w in zip(base_probs, weights)]
            total = sum(probs)
            probs = [p / total for p in probs]
        else:
            probs = base_probs

        return TriageLevel(
            rng.choice([lv.value for lv in levels], p=probs)  # type: ignore[arg-type]
        )


# ── Admission / routing policy ─────────────────────────────────────────────────

class AdmissionPolicy:
    """Decides whether a patient should go directly to ICU after triage."""

    # Probability of direct ICU admission by triage level (overrides config)
    _ICU_DIRECT_PROB = {
        TriageLevel.CRITICAL: 1.00,
        TriageLevel.HIGH:     0.30,
        TriageLevel.MEDIUM:   0.05,
        TriageLevel.LOW:      0.00,
    }

    def needs_direct_icu(
        self,
        triage_level: TriageLevel,
        rng: np.random.Generator,
    ) -> bool:
        prob = self._ICU_DIRECT_PROB.get(triage_level, 0.0)
        return rng.random() < prob

    def needs_icu_transfer(
        self,
        triage_level: TriageLevel,
        rng: np.random.Generator,
        config: SimulationConfig,
    ) -> bool:
        """
        Decides if a patient deteriorates and needs ICU transfer
        mid-treatment in the regular ward.
        """
        # Critical and high already screened at admission; lower chance here
        level_multiplier = {
            TriageLevel.CRITICAL: 0.1,  # most went to ICU directly
            TriageLevel.HIGH:     0.5,
            TriageLevel.MEDIUM:   1.0,
            TriageLevel.LOW:      0.3,
        }.get(triage_level, 1.0)

        return rng.random() < (config.prob_icu_transfer * level_multiplier)


# ── Discharge / mortality policy ───────────────────────────────────────────────

class DischargePolicy:
    """Determines patient outcome at end of treatment."""

    def outcome_is_death(
        self,
        triage_level: TriageLevel,
        in_icu: bool,
        rng: np.random.Generator,
        config: SimulationConfig,
    ) -> bool:
        """
        Returns True if the patient does not survive their treatment.
        ICU patients have a slightly higher baseline mortality.
        """
        prob_map = {
            TriageLevel.CRITICAL: config.prob_death_critical,
            TriageLevel.HIGH:     config.prob_death_high,
            TriageLevel.MEDIUM:   config.prob_death_medium,
            TriageLevel.LOW:      config.prob_death_low,
        }
        base = prob_map.get(triage_level, 0.01)
        icu_multiplier = 1.5 if in_icu else 1.0
        return rng.random() < min(1.0, base * icu_multiplier)


# ── Triage priority helper ──────────────────────────────────────────────────────

def triage_priority(level: TriageLevel) -> int:
    """
    Map triage level to SimPy PriorityResource priority.
    Lower integer = higher priority (served first).
    """
    return {
        TriageLevel.CRITICAL: 0,
        TriageLevel.HIGH:     1,
        TriageLevel.MEDIUM:   2,
        TriageLevel.LOW:      3,
    }.get(level, 2)


# ── Module-level policy singletons ────────────────────────────────────────────
triage_policy    = TriagePolicy()
admission_policy = AdmissionPolicy()
discharge_policy = DischargePolicy()
