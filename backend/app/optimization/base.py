"""
Optimization engine base types and abstract interface.

Design
──────
• A Solution is a dict mapping variable names to float values.
• Optimizers search the Solution space guided by a SolutionEvaluator.
• BaseOptimizer exposes one public method: optimize(state) → OptimizationResult.
• The entire interface is solver-agnostic; external solvers (scipy, OR-Tools,
  PuLP, Gurobi) can be integrated by subclassing BaseOptimizer.

Decision variables
──────────────────
The search space represents operational resource allocation:
  • doctors_on_duty    – how many doctors should be active
  • nurses_on_duty     – how many nurses should be active
  • icu_beds_active    – how many ICU beds to keep staffed
  • regular_beds_active – how many regular ward beds to keep open
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.simulation.state import StateSnapshot


# ── Decision variable ──────────────────────────────────────────────────────────

@dataclass
class OptimizationVariable:
    name: str
    min_value: float
    max_value: float
    step: float = 1.0
    integer: bool = True

    def clip(self, value: float) -> float:
        clipped = float(np.clip(value, self.min_value, self.max_value))
        if self.step > 0:
            clipped = round(clipped / self.step) * self.step
        return float(int(clipped)) if self.integer else clipped

    def random(self, rng: np.random.Generator) -> float:
        n_steps = int((self.max_value - self.min_value) / self.step)
        return self.clip(self.min_value + rng.integers(0, n_steps + 1) * self.step)

    @property
    def range(self) -> float:
        return self.max_value - self.min_value


Solution = dict[str, float]


def build_variables_from_state(state: StateSnapshot) -> list[OptimizationVariable]:
    """
    Build a contextual search space anchored to the current simulation state.
    Allows ±50 % headroom above current capacity and down to 1 minimum.
    """
    return [
        OptimizationVariable(
            "doctors_on_duty",
            min_value=max(1, state.staff.total_doctors - 5),
            max_value=state.staff.total_doctors + 15,
        ),
        OptimizationVariable(
            "nurses_on_duty",
            min_value=max(1, state.staff.total_nurses - 10),
            max_value=state.staff.total_nurses + 25,
        ),
        OptimizationVariable(
            "icu_beds_active",
            min_value=max(1, state.total_icu_beds - 5),
            max_value=state.total_icu_beds + 15,
        ),
        OptimizationVariable(
            "regular_beds_active",
            min_value=max(1, state.total_regular_beds - 20),
            max_value=state.total_regular_beds + 50,
        ),
    ]


def baseline_solution(state: StateSnapshot) -> Solution:
    """Return a solution matching the current simulation state exactly."""
    return {
        "doctors_on_duty":     float(state.staff.total_doctors),
        "nurses_on_duty":      float(state.staff.total_nurses),
        "icu_beds_active":     float(state.total_icu_beds),
        "regular_beds_active": float(state.total_regular_beds),
    }


# ── Result types ───────────────────────────────────────────────────────────────

@dataclass
class ObjectiveScore:
    name: str
    score: float          # 0.0 (worst) → 1.0 (best)
    weight: float
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResult:
    solution: Solution
    objective_scores: list[ObjectiveScore]
    composite_score: float
    feasible: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "solution":        self.solution,
            "composite_score": round(self.composite_score, 6),
            "feasible":        self.feasible,
            "objectives": [
                {
                    "name":   o.name,
                    "score":  round(o.score, 6),
                    "weight": o.weight,
                    "detail": o.detail,
                }
                for o in self.objective_scores
            ],
        }


@dataclass
class ConvergencePoint:
    iteration: int
    best_score: float
    mean_score: float


@dataclass
class OptimizationResult:
    run_id: str
    algorithm: str
    state_simulation_time: float
    best_solution: Solution
    best_score: float
    baseline_score: float
    improvement_pct: float
    evaluations: int
    iterations: int
    converged: bool
    convergence_history: list[ConvergencePoint]
    all_objectives: list[ObjectiveScore]
    wall_time_seconds: float
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id":                self.run_id,
            "algorithm":             self.algorithm,
            "state_simulation_time": self.state_simulation_time,
            "best_solution":         self.best_solution,
            "best_score":            round(self.best_score, 6),
            "baseline_score":        round(self.baseline_score, 6),
            "improvement_pct":       round(self.improvement_pct, 2),
            "evaluations":           self.evaluations,
            "iterations":            self.iterations,
            "converged":             self.converged,
            "convergence_history": [
                {
                    "iteration":  c.iteration,
                    "best_score": round(c.best_score, 6),
                    "mean_score": round(c.mean_score, 6),
                }
                for c in self.convergence_history
            ],
            "all_objectives": [
                {
                    "name":   o.name,
                    "score":  round(o.score, 6),
                    "weight": o.weight,
                    "detail": o.detail,
                }
                for o in self.all_objectives
            ],
            "wall_time_seconds": round(self.wall_time_seconds, 4),
            "recommendations":   self.recommendations,
        }


# ── Optimizer config ───────────────────────────────────────────────────────────

@dataclass
class OptimizerConfig:
    seed: int = 42
    max_iterations: int = 60
    convergence_tolerance: float = 1e-5
    convergence_patience: int = 10


# ── Abstract base ──────────────────────────────────────────────────────────────

class BaseOptimizer(ABC):
    algorithm_name: str = "base"

    def __init__(self, config: OptimizerConfig | None = None) -> None:
        self._config = config or OptimizerConfig()
        self._rng = np.random.default_rng(self._config.seed)
        self._eval_count: int = 0

    def optimize(
        self,
        state: StateSnapshot,
        variables: list[OptimizationVariable] | None = None,
    ) -> OptimizationResult:
        t0 = time.perf_counter()
        self._eval_count = 0
        self._rng = np.random.default_rng(self._config.seed)
        vars_ = variables or build_variables_from_state(state)

        result = self._search(state, vars_)
        result.wall_time_seconds = time.perf_counter() - t0
        result.evaluations = self._eval_count
        result.recommendations = _generate_recommendations(result.best_solution, state)
        return result

    @abstractmethod
    def _search(
        self,
        state: StateSnapshot,
        variables: list[OptimizationVariable],
    ) -> OptimizationResult:
        ...

    def _new_result(
        self,
        state: StateSnapshot,
        best: Solution,
        best_score: float,
        baseline_score: float,
        iterations: int,
        converged: bool,
        history: list[ConvergencePoint],
        objectives: list[ObjectiveScore],
    ) -> OptimizationResult:
        imp = (
            ((best_score - baseline_score) / max(1e-9, baseline_score)) * 100
            if baseline_score > 0
            else 0.0
        )
        return OptimizationResult(
            run_id=str(uuid.uuid4()),
            algorithm=self.algorithm_name,
            state_simulation_time=state.simulation_time,
            best_solution={k: float(v) for k, v in best.items()},
            best_score=best_score,
            baseline_score=baseline_score,
            improvement_pct=imp,
            evaluations=0,          # filled after _search returns
            iterations=iterations,
            converged=converged,
            convergence_history=history,
            all_objectives=objectives,
            wall_time_seconds=0.0,  # filled after _search returns
            recommendations=[],     # filled after _search returns
        )


def _generate_recommendations(sol: Solution, state: StateSnapshot) -> list[str]:
    recs: list[str] = []
    td = state.staff.total_doctors
    tn = state.staff.total_nurses
    ti = state.total_icu_beds
    tr = state.total_regular_beds

    doc_diff = int(sol.get("doctors_on_duty", td) - td)
    if doc_diff > 0:
        recs.append(f"Add {doc_diff} doctor(s) on duty – model predicts overload reduction.")
    elif doc_diff < 0:
        recs.append(f"Current doctor count may be reduced by {-doc_diff} without performance loss.")

    nur_diff = int(sol.get("nurses_on_duty", tn) - tn)
    if nur_diff > 0:
        recs.append(f"Schedule {nur_diff} additional nurse(s) for optimal ward coverage.")
    elif nur_diff < 0:
        recs.append(f"Nurse capacity can be reduced by {-nur_diff} at current patient load.")

    icu_diff = int(sol.get("icu_beds_active", ti) - ti)
    if icu_diff > 0:
        recs.append(f"Open {icu_diff} additional ICU bed(s) – current utilisation is high.")
    elif icu_diff < 0:
        recs.append(f"ICU is under-utilised; {-icu_diff} bed(s) can be temporarily repurposed.")

    reg_diff = int(sol.get("regular_beds_active", tr) - tr)
    if reg_diff > 0:
        recs.append(f"Activate {reg_diff} additional ward bed(s) to reduce congestion.")

    if state.emergency_queue_length > 5:
        recs.append(
            f"Emergency queue ({state.emergency_queue_length} patients) is elevated. "
            "Consider surge protocol activation."
        )

    if not recs:
        recs.append("Current allocation is near-optimal for the observed patient load.")

    return recs
