"""
GreedyOptimizer – coordinate descent with stochastic restarts.

Algorithm
─────────
1. Start from the baseline solution (current simulation state).
2. For each variable in round-robin order, try +step and −step.
3. Accept the move that produces the highest composite score.
4. Repeat until no variable improves the score (local minimum) or
   max_iterations is reached.
5. After convergence, perform a small number of random restarts to
   escape shallow local minima.

Complexity: O(max_iterations × n_variables × 2) evaluations.
Typical run: < 5 ms for the default 60-iteration budget.
"""
from __future__ import annotations

from app.optimization.base import (
    BaseOptimizer,
    ConvergencePoint,
    OptimizerConfig,
    OptimizationResult,
    OptimizationVariable,
    Solution,
    baseline_solution,
)
from app.optimization.evaluator import default_evaluator
from app.simulation.state import StateSnapshot


class GreedyOptimizer(BaseOptimizer):
    algorithm_name = "greedy"

    _NUM_RESTARTS = 3   # random restarts after local convergence

    def _search(
        self,
        state: StateSnapshot,
        variables: list[OptimizationVariable],
    ) -> OptimizationResult:
        evaluator = default_evaluator
        history: list[ConvergencePoint] = []

        # ── Baseline ───────────────────────────────────────────────────────────
        best = baseline_solution(state)
        baseline_eval = evaluator.evaluate(best, state)
        self._eval_count += 1
        best_score = baseline_eval.composite_score
        baseline_score = best_score

        # ── Coordinate descent ─────────────────────────────────────────────────
        iteration = 0
        patience_counter = 0

        for restart in range(1 + self._NUM_RESTARTS):
            if restart > 0:
                # Random restart: perturb the best solution found so far
                candidate = {
                    v.name: v.clip(best[v.name] + self._rng.normal(0, v.range * 0.15))
                    for v in variables
                }
                cand_eval = evaluator.evaluate(candidate, state)
                self._eval_count += 1
                if cand_eval.composite_score > best_score:
                    best = candidate
                    best_score = cand_eval.composite_score

            improved = True
            while improved and iteration < self._config.max_iterations:
                improved = False
                step_scores: list[float] = []

                for var in variables:
                    current_val = best.get(var.name, var.min_value)
                    for delta in (var.step, -var.step):
                        candidate = dict(best)
                        candidate[var.name] = var.clip(current_val + delta)
                        result = evaluator.evaluate(candidate, state)
                        self._eval_count += 1
                        step_scores.append(result.composite_score)

                        if result.composite_score > best_score + self._config.convergence_tolerance:
                            best = candidate
                            best_score = result.composite_score
                            improved = True

                mean_score = sum(step_scores) / max(1, len(step_scores))
                history.append(
                    ConvergencePoint(
                        iteration=iteration,
                        best_score=best_score,
                        mean_score=mean_score,
                    )
                )
                iteration += 1

                if not improved:
                    patience_counter += 1
                    if patience_counter >= self._config.convergence_patience:
                        break
                else:
                    patience_counter = 0

        final_eval = evaluator.evaluate(best, state)
        self._eval_count += 1

        return self._new_result(
            state=state,
            best=best,
            best_score=best_score,
            baseline_score=baseline_score,
            iterations=iteration,
            converged=patience_counter >= self._config.convergence_patience,
            history=history,
            objectives=final_eval.objective_scores,
        )
