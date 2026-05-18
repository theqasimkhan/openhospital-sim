"""
SolutionEvaluator – scores a candidate Solution against a StateSnapshot.

The composite score is the weighted average of all objective scores.
Weights are normalised internally so they always sum to 1.0.
"""
from __future__ import annotations

from app.optimization.base import EvaluationResult, ObjectiveScore, Solution
from app.optimization.objectives import OBJECTIVES, ObjectiveFunction
from app.simulation.state import StateSnapshot


class SolutionEvaluator:
    """
    Stateless evaluator.  Thread-safe: no mutable state after construction.

    Usage:
        evaluator = SolutionEvaluator()
        result = evaluator.evaluate(solution, state)
        print(result.composite_score)   # 0.0 – 1.0
    """

    def __init__(
        self,
        objectives: list[ObjectiveFunction] | None = None,
    ) -> None:
        self._objectives = objectives or OBJECTIVES
        total_weight = sum(o.weight for o in self._objectives)
        # Normalise weights so they always sum to 1.0
        self._norm_weights = {
            o.name: o.weight / total_weight for o in self._objectives
        }

    def evaluate(
        self,
        solution: Solution,
        state: StateSnapshot,
    ) -> EvaluationResult:
        """
        Score a solution.  Returns an EvaluationResult with per-objective
        breakdowns and a composite weighted score.
        """
        scores: list[ObjectiveScore] = []
        composite = 0.0
        feasible = _is_feasible(solution, state)

        for obj in self._objectives:
            obj_score = obj.score(solution, state)
            norm_w = self._norm_weights[obj.name]
            composite += obj_score.score * norm_w
            scores.append(
                ObjectiveScore(
                    name=obj_score.name,
                    score=obj_score.score,
                    weight=norm_w,
                    detail=obj_score.detail,
                )
            )

        # Infeasible solutions get a hard penalty
        if not feasible:
            composite *= 0.1

        return EvaluationResult(
            solution=solution,
            objective_scores=scores,
            composite_score=composite,
            feasible=feasible,
        )

    def evaluate_many(
        self,
        solutions: list[Solution],
        state: StateSnapshot,
    ) -> list[EvaluationResult]:
        return [self.evaluate(s, state) for s in solutions]


def _is_feasible(solution: Solution, state: StateSnapshot) -> bool:
    """
    A solution is infeasible if it violates hard constraints:
      • Cannot activate more beds than the physical ceiling (×2 surge cap)
      • Cannot schedule zero or negative staff
    """
    max_icu   = state.total_icu_beds * 2
    max_reg   = state.total_regular_beds * 2

    if solution.get("icu_beds_active", 1) < 1:
        return False
    if solution.get("regular_beds_active", 1) < 1:
        return False
    if solution.get("doctors_on_duty", 1) < 1:
        return False
    if solution.get("nurses_on_duty", 1) < 1:
        return False
    if solution.get("icu_beds_active", 0) > max_icu:
        return False
    if solution.get("regular_beds_active", 0) > max_reg:
        return False
    return True


# Module-level shared evaluator (stateless, safe to reuse)
default_evaluator = SolutionEvaluator()
