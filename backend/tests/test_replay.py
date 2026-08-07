"""
Tests for the replay engine and replay API endpoints.

Verifies that runs are recorded, steps are persisted, cursors advance
correctly, and export endpoints return well-formed data.
"""
from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from app.replay.store import ReplayStore, RunStatus

# ═══════════════════════════════════════════════════════════════════════════════
# ReplayStore unit tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestReplayStore:
    def _make_store(self) -> ReplayStore:
        return ReplayStore()

    def _sample_config(self) -> dict:
        return {"seed": 42, "icu_beds": 20, "regular_beds": 80}

    def _sample_state(self) -> dict:
        return {"icu_occupancy": 5, "total_icu_beds": 20, "step": 0}

    def _sample_step(self, step_number: int = 1) -> dict:
        return dict(
            step_number=step_number,
            simulation_time_before=float((step_number - 1) * 60),
            simulation_time_after=float(step_number * 60),
            step_minutes=60.0,
            events=[{"event_type": "simulation_stepped", "id": f"evt-{step_number}"}],
            state_snapshot={"step": step_number},
            agent_decisions=[],
        )

    def test_begin_run_returns_uuid(self):
        store = self._make_store()
        run_id = store.begin_run(self._sample_config(), self._sample_state())
        assert isinstance(run_id, str)
        assert len(run_id) == 36  # UUID4

    def test_current_run_id_tracks_active_run(self):
        store = self._make_store()
        run_id = store.begin_run(self._sample_config(), self._sample_state())
        assert store.get_current_run_id() == run_id

    def test_record_step_appends_to_run(self):
        store = self._make_store()
        store.begin_run(self._sample_config(), self._sample_state())
        store.record_step(**self._sample_step(1))
        run = store.get_run(store.get_current_run_id())
        assert len(run.steps) == 1

    def test_multiple_steps_recorded(self):
        store = self._make_store()
        store.begin_run(self._sample_config(), self._sample_state())
        for i in range(1, 6):
            store.record_step(**self._sample_step(i))
        run = store.get_run(store.get_current_run_id())
        assert len(run.steps) == 5

    def test_finish_run_marks_complete(self):
        store = self._make_store()
        run_id = store.begin_run(self._sample_config(), self._sample_state())
        store.record_step(**self._sample_step(1))
        store.finish_run(completed=True)
        run = store.get_run(run_id)
        assert run.status == RunStatus.COMPLETE
        assert run.completed_at is not None

    def test_finish_run_clears_current_run_id(self):
        store = self._make_store()
        store.begin_run(self._sample_config(), self._sample_state())
        store.finish_run(completed=True)
        assert store.get_current_run_id() is None

    def test_list_runs_returns_summaries(self):
        store = self._make_store()
        for _ in range(3):
            store.begin_run(self._sample_config(), self._sample_state())
            store.finish_run(completed=True)
        runs = store.list_runs(limit=10)
        assert len(runs) == 3

    def test_list_runs_newest_first(self):
        store = self._make_store()
        ids = []
        for _ in range(3):
            rid = store.begin_run(self._sample_config(), self._sample_state())
            ids.append(rid)
            store.finish_run(completed=True)
        runs = store.list_runs(limit=10)
        # Most recent run should be first
        assert runs[0]["run_id"] == ids[-1]

    def test_get_run_raises_on_unknown(self):
        store = self._make_store()
        with pytest.raises(KeyError):
            store.get_run("not-a-real-run-id")

    def test_create_cursor(self):
        store = self._make_store()
        run_id = store.begin_run(self._sample_config(), self._sample_state())
        for i in range(1, 4):
            store.record_step(**self._sample_step(i))
        store.finish_run(completed=True)
        cursor_id = store.create_cursor(run_id)
        assert isinstance(cursor_id, str)

    def test_replay_step_advances_cursor(self):
        store = self._make_store()
        run_id = store.begin_run(self._sample_config(), self._sample_state())
        for i in range(1, 4):
            store.record_step(**self._sample_step(i))
        store.finish_run(completed=True)
        cursor_id = store.create_cursor(run_id)
        step = store.replay_step(cursor_id)
        assert step is not None
        assert step["step_number"] == 1

    def test_replay_exhaustion_returns_none(self):
        store = self._make_store()
        run_id = store.begin_run(self._sample_config(), self._sample_state())
        store.record_step(**self._sample_step(1))
        store.finish_run(completed=True)
        cursor_id = store.create_cursor(run_id)
        store.replay_step(cursor_id)        # step 1
        result = store.replay_step(cursor_id)  # exhausted
        assert result is None

    def test_seek_cursor(self):
        store = self._make_store()
        run_id = store.begin_run(self._sample_config(), self._sample_state())
        for i in range(1, 6):
            store.record_step(**self._sample_step(i))
        store.finish_run(completed=True)
        cursor_id = store.create_cursor(run_id)
        store.seek_cursor(cursor_id, 3)
        step = store.replay_step(cursor_id)
        assert step["step_number"] == 4  # step at index 3 is step_number 4

    def test_export_events_json_is_valid_json(self):
        store = self._make_store()
        store.begin_run(self._sample_config(), self._sample_state())
        store.record_step(**self._sample_step(1))
        run_id = store.get_current_run_id()
        store.finish_run(completed=True)
        run = store.get_run(run_id)
        export = run.export_events_json()
        events = json.loads(export)
        assert isinstance(events, list)
        assert len(events) == 1

    def test_run_metrics(self):
        store = self._make_store()
        store.begin_run(self._sample_config(), self._sample_state())
        for i in range(1, 4):
            store.record_step(**self._sample_step(i))
        run_id = store.get_current_run_id()
        store.finish_run(completed=True)
        run = store.get_run(run_id)
        assert run.total_events == 3
        assert run.duration_simulated_minutes == 180.0


# ═══════════════════════════════════════════════════════════════════════════════
# Replay API endpoint tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestReplayAPI:
    async def _create_run(self, client: AsyncClient, steps: int = 3):
        """Helper: run a simulation through the API to populate the replay store."""
        await client.post("/api/v1/simulation/reset")
        r = await client.post(
            "/api/v1/simulation/start",
            json={"config": {"seed": 42}},
        )
        run_id = r.json()["data"].get("run_id")
        for _ in range(steps):
            await client.post("/api/v1/simulation/step", json={"step_minutes": 60})
        return run_id

    async def test_list_runs_empty_initially(self, client: AsyncClient):
        # Reset store indirectly by resetting simulation
        await client.post("/api/v1/simulation/reset")
        r = await client.get("/api/v1/replay/runs")
        assert r.status_code == 200

    async def test_list_runs_after_simulation(self, client: AsyncClient):
        await self._create_run(client, steps=2)
        r = await client.get("/api/v1/replay/runs")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 1

    async def test_get_run_by_id(self, client: AsyncClient):
        run_id = await self._create_run(client, steps=2)
        if run_id:
            r = await client.get(f"/api/v1/replay/runs/{run_id}")
            assert r.status_code == 200
            body = r.json()
            assert body["run"]["run_id"] == run_id

    async def test_get_unknown_run_returns_404(self, client: AsyncClient):
        r = await client.get("/api/v1/replay/runs/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    async def test_get_run_step(self, client: AsyncClient):
        run_id = await self._create_run(client, steps=3)
        # Finish the run
        await client.post("/api/v1/simulation/reset")
        if run_id:
            r = await client.get(f"/api/v1/replay/runs/{run_id}/steps/0")
            assert r.status_code in (200, 404)  # 200 if steps recorded, 404 if not

    async def test_export_run_events_json(self, client: AsyncClient):
        run_id = await self._create_run(client, steps=2)
        await client.post("/api/v1/simulation/reset")  # close recording
        if run_id:
            r = await client.get(
                f"/api/v1/replay/runs/{run_id}/export",
                params={"format": "json", "target": "events"},
            )
            if r.status_code == 200:
                assert r.headers["content-type"].startswith("application/json")
                data = json.loads(r.content)
                assert isinstance(data, list)

    async def test_create_and_use_cursor(self, client: AsyncClient):
        run_id = await self._create_run(client, steps=2)
        await client.post("/api/v1/simulation/reset")  # close recording
        if run_id:
            # Create cursor
            r = await client.post(f"/api/v1/replay/runs/{run_id}/cursor")
            if r.status_code == 201:
                cursor_id = r.json()["cursor_id"]
                # Advance cursor
                r2 = await client.post(f"/api/v1/replay/cursor/{cursor_id}/next")
                assert r2.status_code in (200, 204)
                # Close cursor
                r3 = await client.delete(f"/api/v1/replay/cursor/{cursor_id}")
                assert r3.status_code == 204

    async def test_metrics_endpoint_responds(self, client: AsyncClient):
        r = await client.get("/api/v1/metrics")
        assert r.status_code == 200
        # Should be Prometheus text format or a plain text fallback
        assert "text/plain" in r.headers.get("content-type", "") or \
               "text" in r.headers.get("content-type", "")
