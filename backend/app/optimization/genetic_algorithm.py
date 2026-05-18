"""
GeneticOptimizer – real-valued genetic algorithm.

Algorithm
─────────
• Population initialised with the baseline + random perturbations.
• Selection: binary tournament (2 random candidates, best wins).
• Crossover: uniform crossover (each gene independently chosen from parent A or B).
• Mutation: Gaussian perturbation scaled to the variable range.
• Elitism: top-2 solutions are always preserved into the next generation.
• Early stopping: if best score does not improve for `convergence_patience` generations.

Parameters (OptimizerConfig extensions)
────────────────────────────────────────
POPULATION_SIZE  – number of candidate solutions per generation
CROSSOVER_RATE   – probability that two parents exchange genes
MUTATION_RATE    – per-gene probability of applying Gaussian noise
MUTATION_SIGMA   – std dev of mutation noise as fraction of variable range
ELITE_SIZE       – number of elites carried forward unchanged
"""
from __future__ import annotations

from app.optimization.base import (
    BaseOptimizer,
    ConvergencePoint,
    OptimizationResult,
    OptimizationVariable,
    Solution,
    baseline_solution,
)
from app.optimization.evaluator import default_evaluator
from app.simulation.state import StateSnapshot


class GeneticOptimizer(BaseOptimizer):
    algorithm_name = "genetic"

    POPULATION_SIZE = 24
    CROSSOVER_RATE  = 0.80
    MUTATION_RATE   = 0.20
    MUTATION_SIGMA  = 0.12   # fraction of variable range
    ELITE_SIZE      = 2

    def _search(
        self,
        state: StateSnapshot,
        variables: list[OptimizationVariable],
    ) -> OptimizationResult:
        evaluator = default_evaluator
        history: list[ConvergencePoint] = []

        # ── Initialise population ─────────────────────────────────────────────
        population = self._init_population(variables, state)
        scores = [evaluator.evaluate(p, state).composite_score for p in population]
        self._eval_count += len(population)

        baseline_score = evaluator.evaluate(baseline_solution(state), state).composite_score
        self._eval_count += 1

        best_idx   = int(max(range(len(scores)), key=lambda i: scores[i]))
        best       = dict(population[best_idx])
        best_score = scores[best_idx]

        patience = 0
        iteration = 0
        converged = False

        # ── Generational loop ─────────────────────────────────────────────────
        for gen in range(self._config.max_iterations):
            iteration = gen + 1

            # Sort by score (descending) for elitism
            ranked = sorted(zip(scores, population), key=lambda x: x[0], reverse=True)
            scores_sorted = [s for s, _ in ranked]
            pop_sorted = [p for _, p in ranked]

            new_pop: list[Solution] = list(pop_sorted[: self.ELITE_SIZE])

            # Fill remainder via selection → crossover → mutation
            while len(new_pop) < self.POPULATION_SIZE:
                parent_a = self._tournament_select(pop_sorted, scores_sorted)
                parent_b = self._tournament_select(pop_sorted, scores_sorted)
                child    = self._crossover(parent_a, parent_b, variables)
                child    = self._mutate(child, variables)
                new_pop.append(child)

            population = new_pop
            scores = [evaluator.evaluate(p, state).composite_score for p in population]
            self._eval_count += len(population)

            gen_best_idx = int(max(range(len(scores)), key=lambda i: scores[i]))
            gen_best     = scores[gen_best_idx]
            mean_score   = sum(scores) / len(scores)

            history.append(
                ConvergencePoint(iteration=iteration, best_score=gen_best, mean_score=mean_score)
            )

            if gen_best > best_score + self._config.convergence_tolerance:
                best       = dict(population[gen_best_idx])
                best_score = gen_best
                patience   = 0
            else:
                patience += 1

            if patience >= self._config.convergence_patience:
                converged = True
                break

        final_eval = evaluator.evaluate(best, state)
        self._eval_count += 1

        return self._new_result(
            state=state,
            best=best,
            best_score=best_score,
            baseline_score=baseline_score,
            iterations=iteration,
            converged=converged,
            history=history,
            objectives=final_eval.objective_scores,
        )

    # ── Operators ─────────────────────────────────────────────────────────────

    def _init_population(
        self,
        variables: list[OptimizationVariable],
        state: StateSnapshot,
    ) -> list[Solution]:
        base = baseline_solution(state)
        pop: list[Solution] = [base]
        while len(pop) < self.POPULATION_SIZE:
            candidate = {
                v.name: v.clip(
                    base[v.name] + self._rng.normal(0, v.range * self.MUTATION_SIGMA * 2)
                )
                for v in variables
            }
            pop.append(candidate)
        return pop

    def _tournament_select(
        self,
        population: list[Solution],
        scores: list[float],
        tournament_size: int = 3,
    ) -> Solution:
        indices = self._rng.choice(len(population), size=tournament_size, replace=False)
        winner = max(indices, key=lambda i: scores[i])
        return dict(population[winner])

    def _crossover(
        self,
        parent_a: Solution,
        parent_b: Solution,
        variables: list[OptimizationVariable],
    ) -> Solution:
        if self._rng.random() > self.CROSSOVER_RATE:
            return dict(parent_a)
        child: Solution = {}
        for v in variables:
            child[v.name] = (
                parent_a[v.name] if self._rng.random() < 0.5 else parent_b[v.name]
            )
        return child

    def _mutate(
        self,
        solution: Solution,
        variables: list[OptimizationVariable],
    ) -> Solution:
        mutated = dict(solution)
        for v in variables:
            if self._rng.random() < self.MUTATION_RATE:
                noise = self._rng.normal(0, v.range * self.MUTATION_SIGMA)
                mutated[v.name] = v.clip(solution[v.name] + noise)
        return mutated
