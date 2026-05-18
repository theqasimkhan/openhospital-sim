"""
ParticleSwarmOptimizer – continuous PSO with linearly decaying inertia.

Algorithm (standard PSO – Kennedy & Eberhart, 1995)
────────────────────────────────────────────────────
• N particles, each with a position (Solution) and velocity (dict[str, float]).
• Each particle tracks its personal best (pbest) and the global best (gbest).
• Velocity update:
    v_new = w·v + c1·r1·(pbest − x) + c2·r2·(gbest − x)
• Position update:  x_new = x + v_new
• Inertia weight w decays linearly from W_MAX to W_MIN over all iterations.
• Velocity is clamped to ±VMAX_FRACTION of the variable range to prevent
  particles from overshooting the bounds.

This implementation is fully compatible with the BaseOptimizer interface
and matches the Greedy / Genetic API exactly.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

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


@dataclass
class Particle:
    position:      Solution
    velocity:      dict[str, float]
    pbest:         Solution
    pbest_score:   float
    score:         float = 0.0


class ParticleSwarmOptimizer(BaseOptimizer):
    algorithm_name = "pso"

    N_PARTICLES    = 24
    W_MAX          = 0.90   # initial inertia weight
    W_MIN          = 0.30   # final inertia weight (linearly decayed)
    C1             = 1.50   # cognitive (personal best) weight
    C2             = 1.50   # social (global best) weight
    VMAX_FRACTION  = 0.25   # max velocity as fraction of variable range

    def _search(
        self,
        state: StateSnapshot,
        variables: list[OptimizationVariable],
    ) -> OptimizationResult:
        evaluator = default_evaluator
        history: list[ConvergencePoint] = []

        baseline_score = evaluator.evaluate(baseline_solution(state), state).composite_score
        self._eval_count += 1

        # ── Initialise swarm ───────────────────────────────────────────────────
        swarm = self._init_swarm(variables, state, evaluator)
        self._eval_count += self.N_PARTICLES

        gbest       = max(swarm, key=lambda p: p.pbest_score)
        gbest_pos   = dict(gbest.pbest)
        gbest_score = gbest.pbest_score

        vmax = {v.name: v.range * self.VMAX_FRACTION for v in variables}

        iteration = 0
        converged = False
        patience  = 0

        # ── Iteration loop ─────────────────────────────────────────────────────
        for it in range(self._config.max_iterations):
            iteration = it + 1
            w = self.W_MAX - (self.W_MAX - self.W_MIN) * (it / max(1, self._config.max_iterations - 1))

            iter_scores: list[float] = []

            for particle in swarm:
                r1 = self._rng.random(len(variables))
                r2 = self._rng.random(len(variables))

                new_vel: dict[str, float] = {}
                new_pos: Solution = {}

                for idx, var in enumerate(variables):
                    v_i = (
                        w * particle.velocity[var.name]
                        + self.C1 * r1[idx] * (particle.pbest[var.name] - particle.position[var.name])
                        + self.C2 * r2[idx] * (gbest_pos[var.name]       - particle.position[var.name])
                    )
                    # Velocity clamping
                    v_i = float(np.clip(v_i, -vmax[var.name], vmax[var.name]))
                    new_vel[var.name] = v_i
                    new_pos[var.name] = var.clip(particle.position[var.name] + v_i)

                particle.velocity = new_vel
                particle.position = new_pos

                new_score = evaluator.evaluate(new_pos, state).composite_score
                self._eval_count += 1
                particle.score = new_score
                iter_scores.append(new_score)

                if new_score > particle.pbest_score:
                    particle.pbest       = dict(new_pos)
                    particle.pbest_score = new_score

                if new_score > gbest_score:
                    gbest_pos   = dict(new_pos)
                    gbest_score = new_score

            mean_score = sum(iter_scores) / max(1, len(iter_scores))
            history.append(
                ConvergencePoint(iteration=iteration, best_score=gbest_score, mean_score=mean_score)
            )

            if iteration > 1:
                prev = history[-2].best_score
                if gbest_score - prev < self._config.convergence_tolerance:
                    patience += 1
                else:
                    patience = 0

            if patience >= self._config.convergence_patience:
                converged = True
                break

        final_eval = evaluator.evaluate(gbest_pos, state)
        self._eval_count += 1

        return self._new_result(
            state=state,
            best=gbest_pos,
            best_score=gbest_score,
            baseline_score=baseline_score,
            iterations=iteration,
            converged=converged,
            history=history,
            objectives=final_eval.objective_scores,
        )

    # ── Swarm initialisation ──────────────────────────────────────────────────

    def _init_swarm(
        self,
        variables: list[OptimizationVariable],
        state: StateSnapshot,
        evaluator,
    ) -> list[Particle]:
        base = baseline_solution(state)
        particles: list[Particle] = []

        for i in range(self.N_PARTICLES):
            if i == 0:
                pos = dict(base)
            else:
                pos = {v.name: v.random(self._rng) for v in variables}

            vel = {
                v.name: float(self._rng.uniform(-v.range * 0.1, v.range * 0.1))
                for v in variables
            }
            score = evaluator.evaluate(pos, state).composite_score
            particles.append(
                Particle(
                    position=pos,
                    velocity=vel,
                    pbest=dict(pos),
                    pbest_score=score,
                    score=score,
                )
            )

        return particles
