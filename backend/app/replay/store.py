"""
ReplayStore – persists completed and in-progress simulation runs so they can be
replayed, inspected, and exported without re-running the engine.

Design
──────
• Every run is identified by a UUID run_id.
• A run captures: config, all events (ordered), per-step state snapshots, and
  all agent decisions produced during the run.
• Replay cursor: callers advance through a stored run one step at a time,
  receiving the same StepResult shape as the live engine.
• Export: runs can be serialised to JSON or NDJSON for downstream tooling.
• Storage: in-process dict (suitable for single-replica deployments).
  Can be replaced with a Redis-backed or PostgreSQL-backed store by swapping
  out the `_runs` dict for an async repository.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ── Run status ─────────────────────────────────────────────────────────────────

class RunStatus(str, Enum):
    RECORDING  = "recording"   # live run currently in progress
    COMPLETE   = "complete"    # engine reached COMPLETED or was reset
    ABORTED    = "aborted"     # reset before natural completion


# ── Stored step ────────────────────────────────────────────────────────────────

@dataclass
class StoredStep:
    step_number:           int
    simulation_time_before: float
    simulation_time_after:  float
    step_minutes:          float
    events:                list[dict[str, Any]]
    state_snapshot:        dict[str, Any]
    agent_decisions:       list[dict[str, Any]]
    wall_time:             float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_number":            self.step_number,
            "simulation_time_before": self.simulation_time_before,
            "simulation_time_after":  self.simulation_time_after,
            "step_minutes":           self.step_minutes,
            "events_count":           len(self.events),
            "events":                 self.events,
            "state_snapshot":         self.state_snapshot,
            "agent_decisions_count":  len(self.agent_decisions),
            "agent_decisions":        self.agent_decisions,
            "wall_time":              self.wall_time,
        }


# ── Simulation run record ──────────────────────────────────────────────────────

@dataclass
class SimulationRun:
    run_id:       str
    seed:         int
    config:       dict[str, Any]
    status:       RunStatus
    started_at:   float                  = field(default_factory=time.time)
    completed_at: float | None           = None
    steps:        list[StoredStep]       = field(default_factory=list)
    initial_state: dict[str, Any]        = field(default_factory=dict)
    tags:          list[str]             = field(default_factory=list)

    # ── Derived metrics ────────────────────────────────────────────────────────

    @property
    def total_events(self) -> int:
        return sum(len(s.events) for s in self.steps)

    @property
    def total_decisions(self) -> int:
        return sum(len(s.agent_decisions) for s in self.steps)

    @property
    def duration_simulated_minutes(self) -> float:
        if not self.steps:
            return 0.0
        return self.steps[-1].simulation_time_after

    @property
    def wall_duration_seconds(self) -> float | None:
        if self.completed_at is None:
            return None
        return round(self.completed_at - self.started_at, 3)

    def summary(self) -> dict[str, Any]:
        return {
            "run_id":                     self.run_id,
            "seed":                       self.seed,
            "status":                     self.status.value,
            "step_count":                 len(self.steps),
            "total_events":               self.total_events,
            "total_decisions":            self.total_decisions,
            "duration_simulated_minutes": self.duration_simulated_minutes,
            "wall_duration_seconds":      self.wall_duration_seconds,
            "started_at":                 self.started_at,
            "completed_at":               self.completed_at,
            "tags":                       self.tags,
        }

    def to_dict(self, include_steps: bool = True) -> dict[str, Any]:
        d = self.summary()
        d["config"] = self.config
        d["initial_state"] = self.initial_state
        if include_steps:
            d["steps"] = [s.to_dict() for s in self.steps]
        return d

    # ── Export helpers ─────────────────────────────────────────────────────────

    def export_events_json(self) -> str:
        """All events across all steps as a JSON array string."""
        all_events = []
        for step in self.steps:
            for evt in step.events:
                all_events.append({**evt, "_run_id": self.run_id})
        return json.dumps(all_events, indent=2)

    def export_events_ndjson(self) -> str:
        """All events as newline-delimited JSON (one event per line)."""
        lines = []
        for step in self.steps:
            for evt in step.events:
                lines.append(json.dumps({**evt, "_run_id": self.run_id}))
        return "\n".join(lines)

    def export_decisions_json(self) -> str:
        """All agent decisions across all steps as a JSON array string."""
        all_decisions = []
        for step in self.steps:
            for dec in step.agent_decisions:
                all_decisions.append({**dec, "_run_id": self.run_id})
        return json.dumps(all_decisions, indent=2)


# ── Replay cursor ──────────────────────────────────────────────────────────────

@dataclass
class ReplayCursor:
    """Tracks playback position for a replay session."""
    run_id:       str
    current_step: int = 0          # next step index to deliver

    @property
    def is_exhausted(self) -> bool:
        return False  # checked against run.steps length externally


# ── ReplayStore singleton ──────────────────────────────────────────────────────

class ReplayStore:
    """
    In-memory store for simulation runs and replay cursors.

    All public methods that mutate state are protected by a single asyncio.Lock
    (same concurrency model as the engine/registry).
    """

    MAX_RUNS = 50  # oldest runs are evicted when limit is reached

    def __init__(self) -> None:
        self._runs:    dict[str, SimulationRun] = {}
        self._cursors: dict[str, ReplayCursor]  = {}
        self._current_run_id: str | None        = None
        self._lock: asyncio.Lock                = asyncio.Lock()

    # ── Recording ──────────────────────────────────────────────────────────────

    def begin_run(self, config: dict[str, Any], initial_state: dict[str, Any]) -> str:
        """Called when simulation/start succeeds. Returns a new run_id."""
        run_id = str(uuid.uuid4())
        run = SimulationRun(
            run_id=run_id,
            seed=config.get("seed", 0),
            config=config,
            status=RunStatus.RECORDING,
            initial_state=initial_state,
        )
        self._evict_if_needed()
        self._runs[run_id] = run
        self._current_run_id = run_id
        return run_id

    def record_step(
        self,
        step_number: int,
        simulation_time_before: float,
        simulation_time_after: float,
        step_minutes: float,
        events: list[dict[str, Any]],
        state_snapshot: dict[str, Any],
        agent_decisions: list[dict[str, Any]],
    ) -> None:
        """Append a completed step to the currently-recording run."""
        if self._current_run_id is None:
            return
        run = self._runs.get(self._current_run_id)
        if run is None or run.status != RunStatus.RECORDING:
            return
        run.steps.append(StoredStep(
            step_number=step_number,
            simulation_time_before=simulation_time_before,
            simulation_time_after=simulation_time_after,
            step_minutes=step_minutes,
            events=events,
            state_snapshot=state_snapshot,
            agent_decisions=agent_decisions,
        ))

    def finish_run(self, completed: bool = True) -> None:
        """Mark the current recording run as complete or aborted."""
        if self._current_run_id is None:
            return
        run = self._runs.get(self._current_run_id)
        if run is None:
            return
        run.status = RunStatus.COMPLETE if completed else RunStatus.ABORTED
        run.completed_at = time.time()
        self._current_run_id = None

    # ── Replay ─────────────────────────────────────────────────────────────────

    def create_cursor(self, run_id: str) -> str:
        """Create a replay cursor for the given run. Returns a cursor_id."""
        if run_id not in self._runs:
            raise KeyError(f"Run '{run_id}' not found")
        cursor_id = str(uuid.uuid4())
        self._cursors[cursor_id] = ReplayCursor(run_id=run_id)
        return cursor_id

    def replay_step(self, cursor_id: str) -> dict[str, Any] | None:
        """
        Advance the cursor by one step and return the StoredStep dict.
        Returns None when playback is exhausted.
        """
        cursor = self._cursors.get(cursor_id)
        if cursor is None:
            raise KeyError(f"Cursor '{cursor_id}' not found")
        run = self._runs.get(cursor.run_id)
        if run is None:
            raise KeyError(f"Run '{cursor.run_id}' not found")
        if cursor.current_step >= len(run.steps):
            return None
        step = run.steps[cursor.current_step]
        cursor.current_step += 1
        return {
            **step.to_dict(),
            "cursor_position": cursor.current_step,
            "total_steps":     len(run.steps),
            "exhausted":       cursor.current_step >= len(run.steps),
        }

    def seek_cursor(self, cursor_id: str, step_index: int) -> None:
        """Jump the cursor to an arbitrary step index."""
        cursor = self._cursors.get(cursor_id)
        if cursor is None:
            raise KeyError(f"Cursor '{cursor_id}' not found")
        run = self._runs.get(cursor.run_id)
        if run is None:
            raise KeyError(f"Run '{cursor.run_id}' not found")
        if step_index < 0 or step_index > len(run.steps):
            raise ValueError(f"step_index {step_index} out of range [0, {len(run.steps)}]")
        cursor.current_step = step_index

    def close_cursor(self, cursor_id: str) -> None:
        self._cursors.pop(cursor_id, None)

    # ── Queries ────────────────────────────────────────────────────────────────

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return summaries of the most recent runs (newest first)."""
        runs = sorted(self._runs.values(), key=lambda r: r.started_at, reverse=True)
        return [r.summary() for r in runs[:limit]]

    def get_run(self, run_id: str) -> SimulationRun:
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(f"Run '{run_id}' not found")
        return run

    def get_current_run_id(self) -> str | None:
        return self._current_run_id

    # ── Eviction ───────────────────────────────────────────────────────────────

    def _evict_if_needed(self) -> None:
        if len(self._runs) >= self.MAX_RUNS:
            oldest = sorted(
                (r for r in self._runs.values() if r.run_id != self._current_run_id),
                key=lambda r: r.started_at,
            )
            for run in oldest[: len(self._runs) - self.MAX_RUNS + 1]:
                del self._runs[run.run_id]

    def get_lock(self) -> asyncio.Lock:
        return self._lock


# ── Global singleton ───────────────────────────────────────────────────────────

_store: ReplayStore = ReplayStore()


def get_replay_store() -> ReplayStore:
    return _store
