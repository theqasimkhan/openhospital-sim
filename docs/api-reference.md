# API Reference

**Base URL**: `http://localhost:8000`  
**API prefix**: `/api/v1`  
**Interactive docs**: `http://localhost:8000/api/v1/docs` (development only)

All responses are JSON unless otherwise noted. Timestamps are Unix epoch floats. Simulation times are in simulated minutes.

---

## System

### GET /api/v1/ping
Liveness probe. No database or Redis check.

```http
GET /api/v1/ping
```

```json
{"status": "ok", "message": "pong"}
```

---

### GET /api/v1/health
Readiness check. Probes PostgreSQL and Redis.

```json
{
  "status": "healthy",
  "checks": {
    "postgres": {"status": "ok", "latency_ms": 1.2},
    "redis":    {"status": "ok", "latency_ms": 0.4}
  }
}
```

---

### GET /api/v1/metrics
Prometheus-compatible metrics endpoint (text exposition format 0.0.4).

```
# HELP ohsim_http_requests_total Total HTTP requests
# TYPE ohsim_http_requests_total counter
ohsim_http_requests_total{method="POST",path="/api/v1/simulation/step",status_code="200"} 42.0
...
```

Scrape configuration:
```yaml
scrape_configs:
  - job_name: ohsim
    metrics_path: /api/v1/metrics
    static_configs:
      - targets: ["localhost:8000"]
```

---

## Simulation Engine

### POST /api/v1/simulation/start
Initialise and start the simulation engine.

**Request body** (all fields optional):
```json
{
  "config": {
    "seed": 42,
    "icu_beds": 20,
    "regular_beds": 80,
    "num_doctors": 15,
    "num_nurses": 40,
    "num_equipment_units": 30,
    "mean_inter_arrival_minutes": 10.0,
    "default_step_minutes": 60.0,
    "max_simulation_time": 10080.0
  }
}
```

**Response**:
```json
{
  "status": "started",
  "simulation_time": 0.0,
  "engine_status": "active",
  "data": {
    "state":  { ... StateSnapshot ... },
    "config": { ... SimulationConfig ... },
    "run_id": "uuid-of-replay-run"
  }
}
```

**Errors**: `409 Conflict` if engine is already active.

---

### POST /api/v1/simulation/step
Advance the simulation clock.

**Request**:
```json
{"step_minutes": 60.0}
```

**Response**:
```json
{
  "status": "stepped",
  "simulation_time": 60.0,
  "engine_status": "active",
  "data": {
    "step_number": 1,
    "simulation_time_before": 0.0,
    "simulation_time_after": 60.0,
    "new_events_count": 7,
    "new_events": [ ... ],
    "state": { ... },
    "agent_decisions_count": 3,
    "agent_decisions": [ ... ]
  }
}
```

**Errors**: `409 Conflict` if engine is not active.

---

### POST /api/v1/simulation/reset
Reset engine to idle. Marks the replay run as aborted.

**Response**:
```json
{"status": "reset", "simulation_time": 0.0, "engine_status": "idle", "data": {...}}
```

---

### GET /api/v1/simulation/state
Point-in-time state snapshot.

**Response `data` contains**:
```json
{
  "state": {
    "simulation_time": 120.0,
    "step_count": 2,
    "icu_occupancy": 4,
    "total_icu_beds": 20,
    "regular_bed_occupancy": 31,
    "total_regular_beds": 80,
    "emergency_queue_length": 1,
    "staff_availability": 1.0,
    "doctor_workload": 0.71,
    "nurse_workload": 0.52,
    "active_patients_count": 35,
    "discharged_count": 9,
    "death_count": 0,
    "patient_throughput": 9,
    "equipment_utilization": 0.58
  },
  "resources": { ... SimPy resource pool snapshot ... }
}
```

---

### GET /api/v1/simulation/events
Filtered event log query.

**Query params**:
| Param | Type | Description |
|-------|------|-------------|
| `since_time` | float | Min simulation time |
| `since_step` | int | Min step number |
| `event_type` | str | Event type filter (see full list) |
| `limit` | int | Max events returned (default 200, max 5000) |

**Valid `event_type` values**: `patient_arrived`, `triage_complete`, `doctor_assigned`, `treatment_started`, `icu_transfer`, `discharge`, `patient_death`, `emergency_spike`, `staff_shortage`, `staff_restored`, `simulation_started`, `simulation_stepped`, `simulation_reset`

---

## Agents

### GET /api/v1/agents
All 7 agents with status, event count, decision count, and reasoning summary.

### GET /api/v1/agents/registry
Registry metadata: total events processed, total decisions, agent count.

### GET /api/v1/agents/decisions/recent

**Query params**:
| Param | Description |
|-------|-------------|
| `agent_id` | Filter by specific agent |
| `agent_type` | Filter by type (`patient`, `doctor`, etc.) |
| `priority` | Filter by priority (`info`, `low`, `medium`, `high`, `critical`) |
| `since_sim_time` | Only decisions after this simulation time |
| `limit` | Max results (default 50, max 500) |

### GET /api/v1/agents/forecast/timeseries
Per-step time-series from ForecastingAgent. Used as input to the forecasting pipeline.

### GET /api/v1/agents/{agent_id}
Full agent state including internal counters. Agent IDs: `patient-agent-001`, `doctor-agent-001`, `nurse-agent-001`, `admin-agent-001`, `icu-manager-001`, `emergency-coord-001`, `forecasting-agent-001`.

### GET /api/v1/agents/{agent_id}/logs
Agent's decision log (paginated). Query param: `limit` (max 500).

---

## Forecasting

### POST /api/v1/forecasting/run

**Request**:
```json
{"horizon_steps": 8, "alpha": 0.3, "beta": 0.1}
```

Requires ≥ 3 completed simulation steps. Returns a `ForecastBundle`.

### GET /api/v1/forecasting/latest
Latest cached ForecastBundle. Returns `404` if no forecast has been run.

### GET /api/v1/forecasting/surge-risk
Real-time surge risk assessment. Falls back to live snapshot if no forecast exists.

---

## Optimization

### POST /api/v1/optimization/run

**Request**:
```json
{
  "algorithm": "genetic",
  "max_iterations": 80,
  "population_size": 40,
  "mutation_rate": 0.15
}
```

**`algorithm`**: `greedy` | `genetic` | `pso`

### GET /api/v1/optimization/results
Latest optimization result. Returns `404` if no run has completed.

---

## Replay

### GET /api/v1/replay/runs
List all recorded simulation runs (newest first).

**Query param**: `limit` (default 20, max 50)

### GET /api/v1/replay/runs/{run_id}
Full run detail. Query param: `include_steps=false` to skip step data.

### GET /api/v1/replay/runs/{run_id}/steps/{step_index}
Single step detail by zero-based index.

### GET /api/v1/replay/runs/{run_id}/export
Export run data as a downloadable file.

**Query params**:
| Param | Values | Default |
|-------|--------|---------|
| `format` | `json` \| `ndjson` | `json` |
| `target` | `events` \| `decisions` | `events` |

### POST /api/v1/replay/runs/{run_id}/cursor
Open a replay cursor. Returns `{"cursor_id": "...", "total_steps": N}`.

### POST /api/v1/replay/cursor/{cursor_id}/next
Advance cursor by one step. Returns `204 No Content` when exhausted.

### POST /api/v1/replay/cursor/{cursor_id}/seek
Jump cursor to a specific step.

```json
{"step_index": 5}
```

### DELETE /api/v1/replay/cursor/{cursor_id}
Close a replay cursor. Returns `204 No Content`.

---

## Error Response Shape

All error responses use a consistent structure:

```json
{
  "detail": "Human-readable error message",
  "error_code": "SIMULATION_ALREADY_ACTIVE",
  "status_code": 409
}
```

| HTTP Status | When |
|-------------|------|
| 400 | Bad request (malformed JSON) |
| 404 | Resource not found |
| 409 | Conflict (e.g. start while active) |
| 422 | Validation error (invalid field values) |
| 500 | Unhandled server error |
