"""
Prometheus metrics for OpenHospital Sim.

Metric families
───────────────
ohsim_http_requests_total          – counter  – HTTP request counts by method/path/status
ohsim_http_request_duration_seconds – histogram – latency distribution
ohsim_simulation_steps_total       – counter  – total engine steps executed
ohsim_simulation_events_total      – counter  – total sim events by type
ohsim_agent_decisions_total        – counter  – agent decisions by agent/priority
ohsim_icu_occupancy_ratio           – gauge    – ICU beds occupied / total
ohsim_ward_occupancy_ratio          – gauge    – ward beds occupied / total
ohsim_emergency_queue_length        – gauge    – patients waiting for triage
ohsim_staff_availability_ratio      – gauge    – fraction of staff available
ohsim_patient_throughput_total      – counter  – cumulative discharges
ohsim_patient_deaths_total          – counter  – cumulative deaths
ohsim_active_patients               – gauge    – patients currently in the system
ohsim_forecast_runs_total           – counter  – forecasting pipeline executions
ohsim_optimization_runs_total       – counter  – optimizer invocations by algorithm
ohsim_replay_runs_stored            – gauge    – number of runs in the replay store
"""
from __future__ import annotations

import time
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


# ── Registry ───────────────────────────────────────────────────────────────────

if PROMETHEUS_AVAILABLE:
    _registry = CollectorRegistry(auto_describe=True)

    # ── HTTP layer ────────────────────────────────────────────────────────────
    HTTP_REQUESTS = Counter(
        "ohsim_http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status_code"],
        registry=_registry,
    )
    HTTP_LATENCY = Histogram(
        "ohsim_http_request_duration_seconds",
        "HTTP request latency",
        ["method", "path"],
        buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
        registry=_registry,
    )

    # ── Simulation engine ─────────────────────────────────────────────────────
    SIM_STEPS = Counter(
        "ohsim_simulation_steps_total",
        "Total simulation steps executed",
        registry=_registry,
    )
    SIM_EVENTS = Counter(
        "ohsim_simulation_events_total",
        "Simulation events by type",
        ["event_type"],
        registry=_registry,
    )

    # ── Agents ────────────────────────────────────────────────────────────────
    AGENT_DECISIONS = Counter(
        "ohsim_agent_decisions_total",
        "Agent decisions by agent ID and priority",
        ["agent_id", "priority"],
        registry=_registry,
    )

    # ── Hospital state gauges ─────────────────────────────────────────────────
    ICU_OCCUPANCY_RATIO = Gauge(
        "ohsim_icu_occupancy_ratio",
        "ICU beds occupied fraction (0.0–1.0)",
        registry=_registry,
    )
    WARD_OCCUPANCY_RATIO = Gauge(
        "ohsim_ward_occupancy_ratio",
        "Regular ward occupancy fraction (0.0–1.0)",
        registry=_registry,
    )
    EMERGENCY_QUEUE = Gauge(
        "ohsim_emergency_queue_length",
        "Patients in the emergency intake queue",
        registry=_registry,
    )
    STAFF_AVAILABILITY = Gauge(
        "ohsim_staff_availability_ratio",
        "Fraction of staff currently available (0.0–1.0)",
        registry=_registry,
    )
    ACTIVE_PATIENTS = Gauge(
        "ohsim_active_patients",
        "Patients currently in the simulation",
        registry=_registry,
    )

    # ── Cumulative counters ────────────────────────────────────────────────────
    PATIENT_THROUGHPUT = Counter(
        "ohsim_patient_throughput_total",
        "Cumulative patient discharges",
        registry=_registry,
    )
    PATIENT_DEATHS = Counter(
        "ohsim_patient_deaths_total",
        "Cumulative patient deaths in simulation",
        registry=_registry,
    )

    # ── Pipeline counters ─────────────────────────────────────────────────────
    FORECAST_RUNS = Counter(
        "ohsim_forecast_runs_total",
        "Forecasting pipeline invocations",
        registry=_registry,
    )
    OPTIMIZATION_RUNS = Counter(
        "ohsim_optimization_runs_total",
        "Optimizer invocations by algorithm",
        ["algorithm"],
        registry=_registry,
    )

    # ── Replay ────────────────────────────────────────────────────────────────
    REPLAY_RUNS_STORED = Gauge(
        "ohsim_replay_runs_stored",
        "Number of simulation runs in the replay store",
        registry=_registry,
    )


# ── Update helpers (called from endpoints) ─────────────────────────────────────

def update_state_metrics(snapshot: dict) -> None:
    """Push a StateSnapshot dict into the gauge metrics.

    StateSnapshot.to_dict() uses a *nested* structure:
        snapshot["icu"]["occupancy"]          (not snapshot["icu_occupancy"])
        snapshot["regular_ward"]["occupancy"] (not snapshot["regular_bed_occupancy"])
        snapshot["staff"]["available_doctors"] / ["total_doctors"] etc.
    """
    if not PROMETHEUS_AVAILABLE:
        return
    try:
        icu      = snapshot.get("icu", {})
        ward     = snapshot.get("regular_ward", {})
        staff    = snapshot.get("staff", {})

        icu_occ  = icu.get("occupancy", 0)
        icu_tot  = icu.get("total_beds", 1)
        ward_occ = ward.get("occupancy", 0)
        ward_tot = ward.get("total_beds", 1)

        ICU_OCCUPANCY_RATIO.set(icu_occ / max(icu_tot, 1))
        WARD_OCCUPANCY_RATIO.set(ward_occ / max(ward_tot, 1))
        EMERGENCY_QUEUE.set(snapshot.get("emergency_queue_length", 0))

        # Compute staff availability as fraction of staff currently on duty
        avail = staff.get("available_doctors", 0) + staff.get("available_nurses", 0)
        total = staff.get("total_doctors", 1) + staff.get("total_nurses", 1)
        STAFF_AVAILABILITY.set(avail / max(total, 1))

        # active_patients is a list in the snapshot
        ACTIVE_PATIENTS.set(len(snapshot.get("active_patients", [])))
    except Exception:
        pass


def record_step_metrics(
    new_events: list[dict],
    agent_decisions: list[dict],
    snapshot: dict,
) -> None:
    """Record per-step counters after a simulation step."""
    if not PROMETHEUS_AVAILABLE:
        return
    try:
        SIM_STEPS.inc()
        for evt in new_events:
            SIM_EVENTS.labels(event_type=evt.get("event_type", "unknown")).inc()
        for dec in agent_decisions:
            AGENT_DECISIONS.labels(
                agent_id=dec.get("agent_id", "unknown"),
                priority=dec.get("priority", "info"),
            ).inc()
        update_state_metrics(snapshot)
    except Exception:
        pass


def generate_metrics_response() -> tuple[bytes, str]:
    """Return (body, content_type) for the /metrics endpoint."""
    if not PROMETHEUS_AVAILABLE:
        body = b"# prometheus_client not installed\n"
        return body, "text/plain; version=0.0.4"
    return generate_latest(_registry), CONTENT_TYPE_LATEST


# ── Request tracing middleware ─────────────────────────────────────────────────

class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that increments HTTP request counters and records
    latency histograms for every request, excluding the /metrics path itself.
    """

    EXCLUDED_PATHS = {"/api/v1/metrics", "/metrics", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.EXCLUDED_PATHS or not PROMETHEUS_AVAILABLE:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        path  = request.url.path
        method = request.method

        HTTP_REQUESTS.labels(
            method=method,
            path=path,
            status_code=str(response.status_code),
        ).inc()
        HTTP_LATENCY.labels(method=method, path=path).observe(duration)

        return response
