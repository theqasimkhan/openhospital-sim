"""
Tests for the simulation engine and simulation API endpoints.

These tests run entirely in-process using mocked DB/Redis dependencies.
The SimPy engine itself is tested directly (no HTTP) for unit-level coverage.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.simulation.config import SimulationConfig
from app.simulation.engine import EngineStatus, HospitalSimEngine
from app.simulation.events import SimEventType

# ═══════════════════════════════════════════════════════════════════════════════
# Engine unit tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestHospitalSimEngine:
    """Direct engine tests – no HTTP layer."""

    def _fresh_engine(self) -> HospitalSimEngine:
        return HospitalSimEngine()

    def test_initial_status_is_idle(self):
        engine = self._fresh_engine()
        assert engine.status == EngineStatus.IDLE

    def test_start_transitions_to_active(self):
        engine = self._fresh_engine()
        snapshot = engine.start(SimulationConfig(seed=42))
        assert engine.status == EngineStatus.ACTIVE
        assert snapshot is not None

    def test_start_when_already_active_raises(self):
        engine = self._fresh_engine()
        engine.start(SimulationConfig(seed=42))
        with pytest.raises(RuntimeError, match="already active"):
            engine.start(SimulationConfig(seed=99))

    def test_step_advances_simulation_time(self):
        engine = self._fresh_engine()
        engine.start(SimulationConfig(seed=42))
        assert engine.simulation_time == 0.0
        result = engine.step(step_minutes=60.0)
        assert result.simulation_time_after == pytest.approx(60.0)

    def test_step_returns_events(self):
        engine = self._fresh_engine()
        engine.start(SimulationConfig(seed=42))
        result = engine.step(step_minutes=120.0)
        assert isinstance(result.new_events, list)
        # With default config, patients should arrive within 2 hours
        assert result.new_events, "Expected at least one event in 2-hour step"

    def test_step_event_types_are_valid(self):
        engine = self._fresh_engine()
        engine.start(SimulationConfig(seed=42))
        result = engine.step(step_minutes=240.0)
        valid_types = {e.value for e in SimEventType}
        for evt in result.new_events:
            assert evt["event_type"] in valid_types

    def test_multiple_steps_increment_step_count(self):
        engine = self._fresh_engine()
        engine.start(SimulationConfig(seed=42))
        for i in range(5):
            result = engine.step(step_minutes=60.0)
            assert result.step_number == i + 1

    def test_reset_returns_to_idle(self):
        engine = self._fresh_engine()
        engine.start(SimulationConfig(seed=42))
        engine.step(step_minutes=60.0)
        snapshot = engine.reset()
        assert engine.status == EngineStatus.IDLE
        assert engine.simulation_time == 0.0
        assert snapshot is not None

    def test_step_on_idle_engine_raises(self):
        engine = self._fresh_engine()
        with pytest.raises(RuntimeError, match="Cannot step"):
            engine.step(step_minutes=60.0)

    def test_step_with_negative_minutes_raises(self):
        engine = self._fresh_engine()
        engine.start(SimulationConfig(seed=42))
        with pytest.raises(ValueError):
            engine.step(step_minutes=-1.0)

    def test_get_events_filter_by_type(self):
        engine = self._fresh_engine()
        engine.start(SimulationConfig(seed=42))
        engine.step(step_minutes=240.0)
        arrivals = engine.get_events(event_type="patient_arrived")
        assert all(e["event_type"] == "patient_arrived" for e in arrivals)

    def test_deterministic_with_same_seed(self):
        """Two engines with the same seed must produce identical event sequences."""
        def run(seed: int) -> list[str]:
            eng = HospitalSimEngine()
            eng.start(SimulationConfig(seed=seed))
            result = eng.step(step_minutes=120.0)
            return [e["event_type"] for e in result.new_events]

        assert run(42) == run(42)

    def test_different_seeds_produce_different_results(self):
        def run(seed: int) -> list[str]:
            eng = HospitalSimEngine()
            eng.start(SimulationConfig(seed=seed))
            result = eng.step(step_minutes=120.0)
            return [e["event_type"] for e in result.new_events]

        # Different seeds should produce different event sequences
        # (extremely unlikely to be identical with 2-hour simulation)
        assert run(1) != run(999)

    def test_state_snapshot_has_required_keys(self):
        engine = self._fresh_engine()
        engine.start(SimulationConfig(seed=42))
        engine.step(step_minutes=60.0)
        snapshot = engine.get_state_snapshot()
        d = snapshot.to_dict()
        assert d["icu"]["occupancy"] >= 0
        assert d["icu"]["total_beds"] >= 1
        assert d["regular_ward"]["occupancy"] >= 0
        assert d["regular_ward"]["total_beds"] >= 1
        assert "emergency_queue_length" in d
        assert "staff" in d
        assert isinstance(d["active_patients"], list)
        assert d["outcomes"]["discharged"] >= 0

    def test_config_is_accessible(self):
        engine = self._fresh_engine()
        cfg = SimulationConfig(seed=77, icu_beds=10)
        engine.start(cfg)
        config_dict = engine.get_config()
        assert config_dict["seed"] == 77
        assert config_dict["icu_beds"] == 10


# ═══════════════════════════════════════════════════════════════════════════════
# Simulation API endpoint tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestSimulationAPI:
    """Integration tests via the HTTP layer."""

    async def test_start_simulation(self, client: AsyncClient):
        r = await client.post(
            "/api/v1/simulation/reset"
        )
        r = await client.post(
            "/api/v1/simulation/start",
            json={"config": {"seed": 42}},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "started"
        assert body["engine_status"] == "active"
        assert "state" in body["data"]
        assert "run_id" in body["data"]

    async def test_step_simulation(self, client: AsyncClient):
        await client.post("/api/v1/simulation/reset")
        await client.post("/api/v1/simulation/start", json={"config": {"seed": 42}})
        r = await client.post(
            "/api/v1/simulation/step",
            json={"step_minutes": 60},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "stepped"
        assert "new_events" in body["data"]
        assert "agent_decisions" in body["data"]

    async def test_get_state(self, client: AsyncClient):
        await client.post("/api/v1/simulation/reset")
        await client.post("/api/v1/simulation/start", json={"config": {"seed": 42}})
        r = await client.get("/api/v1/simulation/state")
        assert r.status_code == 200
        body = r.json()
        assert "state" in body["data"]

    async def test_get_events(self, client: AsyncClient):
        await client.post("/api/v1/simulation/reset")
        await client.post("/api/v1/simulation/start", json={"config": {"seed": 42}})
        await client.post("/api/v1/simulation/step", json={"step_minutes": 120})
        r = await client.get("/api/v1/simulation/events")
        assert r.status_code == 200
        body = r.json()
        assert "events" in body["data"]
        assert isinstance(body["data"]["events"], list)

    async def test_get_events_filter_by_type(self, client: AsyncClient):
        await client.post("/api/v1/simulation/reset")
        await client.post("/api/v1/simulation/start", json={"config": {"seed": 42}})
        await client.post("/api/v1/simulation/step", json={"step_minutes": 240})
        r = await client.get(
            "/api/v1/simulation/events",
            params={"event_type": "patient_arrived"},
        )
        assert r.status_code == 200
        for evt in r.json()["data"]["events"]:
            assert evt["event_type"] == "patient_arrived"

    async def test_reset_simulation(self, client: AsyncClient):
        await client.post("/api/v1/simulation/start", json={"config": {"seed": 42}})
        r = await client.post("/api/v1/simulation/reset")
        assert r.status_code == 200
        assert r.json()["engine_status"] == "idle"

    async def test_step_without_start_returns_409(self, client: AsyncClient):
        await client.post("/api/v1/simulation/reset")
        r = await client.post("/api/v1/simulation/step", json={"step_minutes": 60})
        assert r.status_code == 409

    async def test_start_twice_returns_409(self, client: AsyncClient):
        await client.post("/api/v1/simulation/reset")
        await client.post("/api/v1/simulation/start", json={"config": {"seed": 42}})
        r = await client.post("/api/v1/simulation/start", json={"config": {"seed": 42}})
        assert r.status_code == 409
