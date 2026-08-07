"""
Prometheus-compatible /metrics endpoint.

Returns Prometheus text exposition format (version 0.0.4).
Compatible with any Prometheus scraper, Grafana agent, or OpenTelemetry
Prometheus receiver.

The endpoint is intentionally kept outside auth middleware so that Prometheus
can scrape it without credentials. In production, restrict access at the
network/ingress layer rather than in the application.
"""
from __future__ import annotations

from fastapi import APIRouter
from starlette.responses import Response

from app.observability.metrics import generate_metrics_response
from app.replay.store import get_replay_store

try:
    from app.observability.metrics import PROMETHEUS_AVAILABLE, REPLAY_RUNS_STORED
except ImportError:
    PROMETHEUS_AVAILABLE = False

router = APIRouter(tags=["observability"])


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    description=(
        "Exposes all application metrics in Prometheus text exposition format. "
        "Scrape this endpoint from your Prometheus instance or Grafana agent."
    ),
    response_class=Response,
    include_in_schema=True,
)
async def prometheus_metrics() -> Response:
    # Update replay store gauge before rendering
    if PROMETHEUS_AVAILABLE:
        try:
            store = get_replay_store()
            runs = store.list_runs(limit=100)
            REPLAY_RUNS_STORED.set(len(runs))
        except Exception:
            pass

    body, content_type = generate_metrics_response()
    return Response(content=body, media_type=content_type)
