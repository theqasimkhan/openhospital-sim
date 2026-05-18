# System Architecture

## Overview

OpenHospital Sim is a layered, service-oriented hospital digital twin. Each layer has a single responsibility and communicates through well-defined interfaces.

```
┌─────────────────────────────────────────────────────────┐
│                    Next.js Frontend                      │
│  Dashboard · Simulation · Agents · Forecasting · Replay  │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / REST (JSON)
┌────────────────────────▼────────────────────────────────┐
│                   FastAPI Backend                        │
│                  /api/v1 (18+ routes)                    │
│  ┌─────────────────────────────────────────────────┐    │
│  │               API Layer (Phase 1)                │    │
│  │  health · simulation · agents · forecasting      │    │
│  │  optimization · replay · metrics                 │    │
│  └──────────┬──────────────────────────────────────┘    │
│             │                                            │
│  ┌──────────▼──────────┐  ┌──────────────────────────┐  │
│  │  Simulation Engine  │  │   Replay Store (Phase 6) │  │
│  │     (Phase 2)       │  │  In-memory run history   │  │
│  │  SimPy + NumPy DES  │  │  cursor-based playback   │  │
│  └──────────┬──────────┘  └──────────────────────────┘  │
│             │                                            │
│  ┌──────────▼──────────┐  ┌──────────────────────────┐  │
│  │   Agent Registry    │  │  Observability (Phase 6) │  │
│  │     (Phase 3)       │  │  Prometheus metrics      │  │
│  │  7 specialised      │  │  HTTP request tracing    │  │
│  │  hospital agents    │  └──────────────────────────┘  │
│  └──────────┬──────────┘                                 │
│             │                                            │
│  ┌──────────▼──────────┐  ┌──────────────────────────┐  │
│  │  Forecasting Layer  │  │  Optimization Engine     │  │
│  │     (Phase 4)       │  │     (Phase 4)            │  │
│  │  Holt DES + surge   │  │  Greedy · GA · PSO       │  │
│  └─────────────────────┘  └──────────────────────────┘  │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │           Infrastructure Layer (Phase 1)         │    │
│  │  PostgreSQL · Redis · structlog · pydantic-settings│  │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### Frontend (Next.js 14)
- Server-side rendered pages with TypeScript and TailwindCSS
- Polls backend every 5–15s for live state updates
- Falls back to realistic mock data when backend is unreachable
- Six pages: Dashboard, Simulation, Agents, Forecasting, Optimization, Replay

### API Layer (FastAPI)
- Async request handling via uvicorn + asyncio
- Single asyncio.Lock per resource (engine, registry) to serialise concurrent writes
- Pydantic v2 request/response validation
- GZip compression + CORS middleware
- Prometheus metrics middleware on every request

### Simulation Engine (SimPy)
- Discrete-event simulation — time advances in discrete steps, not real-time
- Deterministic: seeded `numpy.random.Generator` makes runs reproducible
- Lifecycle FSM: `IDLE → ACTIVE → COMPLETED`
- Step-based API: callers advance the clock by N simulated minutes per call

### Agent Registry
- Pre-registered set of 7 specialised agents
- Agents observe every `SimEvent` and emit `DecisionLog` entries
- All reasoning is plain-English and structured (agent_id, confidence, tags)
- Agents are stateful: internal counters accumulate across steps

### Forecasting Layer
- Holt's double exponential smoothing (level + trend decomposition)
- Operates on ForecastingAgent's time-series data (per-step metrics)
- Surge detector: composite risk score from 4 independent signals

### Optimization Engine
- Three independent solvers operating on the same `SolutionEvaluator`
- Multi-objective scoring: throughput, mortality, utilisation, workload, queue
- All algorithms produce identical `OptimizationResult` shapes

### Replay Store (Phase 6)
- Records every run in-process (up to 50 runs; oldest evicted)
- Step-granular storage: events + state snapshot + agent decisions per step
- Cursor-based playback: open a cursor, advance one step at a time, seek freely
- Export: JSON array or NDJSON line-delimited format

### Observability (Phase 6)
- Prometheus exposition via `/api/v1/metrics`
- `MetricsMiddleware`: records HTTP request counts and latency histograms
- Gauge metrics updated after every simulation step
- `prometheus_client` is an optional dependency; endpoint degrades gracefully

---

## Data Flow: Simulation Step

```
POST /api/v1/simulation/step
         │
         ▼
  Acquire engine_lock + registry_lock (asyncio.Lock)
         │
         ▼
  engine.step(minutes)            ← SimPy runs event loop
         │ produces SimEvents
         ▼
  engine.get_raw_events(since_index)
         │
         ▼
  registry.process_events(events, snapshot)
         │ each agent sees every event
         │ emits DecisionLog entries
         ▼
  replay_store.record_step(...)   ← persist for later replay
         │
         ▼
  record_step_metrics(...)        ← update Prometheus counters/gauges
         │
         ▼
  return StepResult JSON
```

---

## Technology Decisions

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Simulation | SimPy 4 | Industry-standard Python DES; composable processes |
| RNG | NumPy Generator | Seedable, thread-safe, fast distributions |
| Web framework | FastAPI | Async, auto-docs, Pydantic v2 native |
| DB async driver | asyncpg | Fastest Postgres async adapter |
| Caching | Redis asyncio | Sub-ms latency, sorted sets for time-series |
| Logging | structlog | Structured JSON, zero-config context binding |
| Metrics | prometheus_client | De-facto standard; Grafana-ready |
| Forecasting | NumPy (Holt's) | No extra deps; drop-in replaceable with Prophet/ARIMA |
| Optimization | Pure Python | Portable; GA + PSO need no C extensions |
| Frontend | Next.js 14 | App Router, React Server Components, static generation |
| Charts | Recharts | React-native, composable, TypeScript-first |
