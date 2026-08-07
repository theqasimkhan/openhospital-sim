"""
Tests for the multi-agent layer.

Verifies that agents correctly process simulation events, emit structured
decisions, and expose consistent state via the API.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.agents.base import AgentStatus, AgentType, DecisionPriority
from app.agents.registry import AgentRegistry
from app.simulation.config import SimulationConfig
from app.simulation.engine import HospitalSimEngine

# ═══════════════════════════════════════════════════════════════════════════════
# Registry unit tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentRegistry:
    def _run_simulation(self, steps: int = 4, step_minutes: float = 60.0):
        """Helper: start engine + registry, run N steps, return registry."""
        engine = HospitalSimEngine()
        registry = AgentRegistry()
        cfg = SimulationConfig(seed=42)
        snapshot = engine.start(cfg)
        initial_events = engine.get_raw_events(since_index=0)
        registry.process_events(initial_events, snapshot)
        for _ in range(steps):
            events_before = engine.event_count
            engine.step(step_minutes=step_minutes)
            new_events = engine.get_raw_events(since_index=events_before)
            snapshot = engine.get_state_snapshot()
            registry.process_events(new_events, snapshot)
        return registry

    def test_registry_has_seven_agents(self):
        registry = AgentRegistry()
        agents = registry.list_agents()
        assert len(agents) == 7

    def test_all_agent_types_present(self):
        registry = AgentRegistry()
        agent_types = {a["agent_type"] for a in registry.list_agents()}
        for expected_type in AgentType:
            assert expected_type.value in agent_types

    def test_agents_process_events_and_emit_decisions(self):
        registry = self._run_simulation(steps=4)
        decisions = registry.get_recent_decisions(limit=500)
        assert len(decisions) > 0, "Expected agents to emit decisions after 4 steps"

    def test_decision_log_entries_have_required_fields(self):
        registry = self._run_simulation(steps=2)
        decisions = registry.get_recent_decisions(limit=50)
        for dec in decisions:
            for field in ["id", "agent_id", "decision", "reasoning", "priority", "confidence"]:
                assert field in dec, f"Missing field: {field}"

    def test_confidence_is_valid_range(self):
        registry = self._run_simulation(steps=3)
        for dec in registry.get_recent_decisions(limit=100):
            assert 0.0 <= dec["confidence"] <= 1.0

    def test_priority_values_are_valid(self):
        registry = self._run_simulation(steps=3)
        valid = {p.value for p in DecisionPriority}
        for dec in registry.get_recent_decisions(limit=100):
            assert dec["priority"] in valid

    def test_filter_decisions_by_agent_id(self):
        registry = self._run_simulation(steps=4)
        decisions = registry.get_recent_decisions(agent_id="icu-manager-001", limit=100)
        for dec in decisions:
            assert dec["agent_id"] == "icu-manager-001"

    def test_filter_decisions_by_priority(self):
        registry = self._run_simulation(steps=6)
        decisions = registry.get_recent_decisions(priority="high", limit=100)
        for dec in decisions:
            assert dec["priority"] == DecisionPriority.HIGH.value

    def test_reset_clears_decisions(self):
        registry = self._run_simulation(steps=4)
        assert len(registry.get_recent_decisions(limit=500)) > 0
        registry.reset()
        # After reset, each agent's decision log should be empty
        for agent in registry.list_agents():
            assert agent["decisions_made"] == 0

    def test_agent_status_transitions_to_active(self):
        registry = self._run_simulation(steps=1)
        for agent in registry.list_agents():
            assert agent["status"] != AgentStatus.IDLE.value, (
                f"Agent {agent['agent_id']} should be active after processing events"
            )

    def test_forecasting_agent_time_series(self):
        registry = self._run_simulation(steps=5)
        ts = registry.get_forecast_time_series()
        assert isinstance(ts, list)
        assert len(ts) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Agents API endpoint tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestAgentsAPI:
    async def _setup_run(self, client: AsyncClient, steps: int = 3):
        await client.post("/api/v1/simulation/reset")
        await client.post("/api/v1/simulation/start", json={"config": {"seed": 42}})
        for _ in range(steps):
            await client.post("/api/v1/simulation/step", json={"step_minutes": 60})

    async def test_list_agents(self, client: AsyncClient):
        await self._setup_run(client)
        r = await client.get("/api/v1/agents")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert len(body["data"]["agents"]) == 7

    async def test_get_agent_by_id(self, client: AsyncClient):
        await self._setup_run(client)
        r = await client.get("/api/v1/agents/icu-manager-001")
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["agent_id"] == "icu-manager-001"

    async def test_get_unknown_agent_returns_404(self, client: AsyncClient):
        r = await client.get("/api/v1/agents/nonexistent-agent")
        assert r.status_code == 404

    async def test_get_agent_logs(self, client: AsyncClient):
        await self._setup_run(client, steps=4)
        r = await client.get("/api/v1/agents/icu-manager-001/logs")
        assert r.status_code == 200
        body = r.json()
        assert "logs" in body["data"]
        assert isinstance(body["data"]["logs"], list)

    async def test_get_recent_decisions(self, client: AsyncClient):
        await self._setup_run(client, steps=4)
        r = await client.get("/api/v1/agents/decisions/recent?limit=20")
        assert r.status_code == 200
        body = r.json()
        assert "decisions" in body["data"]

    async def test_registry_metadata(self, client: AsyncClient):
        await self._setup_run(client)
        r = await client.get("/api/v1/agents/registry")
        assert r.status_code == 200
        body = r.json()
        assert "total_events_processed" in body["data"]
        assert "total_decisions" in body["data"]

    async def test_forecast_timeseries(self, client: AsyncClient):
        await self._setup_run(client, steps=5)
        r = await client.get("/api/v1/agents/forecast/timeseries")
        assert r.status_code == 200
        body = r.json()
        assert "timeseries" in body["data"]
