<div align="center">

# OpenHospital Sim

**An AI-powered hospital digital twin — simulate, forecast, and optimise hospital operations at any scale.**

[![CI](https://github.com/theqasimkhan/openhospital-sim/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/theqasimkhan/openhospital-sim/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Live Demo](#) · [API Docs](#api-reference) · [Architecture](docs/architecture.md) · [Roadmap](docs/roadmap.md)

</div>

---

## What Is It?

OpenHospital Sim is a production-grade hospital operations simulator. It runs a physics-accurate discrete-event simulation of hospital processes — patient arrivals, triage, treatment, ICU management, staff shortages, and emergency surges — while a fleet of seven specialised AI agents observe every event, make structured decisions, and explain their reasoning in plain English.

Built for researchers, healthcare operations teams, and engineers who need a rigorous, scriptable, observable platform for:

- **Capacity planning** — how does the ICU behave when inter-arrival rate doubles?
- **What-if analysis** — what is the optimal nurse-to-bed ratio for a 30% surge?
- **Algorithm evaluation** — does genetic or particle-swarm optimization find better staffing solutions?
- **Forecasting** — when will the ICU saturate given the current trend?
- **Training** — replay historical runs step-by-step for decision-making training

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   Next.js 14 Dashboard                        │
│   Dashboard · Simulation · Agents · Forecasting · Replay      │
└─────────────────────────┬────────────────────────────────────┘
                          │ REST / JSON
┌─────────────────────────▼────────────────────────────────────┐
│                 FastAPI Backend  (:8000)                       │
│                                                               │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐  │
│  │  SimPy DES  │  │  7 AI Agents │  │  Replay Store       │  │
│  │  Engine     │──│  Registry    │  │  + /metrics         │  │
│  └─────────────┘  └──────────────┘  └─────────────────────┘  │
│  ┌─────────────┐  ┌──────────────┐                           │
│  │  Forecast   │  │  Optimizer   │                           │
│  │  Pipeline   │  │  GA·PSO·Greedy│                          │
│  └─────────────┘  └──────────────┘                           │
└──────────┬──────────────┬────────────────────────────────────┘
           │              │
    ┌──────▼──────┐  ┌────▼──────┐   ┌────────────┐  ┌────────┐
    │ PostgreSQL  │  │   Redis   │   │ Prometheus │  │Grafana │
    │    :5432    │  │   :6379   │   │   :9090    │  │  :3000 │
    └─────────────┘  └───────────┘   └────────────┘  └────────┘
```

**[→ Full architecture docs](docs/architecture.md)**

---

## Features

### Simulation Engine
- Discrete-event simulation via SimPy — process-oriented, concurrent patient journeys
- 13 event types covering the full patient lifecycle (arrival → triage → treatment → outcome)
- Deterministic replay: same seed always produces the same trajectory
- Emergency spikes, staff shortages, and ICU transfers modelled as background processes
- 25+ tunable parameters: bed counts, staffing, arrival rates, triage probabilities

### Multi-Agent Layer
- **7 specialised agents**: PatientAgent, DoctorAgent, NurseAgent, AdminAgent, ICUManagerAgent, EmergencyCoordinatorAgent, ForecastingAgent
- Every decision is structured: action, plain-English reasoning, confidence score (0–1), priority level, tags
- Agents are stateful — internal counters accumulate across simulation steps
- 400+ decisions emitted across a 24-hour simulated run

### Forecasting
- Holt's double exponential smoothing (level + trend) — drop-in replaceable with Prophet/ARIMA
- Four forecasters: demand, ICU saturation, ward utilisation, staffing requirements
- Composite surge risk detector (4 independent signals weighted into a 0–1 risk score)
- `steps_to_saturation` prediction for ICU capacity planning

### Optimization
- Three solvers on the same multi-objective function: Greedy, Genetic Algorithm, Particle Swarm
- 5 objectives: patient throughput, mortality minimisation, utilisation balance, workload equity, queue minimisation
- Plain-English recommendations with delta from current allocation
- All solvers complete in < 20ms — suitable for real-time API calls

### Replay Engine (Phase 6)
- Every simulation run is recorded step-by-step (events + state + agent decisions)
- Cursor-based playback: open a cursor, advance one step at a time, seek freely
- Export events and decisions as JSON or NDJSON
- Up to 50 runs stored in-process (oldest evicted)

### Observability (Phase 6)
- Prometheus-compatible `/api/v1/metrics` endpoint with 15 metric families
- HTTP request counter + latency histograms via middleware
- Hospital state gauges: ICU occupancy ratio, staff availability, active patients
- Grafana provisioning included — Prometheus datasource auto-configured

### Frontend Dashboard
- Dark enterprise theme — "Datadog for healthcare ops"
- 6 pages: Dashboard, Simulation, Agents, Forecasting, Optimization, Replay
- 11 Recharts components (AreaChart, ComposedChart, RadarChart, BarChart)
- Live API polling with mock data fallback when backend is unavailable
- TypeScript throughout — zero `tsc` errors

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 · TypeScript 5 |
| Web framework | FastAPI 0.115 + Uvicorn |
| Simulation | SimPy 4 + NumPy |
| Database | PostgreSQL 16 (asyncpg + SQLAlchemy async) |
| Cache | Redis 7 (asyncio) |
| Logging | structlog (JSON in prod, console in dev) |
| Metrics | prometheus_client |
| Frontend | Next.js 14 · TailwindCSS · Recharts |
| Testing | pytest + pytest-asyncio + httpx ASGI client |
| Linting | ruff + mypy |
| Containers | Docker (multi-stage) · Docker Compose |
| Orchestration | Kubernetes manifests (Deployment, StatefulSet, HPA, Ingress) |
| CI | GitHub Actions → GHCR |

---

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20+
- Docker & Docker Compose

### 1. Clone & configure

```bash
git clone https://github.com/theqasimkhan/openhospital-sim.git
cd openhospital-sim
cp .env.example .env
```

### 2. Start infrastructure

```bash
docker compose up postgres redis -d
```

### 3. Install and run backend

```bash
make setup-backend
make dev-backend
# → FastAPI running on http://localhost:8000
# → API docs at http://localhost:8000/api/v1/docs
```

### 4. Install and run frontend

```bash
make setup-frontend
make dev-frontend
# → Dashboard at http://localhost:3001
```

### 5. Full stack with Docker Compose

```bash
docker compose up --build
# → Frontend:   http://localhost:3001
# → API:        http://localhost:8000
# → Prometheus: http://localhost:9090
# → Grafana:    http://localhost:3000  (admin/admin)
```

---

## API Examples

### Start a simulation

```bash
curl -X POST http://localhost:8000/api/v1/simulation/start \
  -H "Content-Type: application/json" \
  -d '{"config": {"seed": 42, "icu_beds": 20, "num_doctors": 15}}'
```

### Advance the clock

```bash
curl -X POST http://localhost:8000/api/v1/simulation/step \
  -H "Content-Type: application/json" \
  -d '{"step_minutes": 60}'
```

### Get critical agent decisions

```bash
curl "http://localhost:8000/api/v1/agents/decisions/recent?priority=critical&limit=10"
```

### Run forecasting after 8 steps

```bash
curl -X POST http://localhost:8000/api/v1/forecasting/run \
  -d '{"horizon_steps": 12}'
```

### Optimise resource allocation

```bash
curl -X POST http://localhost:8000/api/v1/optimization/run \
  -d '{"algorithm": "genetic", "max_iterations": 80}'
```

### Export all events from a run

```bash
curl "http://localhost:8000/api/v1/replay/runs/{run_id}/export?format=ndjson" \
  -o events.ndjson
```

### Scrape Prometheus metrics

```bash
curl http://localhost:8000/api/v1/metrics
```

---

## Dashboard Screenshots

> Screenshots coming soon — see the live demo link at the top of this page.

| Page | Description |
|------|-------------|
| **Dashboard** | Real-time KPI cards, ICU/ward capacity bars, patient flow chart, staff radar |
| **Simulation** | Engine controls, config panel, live event timeline, agent decision feed |
| **Agents** | 7 agent cards with status, expandable decision logs, registry stats |
| **Forecasting** | ICU/demand projection charts, surge risk meter, staffing recommendations |
| **Optimization** | Algorithm picker, what-if sliders, convergence graph, recommendation cards |
| **Replay** | Scrubber playback, animated charts, step-by-step event feed |

---

## Simulation Explained

The simulation models a hospital as a set of concurrent processes competing for shared resources.

**Patient journey**:
```
Arrive (Poisson process)
  → Triage (PriorityResource: doctors serve CRITICAL before LOW)
  → Regular ward treatment  ─┐
       or                    ├─ Outcome: Discharge or Death
  → ICU admission           ─┘
```

**Background processes**:
- **Emergency spikes**: Burst arrivals (3–10 patients) every ~8 simulated hours
- **Staff shortages**: 30% of staff unavailable for ~2 hours every ~24 hours

**Determinism**: The engine is seeded by a `numpy.random.Generator`. Identical seed + config → identical event sequence. This makes runs reproducible, comparable, and replayable.

**[→ Full simulation engine docs](docs/simulation-engine.md)**

---

## Project Structure

```
openhospital-sim/
├── backend/
│   ├── app/
│   │   ├── main.py                    # App factory + lifespan
│   │   ├── api/v1/
│   │   │   ├── router.py              # All route registrations
│   │   │   └── endpoints/
│   │   │       ├── health.py          # /ping /health
│   │   │       ├── simulation.py      # Simulation CRUD
│   │   │       ├── agents.py          # Agent queries
│   │   │       ├── forecasting.py     # Forecast + surge
│   │   │       ├── optimization.py    # Optimizer runs
│   │   │       ├── replay.py          # Run history + cursors
│   │   │       └── metrics.py         # /metrics (Prometheus)
│   │   ├── simulation/                # SimPy DES engine (Phase 2)
│   │   ├── agents/                    # 7 AI agents + registry (Phase 3)
│   │   ├── forecasting/               # Statistical pipeline (Phase 4)
│   │   ├── optimization/              # GA · PSO · Greedy (Phase 4)
│   │   ├── replay/                    # Run store + cursor engine (Phase 6)
│   │   ├── observability/             # Prometheus metrics (Phase 6)
│   │   └── core/                      # Config, logging, exceptions
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_health.py
│   │   ├── test_simulation.py
│   │   ├── test_agents.py
│   │   ├── test_replay.py
│   │   └── test_forecasting.py
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── Dockerfile
│   └── pytest.ini
├── frontend/
│   ├── src/
│   │   ├── app/                       # Next.js App Router pages
│   │   ├── components/                # 14 React components
│   │   ├── lib/                       # API client + mock data
│   │   └── types/                     # TypeScript interfaces
│   ├── Dockerfile
│   └── package.json
├── docs/
│   ├── architecture.md
│   ├── simulation-engine.md
│   ├── agents.md
│   ├── forecasting.md
│   ├── optimization.md
│   ├── api-reference.md
│   ├── deployment.md
│   └── roadmap.md
├── k8s/
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── postgres-statefulset.yaml
│   ├── redis-deployment.yaml
│   ├── backend-deployment.yaml
│   ├── frontend-deployment.yaml
│   ├── ingress.yaml
│   └── hpa.yaml
├── infra/
│   ├── prometheus/prometheus.yml
│   └── grafana/provisioning/
├── .github/workflows/ci.yml
├── docker-compose.yml
├── Makefile
├── .env.example
└── README.md
```

---

## Development

### Running tests

```bash
make test
# → pytest with coverage report and HTML output in backend/htmlcov/
```

### Linting & formatting

```bash
make lint       # ruff check
make format     # ruff format + fix
make type-check # mypy
```

### Makefile reference

```bash
make help       # list all targets
make dev        # backend + frontend in parallel
make smoke-test # quick API sanity check
make docker-up  # start full stack
make k8s-apply  # deploy to cluster
make clean      # remove build artefacts
```

---

## Contributing

Contributions are welcome! Please follow these steps:

1. **Fork** the repository and create a feature branch: `git checkout -b feature/my-feature`
2. **Code standards**:
   - Python: follow PEP 8, use type hints everywhere, run `make lint` before committing
   - TypeScript: strict mode, no `any` without justification
   - Tests: new features should include tests; aim to maintain ≥ 70% coverage
   - Docs: update relevant `docs/` files and add a CHANGELOG entry
3. **Commit messages**: use conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
4. **Pull request**: target the `develop` branch, fill out the PR template
5. **CI**: all checks must pass before review

### Reporting issues

- **Bug**: include reproduction steps, expected vs. actual behaviour, and the output of `GET /api/v1/health`
- **Feature request**: describe the use case and expected API/UI behaviour
- **Security vulnerability**: use [GitHub private security advisories](https://github.com/theqasimkhan/openhospital-sim/security/advisories/new) (do not open a public issue for undisclosed problems)

---

## Codebase Metrics

| Category | Files | Lines |
|----------|-------|-------|
| Backend core | 10 | ~620 |
| Simulation engine | 7 | ~1,524 |
| Agents layer | 9 | ~2,141 |
| Forecasting pipeline | 5 | ~993 |
| Optimization engine | 5 | ~1,094 |
| API endpoints | 7 | ~1,200 |
| Replay + observability | 5 | ~600 |
| Tests | 6 | ~550 |
| Frontend pages | 6 | ~700 |
| Frontend components | 14 | ~1,800 |
| Frontend lib/types | 3 | ~700 |
| **Total** | **~77** | **~11,900** |

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 7 | Planned | PostgreSQL persistence + Alembic migrations |
| Phase 8 | Planned | JWT auth + multi-tenancy |
| Phase 9 | Planned | Prophet / ARIMA / XGBoost forecasting |
| Phase 10 | Planned | Real-world FHIR data integration |

**[→ Full roadmap](docs/roadmap.md)**

---

## License

OpenHospital Sim is released under the [MIT License](LICENSE).

```
MIT License

Copyright (c) 2026 OpenHospital Sim Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```

---

<div align="center">

Built with care · Designed for clarity · Made to run at scale

</div>
