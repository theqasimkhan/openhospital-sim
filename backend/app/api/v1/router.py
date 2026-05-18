from fastapi import APIRouter

from app.api.v1.endpoints import agents
from app.api.v1.endpoints import forecasting
from app.api.v1.endpoints import health
from app.api.v1.endpoints import metrics
from app.api.v1.endpoints import optimization
from app.api.v1.endpoints import replay
from app.api.v1.endpoints import simulation

api_router = APIRouter()

# ── System ────────────────────────────────────────────────────────────────────
api_router.include_router(health.router,       prefix="")

# ── Simulation engine (Phase 2) ───────────────────────────────────────────────
api_router.include_router(simulation.router,   prefix="/simulation",   tags=["simulation"])

# ── Multi-agent layer (Phase 3) ───────────────────────────────────────────────
api_router.include_router(agents.router,       prefix="/agents",       tags=["agents"])

# ── Optimization engine (Phase 4) ────────────────────────────────────────────
api_router.include_router(optimization.router, prefix="/optimization", tags=["optimization"])

# ── Forecasting engine (Phase 4) ─────────────────────────────────────────────
api_router.include_router(forecasting.router,  prefix="/forecasting",  tags=["forecasting"])

# ── Replay engine (Phase 6) ───────────────────────────────────────────────────
api_router.include_router(replay.router,       prefix="/replay",       tags=["replay"])

# ── Observability (Phase 6) ───────────────────────────────────────────────────
api_router.include_router(metrics.router,      prefix="",              tags=["observability"])
