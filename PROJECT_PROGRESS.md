# OpenHospital Sim — Project Progress

> **Last updated:** May 18, 2026  
> **Stack:** Python 3.12 · FastAPI · SimPy · NumPy · PostgreSQL · Redis · structlog · prometheus_client · Docker · Kubernetes · Next.js 14 · TypeScript · TailwindCSS · Recharts  
> **Codebase size:** ~8,900 lines of Python across 66 files + ~3,200 lines of TypeScript across 34 frontend files + ~600 lines of infrastructure/config

---

## Overview

OpenHospital Sim is an AI-powered hospital digital twin simulator. The backend models hospital operations through a discrete-event simulation engine, a multi-agent decision layer, statistical forecasting, and resource optimization — all exposed through a versioned FastAPI REST API.

---

## Phase 1 — Backend Skeleton ✅ Complete

### What was built

The foundational FastAPI service with all infrastructure plumbing.

### Files

```
backend/
├── app/
│   ├── main.py                        # App factory, lifespan, middleware
│   ├── api/
│   │   ├── deps.py                    # Annotated DB + Redis dependencies
│   │   └── v1/
│   │       ├── router.py              # Versioned API router
│   │       └── endpoints/
│   │           └── health.py          # /ping, /health
│   ├── core/
│   │   ├── config.py                  # Pydantic-settings (env-driven)
│   │   ├── exceptions.py              # AppError hierarchy + JSON handlers
│   │   └── logging.py                 # structlog JSON/console
│   ├── db/
│   │   ├── session.py                 # Async SQLAlchemy engine + sessionmaker
│   │   └── redis.py                   # Async Redis singleton
│   ├── models/
│   │   └── base.py                    # UUIDMixin, TimestampMixin, AuditMixin
│   └── schemas/
│       └── health.py                  # HealthResponse, PingResponse
├── tests/
│   ├── conftest.py                    # ASGI test client + dependency overrides
│   └── test_health.py                 # Health endpoint tests
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile                         # Multi-stage production image
└── docker-compose.yml                 # Postgres 16 + Redis 7 + backend
```

### API endpoints


| Method | Route            | Description                                                          |
| ------ | ---------------- | -------------------------------------------------------------------- |
| `GET`  | `/api/v1/ping`   | Liveness probe (no DB/Redis check)                                   |
| `GET`  | `/api/v1/health` | Readiness check — probes PostgreSQL + Redis with per-service latency |


### Key features

- **Async-first**: SQLAlchemy asyncio + asyncpg + redis[asyncio]
- **Pydantic v2 settings**: all config via environment variables or `.env`
- **Structured logging**: structlog with JSON output in production, console in dev
- **Error handling**: `AppError` hierarchy with consistent JSON error shapes
- **Middleware**: GZip + CORS
- **Docker**: multi-stage Dockerfile (builder → runtime), `appuser` non-root, healthcheck, 2 uvicorn workers
- **Tests**: httpx ASGI client with mocked DB/Redis via `dependency_overrides`

---

## Phase 2 — Discrete-Event Simulation Engine ✅ Complete

### What was built

A full SimPy-based hospital operations simulation with deterministic replay, snapshot capability, and a complete FastAPI interface.

### Files

```
backend/app/simulation/
├── config.py          # SimulationConfig dataclass (25+ parameters)
├── events.py          # SimEventType enum, SimEvent, EventLog
├── state.py           # Patient, HospitalStateManager, StateSnapshot
├── resources.py       # HospitalResources (SimPy resource pools)
├── policies.py        # TriagePolicy, AdmissionPolicy, DischargePolicy
├── patient_flow.py    # SimPy generator processes
└── engine.py          # HospitalSimEngine orchestrator + singleton

backend/app/api/v1/endpoints/
└── simulation.py      # FastAPI route handlers
```

### Simulation modules in detail

#### `config.py` — SimulationConfig

Single dataclass with every tunable parameter:

- `seed` — deterministic RNG seed (default: 42)
- Hospital capacity: `icu_beds` (20), `regular_beds` (80), `num_doctors` (15), `num_nurses` (40), `num_equipment_units` (30)
- Arrival rate: `mean_inter_arrival_minutes` (10.0 → ~6 patients/hour)
- Treatment durations: triage (5 min), regular ward (120 min), ICU (2,880 min / 2 days)
- Triage probabilities: CRITICAL 5%, HIGH 20%, MEDIUM 45%, LOW 30%
- Emergency spike: every ~8 hours, 3–10 patients per spike
- Staff shortage: every ~24 hours, 30% of staff unavailable for ~2 hours
- Simulation cap: 10,080 minutes (1 simulated week)

#### `events.py` — Event log

- **13 event types**: `PATIENT_ARRIVED`, `TRIAGE_COMPLETE`, `DOCTOR_ASSIGNED`, `TREATMENT_STARTED`, `ICU_TRANSFER`, `DISCHARGE`, `PATIENT_DEATH`, `EMERGENCY_SPIKE`, `STAFF_SHORTAGE`, `STAFF_RESTORED`, `SIMULATION_STARTED`, `SIMULATION_STEPPED`, `SIMULATION_RESET`
- Every `SimEvent` is frozen (immutable): `id`, `simulation_time`, `step_number`, `event_type`, `patient_id`, `metadata`
- `EventLog` is append-only with `snapshot()` / `restore()` for replay-ready event sourcing
- Query methods: `since_time()`, `since_step()`, `by_type()`, `by_patient()`

#### `state.py` — HospitalStateManager

Tracks all 13 required hospital metrics:


| Metric                       | How tracked                                                      |
| ---------------------------- | ---------------------------------------------------------------- |
| ICU occupancy                | Incremented on `transfer_to_icu`, decremented on discharge/death |
| Total ICU beds               | From config                                                      |
| Available beds               | Computed: `total - occupancy`                                    |
| Emergency queue length       | Incremented on arrival, decremented on triage                    |
| Staff availability           | Reduced by shortage fraction, restored after duration            |
| Doctor workload              | `regular_bed_occupancy / available_doctors` (capped 1.0)         |
| Nurse workload               | `(icu + ward occupancy) / available_nurses` (capped 1.0)         |
| Patient throughput           | Running discharged count                                         |
| Equipment utilization        | `in_use / total`                                                 |
| Active patients              | Live dict of `Patient` objects                                   |
| Discharged patients          | Running counter                                                  |
| Deceased simulation patients | Running counter                                                  |
| Event history                | Via `EventLog` (engine-level)                                    |


`StateSnapshot` is a frozen dataclass — serialisable, rollback-anchoring-ready.

#### `resources.py` — SimPy resource pools

- **Doctors / Nurses**: `simpy.PriorityResource` — CRITICAL (priority 0) served before LOW (priority 3)
- **ICU beds / Regular beds / Equipment**: `simpy.Resource` — FIFO
- Runtime capacity adjustment for staff shortage simulation (`reduce_doctors()`, `restore_doctors()`)

#### `policies.py` — Operational policies (no medical logic)

- `TriagePolicy`: probability-weighted triage level; emergency patients skewed toward higher severity (CRITICAL weight ×3.5, LOW weight ×0.2)
- `AdmissionPolicy`: direct ICU at 100% for CRITICAL, 30% for HIGH; mid-treatment ICU transfer based on `prob_icu_transfer`
- `DischargePolicy`: mortality probability by triage level; ICU patients carry ×1.5 multiplier

#### `patient_flow.py` — SimPy processes

Five generator processes:

1. `patient_arrival_process` — Poisson arrivals (exponential inter-arrival)
2. `emergency_spike_process` — Burst arrivals at random intervals
3. `staff_shortage_process` — Reduces SimPy resource capacity temporarily
4. `_regular_treatment` — Doctor (priority) + ward bed → treatment → outcome
5. `_icu_journey` — ICU bed acquisition → treatment → discharge or death

#### `engine.py` — HospitalSimEngine

- **Lifecycle FSM**: `IDLE → ACTIVE → COMPLETED`
- `start(config)` — seeds RNG, builds SimPy env, registers all processes
- `step(step_minutes)` — runs `env.run(until=now + minutes)`, returns `StepResult`
- `reset()` — tears down SimPy env, clears state and event log
- `get_raw_events(since_index)` — exposes raw `SimEvent` objects for agent consumption
- Global singleton + `asyncio.Lock` for thread-safe API access

### API endpoints


| Method | Route                       | Description                                                                                        |
| ------ | --------------------------- | -------------------------------------------------------------------------------------------------- |
| `POST` | `/api/v1/simulation/start`  | Initialise engine (optional config overrides), returns initial state snapshot                      |
| `POST` | `/api/v1/simulation/step`   | Advance clock by `step_minutes` (default 60); returns new events + updated state + agent decisions |
| `POST` | `/api/v1/simulation/reset`  | Tear down to IDLE; clears all state, events, and agent data                                        |
| `GET`  | `/api/v1/simulation/state`  | Point-in-time state snapshot + SimPy resource utilisation                                          |
| `GET`  | `/api/v1/simulation/events` | Filtered event log — query by `since_time`, `since_step`, `event_type`, `limit`                    |


### Verified output (seed=42, 10 simulated hours)

- 63 patient arrivals across 5 steps of 2 hours each
- 44 discharges, 1 death (1.6% mortality)
- ICU: 6/20 beds occupied, doctor workload: 80%, equipment: 60%
- Event types confirmed: `patient_arrived → triage_complete → doctor_assigned → treatment_started → discharge / icu_transfer / patient_death`

---

## Phase 3 — Multi-Agent Hospital Operations Layer ✅ Complete

### What was built

Seven specialised agents that observe simulation events, maintain internal state, make structured operational decisions with explainable reasoning, and expose their logs via a dedicated API.

### Files

```
backend/app/agents/
├── base.py                            # BaseAgent ABC, DecisionLog, enums
├── patient_agent.py                   # PatientAgent
├── doctor_agent.py                    # DoctorAgent
├── nurse_agent.py                     # NurseAgent
├── admin_agent.py                     # AdminAgent
├── icu_manager_agent.py               # ICUManagerAgent
├── emergency_coordinator_agent.py     # EmergencyCoordinatorAgent
├── forecasting_agent.py               # ForecastingAgent
└── registry.py                        # AgentRegistry singleton

backend/app/api/v1/endpoints/
└── agents.py                          # FastAPI route handlers
```

### Agent architecture

#### `base.py` — Foundation

- `**DecisionPriority**`: `INFO | LOW | MEDIUM | HIGH | CRITICAL`
- `**AgentStatus**`: `IDLE | ACTIVE | OVERLOADED | STANDBY | ALERT`
- `**AgentType**`: `patient | doctor | nurse | admin | icu_manager | emergency_coordinator | forecasting`
- `**DecisionLog**`: frozen record with `id`, `agent_id`, `agent_type`, `agent_name`, `simulation_time`, `wall_time`, `trigger_event_id`, `trigger_event_type`, `decision`, `reasoning`, `priority`, `confidence` (0.0–1.0), `tags`, `metadata`
- `**BaseAgent**`: abstract class with `process_event()` dispatch, `_decide()` factory, `get_state()`, `get_logs()`, `reset()`

#### Agent roster


| Agent ID                | Class                       | Decisions emitted on                                                                                                                  |
| ----------------------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `patient-agent-001`     | `PatientAgent`              | Arrival surge (>2× baseline), high-acuity ratio (>30%), ICU spike (>85%), elevated mortality (>5%)                                    |
| `doctor-agent-001`      | `DoctorAgent`               | Doctor overload (>4 patients), CRITICAL prioritisation, fatigue index escalation, shortage response, system workload critical (>95%)  |
| `nurse-agent-001`       | `NurseAgent`                | Workload critical (>90%), queue-support activation (queue >5), ICU nursing pressure (>80%), shortage coverage                         |
| `admin-agent-001`       | `AdminAgent`                | ICU bed reallocation (>80%), ward overflow (>90%), emergency protocol, periodic audit (every 5 steps), multi-system escalation        |
| `icu-manager-001`       | `ICUManagerAgent`           | Admission approval / queueing, capacity warning (>80%), critical alert (>95%), step-down recommendation                               |
| `emergency-coord-001`   | `EmergencyCoordinatorAgent` | Minor / moderate / major spike classification, alert level ladder, double-trouble detection (spike + shortage), all-clear declaration |
| `forecasting-agent-001` | `ForecastingAgent`          | Demand trend changes (decreasing/stable/increasing/surge), ICU saturation early warning, per-step time-series collection              |


#### `registry.py` — AgentRegistry

- Pre-registers all 7 agents on construction; immutable at runtime
- `process_events(events, snapshot)` — dispatches every `SimEvent` to every agent in insertion order
- `get_recent_decisions(limit, agent_id, agent_type, priority, since_sim_time)` — filtered global log
- `get_forecast_time_series()` — delegates to ForecastingAgent
- Global singleton + `asyncio.Lock`

#### Engine integration

`POST /simulation/step` now:

1. Records `events_before = engine.event_count`
2. Runs `engine.step()`
3. Fetches `engine.get_raw_events(since_index=events_before)`
4. Calls `registry.process_events(new_raw_events, snapshot)`
5. Appends `agent_decisions` to the step response

### API endpoints


| Method | Route                                | Description                                                                                     |
| ------ | ------------------------------------ | ----------------------------------------------------------------------------------------------- |
| `GET`  | `/api/v1/agents`                     | All 7 agents: status, event count, decision count, reasoning summary                            |
| `GET`  | `/api/v1/agents/registry`            | Registry metadata: total events processed, total decisions                                      |
| `GET`  | `/api/v1/agents/decisions/recent`    | Global decision log — filter by `agent_id`, `agent_type`, `priority`, `since_sim_time`, `limit` |
| `GET`  | `/api/v1/agents/forecast/timeseries` | ForecastingAgent per-step metrics (arrivals, ICU/ward util, queue, outcomes)                    |
| `GET`  | `/api/v1/agents/{agent_id}`          | Full agent state + internal counters + reasoning summary                                        |
| `GET`  | `/api/v1/agents/{agent_id}/logs`     | Individual agent's decision log (paginated, `limit` up to 500)                                  |


### Verified output (seed=42, 16 simulated hours, 8 steps)

- 7 agents processed 445 events → 44 structured decisions
- ICUManagerAgent: 21 admission decisions (18 direct, 3 transfers)
- PatientAgent: tracked 94 arrivals, 70 discharged, 2 deceased (2.8% mortality)
- ForecastingAgent: 8 time-series data points, trend tracking active
- All decisions carry full structured reasoning and confidence scores

---

## Phase 4 — Forecasting & Optimization Services ✅ Complete

### What was built

A statistical forecasting pipeline and three resource optimization algorithms, both operating on live simulation state.

### Files

```
backend/app/forecasting/
├── base.py                # BaseForecaster, ForecastResult, ForecastPoint, ForecastBundle
├── demand_forecaster.py   # DemandForecaster (patient arrivals)
├── icu_forecaster.py      # ICUForecaster (ICU saturation prediction)
├── staffing_forecaster.py # StaffingForecaster, WardUtilizationForecaster
├── surge_detector.py      # SurgeDetector, SurgeRiskResult
└── schemas.py             # Pydantic request/response schemas

backend/app/optimization/
├── base.py                # OptimizationVariable, Solution, BaseOptimizer, OptimizationResult
├── evaluator.py           # SolutionEvaluator, multi-objective scoring
├── objectives.py          # Individual objective functions
├── greedy.py              # GreedyOptimizer (coordinate descent + random restarts)
├── genetic_algorithm.py   # GeneticOptimizer (real-valued GA)
└── particle_swarm.py      # ParticleSwarmOptimizer (PSO)

backend/app/api/v1/endpoints/
├── forecasting.py         # Forecasting route handlers
└── optimization.py        # Optimization route handlers
```

### Forecasting pipeline

#### Statistical model: Holt's Double Exponential Smoothing

- Level + trend decomposition; outperforms simple moving averages on trended data
- Designed to be drop-in replaced with Prophet / ARIMA / XGBoost by subclassing `BaseForecaster`
- Confidence scales with available data points (low at <5 steps, max ~0.90)

#### Forecasters


| Class                       | Metric forecasted                     | Extra outputs                                   |
| --------------------------- | ------------------------------------- | ----------------------------------------------- |
| `DemandForecaster`          | Patient arrivals per step             | Trend direction                                 |
| `ICUForecaster`             | ICU bed utilisation fraction          | `steps_to_saturation`, `saturation_probability` |
| `WardUtilizationForecaster` | Regular ward occupancy fraction       | Trend direction                                 |
| `StaffingForecaster`        | Recommended doctors + nurses per step | Peak staffing requirement                       |


#### SurgeDetector

Composite surge risk assessment combining:

- Current arrival rate vs. moving average
- ICU occupancy pressure
- Emergency queue depth
- ForecastingAgent demand trend signal

Outputs: `risk_level` (low / medium / high / critical), `composite_score` (0.0–1.0), per-signal breakdown, recommended actions.

### Optimization engine

**Decision variables** (continuous, bounded):

- `doctors_on_duty` — active doctor count
- `nurses_on_duty` — active nurse count
- `icu_beds_active` — staffed ICU beds
- `regular_beds_active` — open ward beds

**Multi-objective scoring** (via `SolutionEvaluator`):

- Patient throughput maximisation
- Mortality minimisation
- Resource utilisation balance
- Staff workload equity
- Queue length minimisation

**Algorithms**:


| Algorithm | Class                    | Typical wall time | Approach                             |
| --------- | ------------------------ | ----------------- | ------------------------------------ |
| `greedy`  | `GreedyOptimizer`        | <5 ms             | Coordinate descent + random restarts |
| `genetic` | `GeneticOptimizer`       | <20 ms            | Real-valued GA, 60 generations       |
| `pso`     | `ParticleSwarmOptimizer` | <20 ms            | Particle swarm, 60 iterations        |


All algorithms return `OptimizationResult` with: `best_score`, `baseline_score`, `improvement_pct`, `best_solution`, `convergence_history`, `evaluations`, `wall_time_seconds`, and plain-English `recommendations`.

### API endpoints


| Method | Route                            | Description                                                                                                                |
| ------ | -------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `POST` | `/api/v1/forecasting/run`        | Fit all forecasters on ForecastingAgent time-series; returns full ForecastBundle (demand, ICU, ward, staffing, surge risk) |
| `GET`  | `/api/v1/forecasting/latest`     | Latest ForecastBundle from most recent run                                                                                 |
| `GET`  | `/api/v1/forecasting/surge-risk` | Real-time surge risk; falls back to live assessment if no forecast has been run                                            |
| `POST` | `/api/v1/optimization/run`       | Run chosen optimizer (`greedy`, `genetic`, `pso`) against current state; returns best allocation + scores                  |
| `GET`  | `/api/v1/optimization/results`   | Latest optimization result                                                                                                 |


---

## Complete API Surface

All routes are under `/api/v1/`. Base URL: `http://localhost:8000`

### System


| Method | Path             | Summary                            |
| ------ | ---------------- | ---------------------------------- |
| GET    | `/api/v1/ping`   | Liveness probe                     |
| GET    | `/api/v1/health` | Readiness — Postgres + Redis probe |


### Simulation Engine


| Method | Path                        | Summary                                      |
| ------ | --------------------------- | -------------------------------------------- |
| POST   | `/api/v1/simulation/start`  | Start simulation (optional config overrides) |
| POST   | `/api/v1/simulation/step`   | Advance clock by N minutes                   |
| POST   | `/api/v1/simulation/reset`  | Reset to idle                                |
| GET    | `/api/v1/simulation/state`  | Current state snapshot                       |
| GET    | `/api/v1/simulation/events` | Filtered event log                           |


### Agents


| Method | Path                                 | Summary                          |
| ------ | ------------------------------------ | -------------------------------- |
| GET    | `/api/v1/agents`                     | All agents with status           |
| GET    | `/api/v1/agents/registry`            | Registry metadata                |
| GET    | `/api/v1/agents/decisions/recent`    | Global decision log (filterable) |
| GET    | `/api/v1/agents/forecast/timeseries` | ForecastingAgent time-series     |
| GET    | `/api/v1/agents/{agent_id}`          | Single agent detail              |
| GET    | `/api/v1/agents/{agent_id}/logs`     | Agent decision log               |


### Forecasting


| Method | Path                             | Summary                |
| ------ | -------------------------------- | ---------------------- |
| POST   | `/api/v1/forecasting/run`        | Run all forecasters    |
| GET    | `/api/v1/forecasting/latest`     | Latest forecast bundle |
| GET    | `/api/v1/forecasting/surge-risk` | Surge risk assessment  |


### Optimization


| Method | Path                           | Summary                                |
| ------ | ------------------------------ | -------------------------------------- |
| POST   | `/api/v1/optimization/run`     | Run optimizer (greedy / genetic / pso) |
| GET    | `/api/v1/optimization/results` | Latest optimization result             |


**Total: 18 routes across 4 domains.**

---

## Phase 5 — Frontend Dashboard ✅ Complete

### What was built

A premium Next.js 14 frontend dashboard with TypeScript, TailwindCSS, and Recharts — connecting directly to all 18 backend API routes with mock data fallback.

### Design aesthetic

- **Datadog for healthcare ops** — data-dense panels, status indicators, live metrics
- **SimCity for hospital infra** — capacity bars, zone utilization, resource allocation views
- **Air traffic control** — real-time queue management, alert ladder, agent decision feeds

### Files

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx                   # Root layout (dark theme, Inter font)
│   │   ├── page.tsx                     # Redirect → /dashboard
│   │   ├── dashboard/page.tsx           # Live hospital command center
│   │   ├── simulation/page.tsx          # Engine controls + event log
│   │   ├── agents/page.tsx              # Agent roster + decision logs
│   │   ├── forecasting/page.tsx         # Forecast charts + surge risk
│   │   ├── optimization/page.tsx        # What-if + resource analytics
│   │   └── replay/page.tsx              # Step-by-step event playback
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppShell.tsx             # Page wrapper (Sidebar + TopBar + main)
│   │   │   ├── Sidebar.tsx              # Fixed nav with route highlighting
│   │   │   └── TopBar.tsx               # Live health check + clock
│   │   ├── dashboard/
│   │   │   ├── HospitalOverviewCards.tsx   # 6 KPI cards + capacity bars + status strip
│   │   │   ├── ICUOccupancyChart.tsx       # AreaChart ICU/ward util + threshold lines
│   │   │   ├── EmergencyQueuePanel.tsx     # BarChart arrivals + visual queue indicator
│   │   │   ├── PatientFlowGraph.tsx        # ComposedChart arrivals/discharge/mortality
│   │   │   └── StaffUtilizationChart.tsx   # RadarChart + staff workload bars
│   │   ├── simulation/
│   │   │   ├── SimulationControls.tsx      # Start/Step/Reset + config panel + presets
│   │   │   └── EventTimeline.tsx           # Filterable scrollable event feed
│   │   ├── agents/
│   │   │   └── AgentDecisionLogs.tsx       # Expandable decision log with filters
│   │   ├── forecasting/
│   │   │   └── ForecastingPanel.tsx        # ICU/ward/demand forecast + surge risk
│   │   ├── optimization/
│   │   │   ├── ResourceAnalytics.tsx       # Convergence + radar + allocation delta
│   │   │   └── WhatIfScenarioPanel.tsx     # Algorithm picker + param sliders
│   │   └── shared/
│   │       ├── StatusBadge.tsx             # PriorityBadge, AgentStatusBadge, RiskBadge
│   │       └── MetricCard.tsx              # MetricCard, CapacityBar, Panel, SectionHeader
│   ├── lib/
│   │   ├── api.ts                          # All 18 API calls with mock fallback
│   │   └── mock-data.ts                    # Realistic mock data for all domains
│   └── types/
│       └── index.ts                        # Full TypeScript types for all API shapes
├── package.json                            # next 14, recharts, tailwind, swr, lucide
├── tailwind.config.ts                      # Custom dark palette (surface, brand, status)
├── next.config.js                          # API proxy rewrite to :8000
└── .env.local                              # NEXT_PUBLIC_API_URL
```

### Pages

| Route | Component | Description |
| ----- | --------- | ----------- |
| `/dashboard` | Command Center | Live KPIs, bed capacity, patient flow, staff radar, agent strip |
| `/simulation` | Engine Controls | Start/Step/Reset with config, event timeline, per-step decisions |
| `/agents` | Agent Roster | 7 agent cards with status, filterable decision log, registry stats |
| `/forecasting` | Forecast Engine | ICU/ward/demand projection charts, surge risk assessment, staffing |
| `/optimization` | Resource Optimizer | What-if sliders, algorithm picker, convergence graph, recommendations |
| `/replay` | Event Replay | Scrubber playback, animated charts, per-step event feed |

### Key features

- **Real API integration** — all 18 backend routes wired; mock data activates automatically when backend is unavailable
- **Live health polling** — TopBar probes `/api/v1/health` every 15s, shows Postgres/Redis latencies
- **Dark enterprise palette** — `#0a0e1a` background, cyan/blue accents, semantic status colors (ok/warn/critical)
- **11 Recharts components** — AreaChart, ComposedChart, BarChart, RadarChart, LineChart, PolarGrid
- **Zero TypeScript errors** — clean `tsc --noEmit` pass
- **Production build passes** — all 6 routes statically generated, `next build` exit 0
- **Dev server** — `npm run dev` starts on http://localhost:3001

---

## Codebase Metrics


| Category                                                 | Files   | Lines      |
| -------------------------------------------------------- | ------- | ---------- |
| Backend app core (main, config, logging, exceptions, DB) | 10      | ~620       |
| Simulation engine (7 modules)                            | 7       | ~1,524     |
| Agents layer (8 agents + registry)                       | 9       | ~2,141     |
| Forecasting pipeline (5 modules)                         | 5       | ~993       |
| Optimization engine (5 modules)                          | 5       | ~1,094     |
| API endpoints (5 files)                                  | 5       | ~1,009     |
| Tests                                                    | 2       | ~121       |
| **Frontend — pages (6)**                                 | 6       | ~700       |
| **Frontend — components (14)**                           | 14      | ~1,800     |
| **Frontend — lib/types (3)**                             | 3       | ~700       |
| **Total**                                                | **~71** | **~10,702**|


---

## Infrastructure

- **Docker**: multi-stage `Dockerfile` (builder → runtime), `appuser` non-root, healthcheck via `/api/v1/ping`
- **Docker Compose**: `postgres:16`, `redis:7` (AOF + LRU eviction), `backend` service with env-driven config
- **Logging**: structlog structured JSON in production, colored console in development
- **Configuration**: all settings from environment variables; `.env.example` provided
- **Testing**: pytest + pytest-asyncio + httpx ASGI client; `dependency_overrides` mock DB/Redis

---

## Recommended Workflow

```
# 1. Start the simulation
POST /api/v1/simulation/start
     { "config": { "seed": 42, "icu_beds": 20, "num_doctors": 15 } }

# 2. Advance in steps (agents process events automatically)
POST /api/v1/simulation/step   { "step_minutes": 60 }

# 3. Query agent decisions
GET  /api/v1/agents/decisions/recent?priority=critical&limit=20

# 4. Run forecasting after several steps
POST /api/v1/forecasting/run   { "horizon_steps": 12 }
GET  /api/v1/forecasting/surge-risk

# 5. Optimise resource allocation
POST /api/v1/optimization/run  { "algorithm": "genetic", "max_iterations": 80 }

# 6. Inspect agent state
GET  /api/v1/agents/icu-manager-001
GET  /api/v1/agents/emergency-coord-001/logs

# 7. Reset and rerun with different parameters
POST /api/v1/simulation/reset
```

---

## Phase 6 — Replay, Observability, Deployment & Documentation ✅ Complete

### What was built

A complete production-hardening layer: step-by-step simulation replay with cursor-based playback, Prometheus-compatible metrics, full-stack Docker Compose with Prometheus + Grafana, Kubernetes-ready manifests, CI/CD pipeline, comprehensive test suite, and full documentation.

### Files

```
backend/app/replay/
├── __init__.py
└── store.py               # ReplayStore singleton (run history, cursor engine, export)

backend/app/observability/
├── __init__.py
└── metrics.py             # 15 Prometheus metric families + MetricsMiddleware

backend/app/api/v1/endpoints/
├── replay.py              # 8 replay routes (runs, cursors, export)
└── metrics.py             # /metrics endpoint

backend/tests/
├── test_simulation.py     # 20 engine + API tests
├── test_agents.py         # 15 registry + API tests
├── test_replay.py         # 17 store + API tests
└── test_forecasting.py    # 10 forecasting + optimization tests

backend/pytest.ini

docs/
├── architecture.md        # System diagram, component responsibilities, data flow
├── simulation-engine.md   # SimPy internals, config table, event types, benchmarks
├── agents.md              # Agent roster, decision schema, registry pattern
├── forecasting.md         # Holt's model, forecasters, surge detector, ForecastBundle
├── optimization.md        # Decision variables, objectives, algorithm comparison
├── api-reference.md       # All 26 routes with schemas, params, error codes
├── deployment.md          # Local dev, Docker, K8s, production checklist, CI/CD
└── roadmap.md             # Phases 7–10 + backlog

k8s/
├── namespace.yaml
├── configmap.yaml
├── secret.yaml
├── postgres-statefulset.yaml
├── redis-deployment.yaml
├── backend-deployment.yaml
├── frontend-deployment.yaml
├── ingress.yaml
└── hpa.yaml

infra/
├── prometheus/prometheus.yml
└── grafana/provisioning/datasources/prometheus.yml

frontend/Dockerfile

.github/workflows/ci.yml   # lint → test → docker build → GHCR publish
docker-compose.yml          # Updated: 6 services (+ Frontend + Prometheus + Grafana)
Makefile                    # 20 targets: setup, dev, test, lint, docker, k8s, smoke
.env.example               # Complete env variable reference
README.md                  # Top-tier open-source README (1,000+ lines)
```

### Replay Engine

#### `store.py` — ReplayStore

- **`SimulationRun`**: captures config, all events (per step), state snapshots, agent decisions, wall clock timing
- **`StoredStep`**: immutable per-step record with full events + decisions
- **Recording**: `begin_run()` → `record_step()` (called after every `/simulation/step`) → `finish_run()`
- **Cursor-based playback**: `create_cursor()` → `replay_step()` → `seek_cursor()` → `close_cursor()`
- **Export**: JSON array or NDJSON (newline-delimited) for events or decisions
- **Eviction**: LRU, max 50 runs stored in-process
- **Integration**: simulation endpoints automatically record into the store

#### Replay API (8 routes)

| Method | Route | Description |
| ------ | ----- | ----------- |
| `GET` | `/api/v1/replay/runs` | List all runs (newest first) |
| `GET` | `/api/v1/replay/runs/{run_id}` | Full run detail |
| `GET` | `/api/v1/replay/runs/{run_id}/steps/{step_index}` | Single step detail |
| `GET` | `/api/v1/replay/runs/{run_id}/export` | Download events/decisions as JSON or NDJSON |
| `POST` | `/api/v1/replay/runs/{run_id}/cursor` | Open a replay cursor |
| `POST` | `/api/v1/replay/cursor/{cursor_id}/next` | Advance cursor (204 when exhausted) |
| `POST` | `/api/v1/replay/cursor/{cursor_id}/seek` | Jump cursor to step index |
| `DELETE` | `/api/v1/replay/cursor/{cursor_id}` | Close cursor |

### Observability

#### Prometheus Metrics (15 families)

| Metric | Type | Description |
| ------ | ---- | ----------- |
| `ohsim_http_requests_total` | Counter | By method/path/status |
| `ohsim_http_request_duration_seconds` | Histogram | Latency distribution |
| `ohsim_simulation_steps_total` | Counter | Total steps executed |
| `ohsim_simulation_events_total` | Counter | By event type |
| `ohsim_agent_decisions_total` | Counter | By agent_id/priority |
| `ohsim_icu_occupancy_ratio` | Gauge | ICU utilisation (0–1) |
| `ohsim_ward_occupancy_ratio` | Gauge | Ward utilisation (0–1) |
| `ohsim_emergency_queue_length` | Gauge | Queue depth |
| `ohsim_staff_availability_ratio` | Gauge | Staff fraction available |
| `ohsim_active_patients` | Gauge | Patients in system |
| `ohsim_patient_throughput_total` | Counter | Cumulative discharges |
| `ohsim_patient_deaths_total` | Counter | Cumulative deaths |
| `ohsim_forecast_runs_total` | Counter | Forecasting pipeline runs |
| `ohsim_optimization_runs_total` | Counter | By algorithm |
| `ohsim_replay_runs_stored` | Gauge | Runs in replay store |

- `MetricsMiddleware` wraps every request automatically
- `prometheus_client` is optional — endpoint degrades gracefully if not installed

### Infrastructure

#### Docker Compose (6 services)

| Service | Image | Port |
| ------- | ----- | ---- |
| `postgres` | postgres:16-alpine | 5432 |
| `redis` | redis:7-alpine | 6379 |
| `backend` | local build | 8000 |
| `frontend` | local build | 3001 |
| `prometheus` | prom/prometheus:v2.51.0 | 9090 |
| `grafana` | grafana/grafana:10.4.0 | 3000 |

#### Kubernetes (9 manifests)

- `namespace.yaml` — isolated `ohsim` namespace
- `configmap.yaml` — all non-secret settings
- `secret.yaml` — passwords/keys (base64 placeholders)
- `postgres-statefulset.yaml` — StatefulSet + PVC + headless Service
- `redis-deployment.yaml` — Deployment + ClusterIP Service
- `backend-deployment.yaml` — 2-replica Deployment + annotations for Prometheus autodiscovery
- `frontend-deployment.yaml` — 2-replica Deployment
- `ingress.yaml` — nginx Ingress with TLS (cert-manager ready)
- `hpa.yaml` — backend (2–8 replicas) + frontend (2–6 replicas) autoscaling

#### GitHub Actions CI

5-job pipeline: `backend-lint` → `backend-test` (with Postgres + Redis services) → `frontend-build` → `docker-build` → `publish` (GHCR on main)

### Test Suite

| File | Tests | Coverage |
| ---- | ----- | -------- |
| `test_health.py` | 4 | System endpoints |
| `test_simulation.py` | 20 | Engine unit + API integration |
| `test_agents.py` | 15 | Registry unit + API integration |
| `test_replay.py` | 17 | Store unit + API integration |
| `test_forecasting.py` | 10 | Forecasting + optimization API |
| **Total** | **66** | — |

All tests use in-process ASGI client with mocked DB/Redis — no external services required.

### Updated API Surface

**Total: 26 routes across 6 domains.**

| Domain | Routes |
| ------ | ------ |
| System | 2 (ping, health) |
| Simulation | 5 (start, step, reset, state, events) |
| Agents | 6 (list, registry, decisions, timeseries, detail, logs) |
| Forecasting | 3 (run, latest, surge-risk) |
| Optimization | 2 (run, results) |
| Replay | 8 (runs, steps, export, cursors) |
| Observability | 1 (metrics) |

---

## Complete API Surface (All Phases)

| Method | Path | Summary |
| ------ | ---- | ------- |
| GET | `/api/v1/ping` | Liveness probe |
| GET | `/api/v1/health` | Readiness — Postgres + Redis |
| GET | `/api/v1/metrics` | Prometheus metrics |
| POST | `/api/v1/simulation/start` | Start simulation |
| POST | `/api/v1/simulation/step` | Advance clock |
| POST | `/api/v1/simulation/reset` | Reset to idle |
| GET | `/api/v1/simulation/state` | State snapshot |
| GET | `/api/v1/simulation/events` | Event log |
| GET | `/api/v1/agents` | All agents |
| GET | `/api/v1/agents/registry` | Registry metadata |
| GET | `/api/v1/agents/decisions/recent` | Global decision log |
| GET | `/api/v1/agents/forecast/timeseries` | ForecastingAgent time-series |
| GET | `/api/v1/agents/{agent_id}` | Single agent |
| GET | `/api/v1/agents/{agent_id}/logs` | Agent decision log |
| POST | `/api/v1/forecasting/run` | Run all forecasters |
| GET | `/api/v1/forecasting/latest` | Latest forecast bundle |
| GET | `/api/v1/forecasting/surge-risk` | Surge risk |
| POST | `/api/v1/optimization/run` | Run optimizer |
| GET | `/api/v1/optimization/results` | Latest result |
| GET | `/api/v1/replay/runs` | List recorded runs |
| GET | `/api/v1/replay/runs/{run_id}` | Run detail |
| GET | `/api/v1/replay/runs/{run_id}/steps/{idx}` | Step detail |
| GET | `/api/v1/replay/runs/{run_id}/export` | Export events/decisions |
| POST | `/api/v1/replay/runs/{run_id}/cursor` | Open replay cursor |
| POST | `/api/v1/replay/cursor/{cursor_id}/next` | Advance cursor |
| POST | `/api/v1/replay/cursor/{cursor_id}/seek` | Seek cursor |
| DELETE | `/api/v1/replay/cursor/{cursor_id}` | Close cursor |

---

## Codebase Metrics

| Category | Files | Lines |
| -------- | ----- | ----- |
| Backend app core | 10 | ~620 |
| Simulation engine | 7 | ~1,524 |
| Agents layer | 9 | ~2,141 |
| Forecasting pipeline | 5 | ~993 |
| Optimization engine | 5 | ~1,094 |
| API endpoints | 7 | ~1,200 |
| Replay engine | 3 | ~380 |
| Observability | 3 | ~220 |
| Tests | 6 | ~550 |
| Frontend — pages | 6 | ~700 |
| Frontend — components | 14 | ~1,800 |
| Frontend — lib/types | 3 | ~700 |
| **Total** | **~78** | **~11,922** |

---

## Infrastructure

- **Docker**: 6-service full-stack compose (Postgres, Redis, Backend, Frontend, Prometheus, Grafana)
- **Kubernetes**: 9 production manifests with HPA, Ingress (nginx), PVC, TLS-ready
- **CI/CD**: GitHub Actions — lint → test → build → publish to GHCR
- **Makefile**: 20 development targets
- **Docs**: 8 documentation pages + top-tier README

---

## Recommended Workflow

```
# 1. Start the simulation
POST /api/v1/simulation/start
     { "config": { "seed": 42, "icu_beds": 20, "num_doctors": 15 } }

# 2. Advance in steps (agents, replay, and metrics update automatically)
POST /api/v1/simulation/step   { "step_minutes": 60 }

# 3. Query agent decisions
GET  /api/v1/agents/decisions/recent?priority=critical&limit=20

# 4. Run forecasting after several steps
POST /api/v1/forecasting/run   { "horizon_steps": 12 }
GET  /api/v1/forecasting/surge-risk

# 5. Optimise resource allocation
POST /api/v1/optimization/run  { "algorithm": "genetic", "max_iterations": 80 }

# 6. Review replay history
GET  /api/v1/replay/runs
POST /api/v1/replay/runs/{run_id}/cursor
POST /api/v1/replay/cursor/{cursor_id}/next

# 7. Export events for external analysis
GET  /api/v1/replay/runs/{run_id}/export?format=ndjson

# 8. Scrape Prometheus metrics
GET  /api/v1/metrics

# 9. Reset and rerun with different parameters
POST /api/v1/simulation/reset
```

---

