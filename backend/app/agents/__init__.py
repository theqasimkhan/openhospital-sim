"""
OpenHospital Sim – multi-agent hospital operations layer.

Phase 3: agents observe simulation events and emit structured decisions
with explainable reasoning. No medical advice is generated; all logic
is purely operational.
"""
from __future__ import annotations

from app.agents.registry import AgentRegistry, get_registry, get_registry_lock

__all__ = ["AgentRegistry", "get_registry", "get_registry_lock"]
