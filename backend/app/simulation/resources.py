"""
SimPy resource pool for the simulated hospital.

Resources wrap SimPy primitives and expose utilisation metrics.
PriorityResource is used for doctors so that high-acuity patients
queue ahead of lower-acuity ones.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import simpy

from app.simulation.config import SimulationConfig

# ── Resource snapshot (for serialisation) ─────────────────────────────────────

@dataclass(frozen=True)
class ResourceSnapshot:
    name: str
    capacity: int
    in_use: int
    queued: int
    utilization: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "name":        self.name,
            "capacity":    self.capacity,
            "in_use":      self.in_use,
            "queued":      self.queued,
            "utilization": round(self.utilization, 4),
        }


# ── Resource pool ──────────────────────────────────────────────────────────────

class HospitalResources:
    """
    Holds all SimPy resource pools for one simulation run.

    Must be recreated when the engine resets (SimPy resources are
    bound to a specific Environment instance).
    """

    def __init__(self, env: simpy.Environment, config: SimulationConfig) -> None:
        # PriorityResource for doctors – lower priority value = served first
        # (CRITICAL=0, HIGH=1, MEDIUM=2, LOW=3)
        self.doctors: simpy.PriorityResource = simpy.PriorityResource(
            env, capacity=config.num_doctors
        )
        self.nurses: simpy.PriorityResource = simpy.PriorityResource(
            env, capacity=config.num_nurses
        )

        # Regular Resource for beds – FIFO within the ICU and ward
        self.icu_beds: simpy.Resource = simpy.Resource(
            env, capacity=config.icu_beds
        )
        self.regular_beds: simpy.Resource = simpy.Resource(
            env, capacity=config.regular_beds
        )
        self.equipment: simpy.Resource = simpy.Resource(
            env, capacity=config.num_equipment_units
        )

        self._config = config

    # ── Snapshot ───────────────────────────────────────────────────────────────

    def _snap(self, name: str, resource: simpy.Resource | simpy.PriorityResource) -> ResourceSnapshot:
        cap = resource.capacity
        in_use = resource.count
        queued = len(resource.queue)
        return ResourceSnapshot(
            name=name,
            capacity=int(cap),
            in_use=in_use,
            queued=queued,
            utilization=in_use / max(1, cap),
        )

    def utilization_snapshot(self) -> dict[str, ResourceSnapshot]:
        return {
            "doctors":      self._snap("doctors",      self.doctors),
            "nurses":       self._snap("nurses",       self.nurses),
            "icu_beds":     self._snap("icu_beds",     self.icu_beds),
            "regular_beds": self._snap("regular_beds", self.regular_beds),
            "equipment":    self._snap("equipment",    self.equipment),
        }

    def to_dict(self) -> dict[str, Any]:
        return {k: v.to_dict() for k, v in self.utilization_snapshot().items()}

    # ── Doctor capacity adjustment (staff shortage) ────────────────────────────

    def reduce_doctors(self, count: int) -> None:
        """Temporarily reduce effective doctor capacity (shortage simulation)."""
        new_cap = max(1, self._config.num_doctors - count)
        self.doctors._capacity = new_cap  # type: ignore[attr-defined]

    def restore_doctors(self) -> None:
        self.doctors._capacity = self._config.num_doctors  # type: ignore[attr-defined]

    def reduce_nurses(self, count: int) -> None:
        new_cap = max(1, self._config.num_nurses - count)
        self.nurses._capacity = new_cap  # type: ignore[attr-defined]

    def restore_nurses(self) -> None:
        self.nurses._capacity = self._config.num_nurses  # type: ignore[attr-defined]
