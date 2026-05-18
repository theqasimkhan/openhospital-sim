"""
Optimization API endpoints.

Routes
──────
POST /optimization/run      – run an optimizer against the current simulation state
GET  /optimization/results  – retrieve the latest optimization result

The optimization algorithms are CPU-bound (pure Python + NumPy), so they run
synchronously under an asyncio.Lock to prevent concurrent modifications to
the shared result store.  Typical wall times are < 50 ms.
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Body, HTTPException, status

from app.core.logging import get_logger
from app.forecasting.schemas import OptimizationResultSchema, OptimizationRunRequest
from app.optimization.base import OptimizerConfig
from app.optimization.genetic_algorithm import GeneticOptimizer
from app.optimization.greedy import GreedyOptimizer
from app.optimization.particle_swarm import ParticleSwarmOptimizer
from app.simulation.engine import get_engine, get_engine_lock

router = APIRouter(tags=["optimization"])
logger = get_logger(__name__)

# ── Module-level result store ─────────────────────────────────────────────────
_latest_result: dict[str, Any] | None = None
_result_lock: asyncio.Lock = asyncio.Lock()

_OPTIMIZERS = {
    "greedy":  GreedyOptimizer,
    "genetic": GeneticOptimizer,
    "pso":     ParticleSwarmOptimizer,
}


# ── POST /optimization/run ────────────────────────────────────────────────────

@router.post(
    "/run",
    summary="Run a resource optimization pass",
    description=(
        "Runs the chosen optimizer against the **current simulation state snapshot**. "
        "Returns the best resource allocation found (doctors, nurses, ICU beds, "
        "ward beds) together with per-objective scores, convergence history, and "
        "plain-English recommendations.\n\n"
        "Algorithms:\n"
        "- `greedy` – fast coordinate descent with random restarts (< 5 ms)\n"
        "- `genetic` – real-valued genetic algorithm (< 20 ms for 60 generations)\n"
        "- `pso`    – particle swarm optimisation (< 20 ms for 60 iterations)"
    ),
    status_code=status.HTTP_200_OK,
)
async def run_optimization(
    body: OptimizationRunRequest = Body(default_factory=OptimizationRunRequest),
) -> dict[str, Any]:
    global _latest_result

    engine      = get_engine()
    engine_lock = get_engine_lock()

    # Fetch a snapshot without advancing the clock
    async with engine_lock:
        snapshot = engine.get_state_snapshot()

    if engine.status.value == "idle":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Simulation is not running. Call POST /simulation/start first.",
        )

    # Build and run the optimizer
    optimizer_cls = _OPTIMIZERS.get(body.algorithm)
    if optimizer_cls is None:  # should not happen with Pydantic Literal validation
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown algorithm '{body.algorithm}'. Choose greedy, genetic, or pso.",
        )

    cfg = OptimizerConfig(
        seed=body.seed,
        max_iterations=body.max_iterations,
    )
    optimizer = optimizer_cls(cfg)

    # Run synchronously (fast, < 50 ms) and store result under lock
    async with _result_lock:
        result = optimizer.optimize(snapshot)
        _latest_result = result.to_dict()

    logger.info(
        "optimization_run",
        algorithm=body.algorithm,
        best_score=result.best_score,
        baseline_score=result.baseline_score,
        improvement_pct=result.improvement_pct,
        evaluations=result.evaluations,
        iterations=result.iterations,
        wall_time_ms=round(result.wall_time_seconds * 1000, 2),
    )

    return {
        "status":  "ok",
        "message": f"Optimization complete ({body.algorithm}).",
        "result":  _latest_result,
    }


# ── GET /optimization/results ─────────────────────────────────────────────────

@router.get(
    "/results",
    summary="Latest optimization result",
    description=(
        "Returns the result from the most recent POST /optimization/run call. "
        "Returns 404 if no optimization has been run in this session."
    ),
    status_code=status.HTTP_200_OK,
)
async def get_optimization_results() -> dict[str, Any]:
    async with _result_lock:
        result = _latest_result

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No optimization result available. "
                "Run POST /optimization/run to generate one."
            ),
        )

    return {"status": "ok", "result": result}
