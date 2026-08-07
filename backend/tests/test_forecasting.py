"""
Tests for the forecasting pipeline and optimization engine.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.agents.registry import AgentRegistry
from app.simulation.config import SimulationConfig
from app.simulation.engine import HospitalSimEngine

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _run_simulation_and_get_registry(steps: int = 8) -> tuple[HospitalSimEngine, AgentRegistry]:
    engine = HospitalSimEngine()
    registry = AgentRegistry()
    cfg = SimulationConfig(seed=42)
    snapshot = engine.start(cfg)
    registry.process_events(engine.get_raw_events(since_index=0), snapshot)
    for _ in range(steps):
        events_before = engine.event_count
        engine.step(step_minutes=60.0)
        new_events = engine.get_raw_events(since_index=events_before)
        snapshot = engine.get_state_snapshot()
        registry.process_events(new_events, snapshot)
    return engine, registry


# ═══════════════════════════════════════════════════════════════════════════════
# Forecasting API endpoint tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestForecastingAPI:
    async def _setup_steps(self, client: AsyncClient, steps: int = 8):
        await client.post("/api/v1/simulation/reset")
        await client.post("/api/v1/simulation/start", json={"config": {"seed": 42}})
        for _ in range(steps):
            await client.post("/api/v1/simulation/step", json={"step_minutes": 60})

    async def test_run_forecasting(self, client: AsyncClient):
        await self._setup_steps(client)
        r = await client.post(
            "/api/v1/forecasting/run",
            json={"horizon_steps": 6},
        )
        assert r.status_code == 200
        body = r.json()
        assert "forecast" in body or "bundle" in body or "status" in body

    async def test_get_latest_forecast(self, client: AsyncClient):
        await self._setup_steps(client)
        await client.post("/api/v1/forecasting/run", json={"horizon_steps": 6})
        r = await client.get("/api/v1/forecasting/latest")
        assert r.status_code in (200, 404)  # 404 if no forecast run yet

    async def test_surge_risk_endpoint(self, client: AsyncClient):
        await self._setup_steps(client, steps=4)
        r = await client.get("/api/v1/forecasting/surge-risk")
        assert r.status_code == 200
        body = r.json()
        assert "risk_level" in body or "surge_risk" in body or "data" in body


# ═══════════════════════════════════════════════════════════════════════════════
# Optimization API endpoint tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestOptimizationAPI:
    async def _setup_steps(self, client: AsyncClient, steps: int = 4):
        await client.post("/api/v1/simulation/reset")
        await client.post("/api/v1/simulation/start", json={"config": {"seed": 42}})
        for _ in range(steps):
            await client.post("/api/v1/simulation/step", json={"step_minutes": 60})

    async def test_run_greedy_optimizer(self, client: AsyncClient):
        await self._setup_steps(client)
        r = await client.post(
            "/api/v1/optimization/run",
            json={"algorithm": "greedy"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "best_score" in body or "result" in body or "data" in body

    async def test_run_genetic_optimizer(self, client: AsyncClient):
        await self._setup_steps(client)
        r = await client.post(
            "/api/v1/optimization/run",
            json={"algorithm": "genetic", "max_iterations": 20},
        )
        assert r.status_code == 200

    async def test_run_pso_optimizer(self, client: AsyncClient):
        await self._setup_steps(client)
        r = await client.post(
            "/api/v1/optimization/run",
            json={"algorithm": "pso", "max_iterations": 20},
        )
        assert r.status_code == 200

    async def test_get_latest_optimization_result(self, client: AsyncClient):
        await self._setup_steps(client)
        await client.post("/api/v1/optimization/run", json={"algorithm": "greedy"})
        r = await client.get("/api/v1/optimization/results")
        assert r.status_code in (200, 404)

    async def test_invalid_algorithm_returns_error(self, client: AsyncClient):
        await self._setup_steps(client)
        r = await client.post(
            "/api/v1/optimization/run",
            json={"algorithm": "not_a_real_algo"},
        )
        assert r.status_code in (400, 422, 500)
