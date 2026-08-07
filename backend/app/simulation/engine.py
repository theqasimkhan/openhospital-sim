"""
HospitalSimEngine – orchestrates the SimPy discrete-event simulation.

Design
──────
• Single global engine instance per process (thread-safe via asyncio.Lock).
• Deterministic: seeded NumPy Generator, reproducible across identical configs.
• Step-based API: callers advance the clock by N simulated minutes per call.
• Snapshot-capable: every step saves a StateSnapshot for inspection / rollback.
• Replay-ready: EventLog is append-only; replaying from event 0 with the same
  seed recreates the identical simulation trajectory.

Lifecycle:
  IDLE  ──start()──►  ACTIVE  ──step()──►  ACTIVE (loop)
  ACTIVE ──reset()──►  IDLE
  ACTIVE ──auto──►  COMPLETED  (if max_simulation_time reached)
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
import simpy

from app.simulation.config import DEFAULT_CONFIG, SimulationConfig
from app.simulation.events import EventLog, SimEventType
from app.simulation.patient_flow import (
    emergency_spike_process,
    patient_arrival_process,
    staff_shortage_process,
)
from app.simulation.resources import HospitalResources
from app.simulation.state import HospitalStateManager, StateSnapshot

# ── Engine status ──────────────────────────────────────────────────────────────

class EngineStatus(str, Enum):
    IDLE      = "idle"
    ACTIVE    = "active"
    COMPLETED = "completed"


# ── Step result ────────────────────────────────────────────────────────────────

@dataclass
class StepResult:
    step_number:        int
    simulation_time_before: float
    simulation_time_after:  float
    step_minutes:       float
    new_events:         list[dict[str, Any]]
    state_snapshot:     dict[str, Any]
    status:             EngineStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_number":            self.step_number,
            "simulation_time_before": self.simulation_time_before,
            "simulation_time_after":  self.simulation_time_after,
            "step_minutes":           self.step_minutes,
            "new_events_count":       len(self.new_events),
            "new_events":             self.new_events,
            "state":                  self.state_snapshot,
            "status":                 self.status.value,
        }


# ── Engine ─────────────────────────────────────────────────────────────────────

class HospitalSimEngine:
    """
    Core discrete-event simulation engine wrapping SimPy.

    Public methods are synchronous (SimPy is synchronous).
    The FastAPI layer protects concurrent access with an asyncio.Lock.
    """

    def __init__(self) -> None:
        self._config: SimulationConfig = DEFAULT_CONFIG
        self._status: EngineStatus = EngineStatus.IDLE
        self._env: simpy.Environment | None = None
        self._resources: HospitalResources | None = None
        self._state: HospitalStateManager = HospitalStateManager(DEFAULT_CONFIG)
        self._event_log: EventLog = EventLog()
        self._rng: np.random.Generator | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self, config: SimulationConfig | None = None) -> StateSnapshot:
        """
        Initialise and start the simulation.
        Raises RuntimeError if already active (call reset() first).
        """
        if self._status == EngineStatus.ACTIVE:
            raise RuntimeError(
                "Simulation is already active. Call /simulation/reset before starting again."
            )

        self._config = config or DEFAULT_CONFIG
        self._config.validate()

        # Build fresh SimPy environment and seeded RNG
        self._env = simpy.Environment()
        self._rng = np.random.default_rng(self._config.seed)
        self._state = HospitalStateManager(self._config)
        self._event_log = EventLog()
        self._resources = HospitalResources(self._env, self._config)

        # Register background processes
        self._env.process(
            patient_arrival_process(
                self._env, self._state, self._resources,
                self._event_log, self._config, self._rng,
            )
        )
        self._env.process(
            emergency_spike_process(
                self._env, self._state, self._resources,
                self._event_log, self._config, self._rng,
            )
        )
        self._env.process(
            staff_shortage_process(
                self._env, self._state, self._resources,
                self._event_log, self._config, self._rng,
            )
        )

        self._status = EngineStatus.ACTIVE
        self._event_log.record(0.0, SimEventType.SIMULATION_STARTED, seed=self._config.seed)

        snapshot = self._state.snapshot(self._event_log.count)
        return snapshot

    def step(self, step_minutes: float | None = None) -> StepResult:
        """
        Advance the simulation clock by `step_minutes` of simulated time.
        Returns a StepResult with all events produced during the step.
        """
        if self._status != EngineStatus.ACTIVE:
            raise RuntimeError(
                f"Cannot step: engine is '{self._status.value}'. "
                "Call /simulation/start first."
            )

        minutes = step_minutes if step_minutes is not None else self._config.default_step_minutes
        if minutes <= 0:
            raise ValueError("step_minutes must be positive")

        env = self._env
        assert env is not None

        time_before = env.now
        time_after = min(time_before + minutes, self._config.max_simulation_time)

        events_before = self._event_log.count
        self._event_log.advance_step()

        # Run the SimPy event loop up to the target time
        env.run(until=time_after)

        self._state.simulation_time = env.now
        self._state.step_count += 1

        # Record engine step in the log
        self._event_log.record(
            env.now,
            SimEventType.SIMULATION_STEPPED,
            step_minutes=minutes,
            step_number=self._state.step_count,
        )

        new_events = [
            e.to_dict()
            for e in self._event_log.all()[events_before:]
        ]
        snapshot = self._state.snapshot(self._event_log.count)

        # Auto-complete when simulation time is exhausted
        if env.now >= self._config.max_simulation_time:
            self._status = EngineStatus.COMPLETED

        return StepResult(
            step_number=self._state.step_count,
            simulation_time_before=time_before,
            simulation_time_after=env.now,
            step_minutes=minutes,
            new_events=new_events,
            state_snapshot=snapshot.to_dict(),
            status=self._status,
        )

    def reset(self) -> StateSnapshot:
        """
        Tear down the current simulation and return to IDLE state.
        The next call to start() may supply a new config.
        """
        self._env = None
        self._resources = None
        self._rng = None
        self._status = EngineStatus.IDLE

        # Fresh state and log
        self._state = HospitalStateManager(self._config)
        self._event_log = EventLog()
        self._event_log.record(0.0, SimEventType.SIMULATION_RESET)

        snapshot = self._state.snapshot(self._event_log.count)
        return snapshot

    # ── Read-only queries ──────────────────────────────────────────────────────

    @property
    def status(self) -> EngineStatus:
        return self._status

    @property
    def simulation_time(self) -> float:
        if self._env is not None:
            return self._env.now
        return 0.0

    def get_state_snapshot(self) -> StateSnapshot:
        """Return a current state snapshot without advancing the clock."""
        return self._state.snapshot(self._event_log.count)

    def get_events(
        self,
        since_time: float | None = None,
        since_step: int | None = None,
        event_type: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Query the event log with optional filters.
        Results are ordered chronologically (ascending simulation_time).
        """
        events = self._event_log.all()

        if since_time is not None:
            events = [e for e in events if e.simulation_time >= since_time]
        if since_step is not None:
            events = [e for e in events if e.step_number >= since_step]
        if event_type is not None:
            events = [e for e in events if e.event_type.value == event_type]
        if limit is not None:
            events = events[-limit:]  # most recent N events

        return [e.to_dict() for e in events]

    def get_resources_snapshot(self) -> dict[str, Any]:
        if self._resources is None:
            return {}
        return self._resources.to_dict()

    def get_config(self) -> dict[str, Any]:
        import dataclasses
        return dataclasses.asdict(self._config)

    # ── Raw event access for agent processing ──────────────────────────────────

    def get_raw_events(self, since_index: int = 0) -> list:
        """
        Return raw SimEvent objects (not dicts) from `since_index` onward.
        Used by the AgentRegistry to process events with typed access.
        """
        return self._event_log.all()[since_index:]

    @property
    def event_count(self) -> int:
        """Current total number of recorded events."""
        return self._event_log.count

    # ── Snapshot history ───────────────────────────────────────────────────────

    def get_snapshots(self) -> list[dict[str, Any]]:
        """
        Return all accumulated StateSnapshots (one per step + start/reset).
        Useful for replaying or inspecting historical state progression.
        """
        return [s.to_dict() for s in self._state.get_snapshots()]


# ── Global singleton + asyncio lock ───────────────────────────────────────────

_engine: HospitalSimEngine = HospitalSimEngine()
_engine_lock: asyncio.Lock = asyncio.Lock()


def get_engine() -> HospitalSimEngine:
    """Return the process-global engine singleton."""
    return _engine


def get_engine_lock() -> asyncio.Lock:
    """Return the asyncio.Lock that serialises API access to the engine."""
    return _engine_lock
