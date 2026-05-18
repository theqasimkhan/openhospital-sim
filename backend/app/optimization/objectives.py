"""
Objective functions for hospital resource optimization.

Each objective scores a candidate Solution against the current StateSnapshot,
returning a float in [0.0, 1.0] where 1.0 is the ideal outcome.

Analytical approximations
──────────────────────────
Objectives use closed-form formulas rather than running a new simulation.
This trades accuracy for speed, making 1000+ evaluations per second feasible.
The approximations are conservative: they under-estimate improvement so
the optimizer does not over-commit resources.

Extending
─────────
To add a new objective, subclass ObjectiveFunction and add an instance to
OBJECTIVES. Adjust WEIGHTS to change the composite scoring.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.optimization.base import ObjectiveScore, Solution
from app.simulation.state import StateSnapshot


# ── Abstract objective ─────────────────────────────────────────────────────────

class ObjectiveFunction(ABC):
    name: str
    weight: float

    @abstractmethod
    def score(
        self,
        solution: Solution,
        state: StateSnapshot,
    ) -> ObjectiveScore:
        """Return an ObjectiveScore with score in [0, 1]."""
        ...


# ── 1. Minimize waiting time ───────────────────────────────────────────────────

class MinimizeWaitingTime(ObjectiveFunction):
    """
    Penalise configurations where the emergency queue per doctor is high.

    Proxy formula:
        queue_per_doctor = emergency_queue / max(1, doctors_on_duty)
        score = max(0, 1 - queue_per_doctor / TARGET_QUEUE_PER_DOCTOR)

    A queue of ≤2 patients per doctor is considered ideal (score=1.0).
    The score degrades linearly as the queue grows.
    """
    name = "minimize_waiting_time"
    weight = 0.30

    _TARGET_QUEUE_PER_DOC = 2.0   # ideal: ≤2 waiting per active doctor
    _MAX_QUEUE_PER_DOC    = 20.0  # score → 0 at this point

    def score(self, solution: Solution, state: StateSnapshot) -> ObjectiveScore:
        doctors = max(1.0, solution.get("doctors_on_duty", state.staff.total_doctors))
        queue   = max(0,   state.emergency_queue_length)
        # Also account for patients waiting for a doctor
        total_wait = queue + max(0, state.regular_bed_occupancy - int(doctors))
        q_per_doc  = total_wait / doctors
        raw_score  = max(0.0, 1.0 - max(0.0, q_per_doc - self._TARGET_QUEUE_PER_DOC)
                         / (self._MAX_QUEUE_PER_DOC - self._TARGET_QUEUE_PER_DOC))
        return ObjectiveScore(
            name=self.name,
            score=raw_score,
            weight=self.weight,
            detail={
                "queue_length":    queue,
                "doctors_on_duty": int(doctors),
                "queue_per_doctor": round(q_per_doc, 2),
            },
        )


# ── 2. Maximize throughput ────────────────────────────────────────────────────

class MaximizeThroughput(ObjectiveFunction):
    """
    Reward configurations that can process patients as fast as they arrive.

    Throughput capacity index (TCI):
        TCI = (doctors × DOC_FACTOR + nurses × NURSE_FACTOR) / active_patients

    TCI ≥ 1.0 means supply ≥ demand → score = 1.0.
    TCI < 1.0 → score degrades linearly.
    """
    name = "maximize_throughput"
    weight = 0.25

    _DOC_FACTOR   = 1.0   # relative service rate contribution per doctor
    _NURSE_FACTOR = 0.35  # relative contribution per nurse

    def score(self, solution: Solution, state: StateSnapshot) -> ObjectiveScore:
        doctors = max(1.0, solution.get("doctors_on_duty", state.staff.total_doctors))
        nurses  = max(1.0, solution.get("nurses_on_duty",  state.staff.total_nurses))
        active  = max(1,   state.regular_bed_occupancy + state.icu_occupancy
                           + state.emergency_queue_length)

        tci        = (doctors * self._DOC_FACTOR + nurses * self._NURSE_FACTOR) / active
        raw_score  = min(1.0, tci)
        return ObjectiveScore(
            name=self.name,
            score=raw_score,
            weight=self.weight,
            detail={
                "throughput_capacity_index": round(tci, 3),
                "active_patients":           active,
                "doctors":                   int(doctors),
                "nurses":                    int(nurses),
            },
        )


# ── 3. Optimize ICU allocation ────────────────────────────────────────────────

class OptimizeICUAllocation(ObjectiveFunction):
    """
    Reward ICU utilisation close to the operational sweet spot (70–85 %).

    Too low → wasted capacity.
    Too high → saturation risk, no surge buffer.

    Score = 1 − |utilisation − TARGET| / TOLERANCE
    """
    name = "optimize_icu_allocation"
    weight = 0.20

    _TARGET      = 0.77   # 77 % utilisation is considered ideal
    _TOLERANCE   = 0.23   # score → 0 at ±23 % from target

    def score(self, solution: Solution, state: StateSnapshot) -> ObjectiveScore:
        icu_beds = max(1.0, solution.get("icu_beds_active", state.total_icu_beds))
        utilisation = state.icu_occupancy / icu_beds
        raw_score = max(0.0, 1.0 - abs(utilisation - self._TARGET) / self._TOLERANCE)
        return ObjectiveScore(
            name=self.name,
            score=raw_score,
            weight=self.weight,
            detail={
                "icu_beds_active": int(icu_beds),
                "icu_occupancy":   state.icu_occupancy,
                "utilisation":     round(utilisation, 4),
                "target":          self._TARGET,
            },
        )


# ── 4. Reduce overload ────────────────────────────────────────────────────────

class ReduceOverload(ObjectiveFunction):
    """
    Penalise solutions where workload ratios exceed safe thresholds.

    Uses a composite of doctor workload and nurse workload:
        overload = max(0, doctor_workload − DOC_THRESHOLD)
                 + max(0, nurse_workload  − NURSE_THRESHOLD)

    The higher the overload, the lower the score.
    """
    name = "reduce_overload"
    weight = 0.15

    _DOC_THRESHOLD   = 0.80   # > 80 % doctor utilisation → overload
    _NURSE_THRESHOLD = 0.75   # > 75 % nurse utilisation → overload

    def score(self, solution: Solution, state: StateSnapshot) -> ObjectiveScore:
        doctors = max(1.0, solution.get("doctors_on_duty", state.staff.total_doctors))
        nurses  = max(1.0, solution.get("nurses_on_duty",  state.staff.total_nurses))
        active_patients = state.regular_bed_occupancy + state.icu_occupancy

        doc_workload   = min(1.0, active_patients / doctors)
        nurse_workload = min(1.0, active_patients / nurses)

        doc_excess   = max(0.0, doc_workload   - self._DOC_THRESHOLD)
        nurse_excess = max(0.0, nurse_workload - self._NURSE_THRESHOLD)

        # Normalise: max possible excess ≈ 0.2 + 0.25 = 0.45
        overload_penalty = (doc_excess + nurse_excess) / 0.45
        raw_score = max(0.0, 1.0 - overload_penalty)

        return ObjectiveScore(
            name=self.name,
            score=raw_score,
            weight=self.weight,
            detail={
                "doctor_workload":   round(doc_workload, 4),
                "nurse_workload":    round(nurse_workload, 4),
                "doc_excess":        round(doc_excess, 4),
                "nurse_excess":      round(nurse_excess, 4),
                "doctors_evaluated": int(doctors),
                "nurses_evaluated":  int(nurses),
            },
        )


# ── 5. Improve resource utilisation ──────────────────────────────────────────

class ImproveResourceUtilization(ObjectiveFunction):
    """
    Reward efficient use of ward beds and equipment.

    Targets:
        • regular ward utilisation  → 72–85 %
        • equipment utilisation     → 60–80 %

    Penalty = |actual − target| / tolerance for each resource.
    """
    name = "improve_resource_utilization"
    weight = 0.10

    _WARD_TARGET      = 0.78
    _WARD_TOLERANCE   = 0.22
    _EQUIP_TARGET     = 0.70
    _EQUIP_TOLERANCE  = 0.30

    def score(self, solution: Solution, state: StateSnapshot) -> ObjectiveScore:
        reg_beds = max(1.0, solution.get("regular_beds_active", state.total_regular_beds))
        ward_util  = state.regular_bed_occupancy / reg_beds
        equip_util = state.equipment_utilization

        ward_score  = max(0.0, 1.0 - abs(ward_util  - self._WARD_TARGET)  / self._WARD_TOLERANCE)
        equip_score = max(0.0, 1.0 - abs(equip_util - self._EQUIP_TARGET) / self._EQUIP_TOLERANCE)

        raw_score = (ward_score + equip_score) / 2.0
        return ObjectiveScore(
            name=self.name,
            score=raw_score,
            weight=self.weight,
            detail={
                "ward_utilisation":       round(ward_util, 4),
                "equipment_utilisation":  round(equip_util, 4),
                "ward_score":             round(ward_score, 4),
                "equipment_score":        round(equip_score, 4),
                "regular_beds_evaluated": int(reg_beds),
            },
        )


# ── Objective registry ────────────────────────────────────────────────────────

OBJECTIVES: list[ObjectiveFunction] = [
    MinimizeWaitingTime(),
    MaximizeThroughput(),
    OptimizeICUAllocation(),
    ReduceOverload(),
    ImproveResourceUtilization(),
]
