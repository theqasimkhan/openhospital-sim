# Roadmap

## Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Backend skeleton (FastAPI, DB, Redis, Docker) | ✅ Complete |
| 2 | Discrete-event simulation engine (SimPy) | ✅ Complete |
| 3 | Multi-agent hospital operations layer | ✅ Complete |
| 4 | Forecasting & optimization services | ✅ Complete |
| 5 | Frontend dashboard (Next.js 14) | ✅ Complete |
| 6 | Replay, observability, deployment, docs | ✅ Complete |
| 7 | Persistence & data model | 🔲 Planned |
| 8 | Authentication & multi-tenancy | 🔲 Planned |
| 9 | Advanced forecasting models | 🔲 Planned |
| 10 | Real-world data integration | 🔲 Planned |

---

## Phase 7 — Persistence & Data Model

**Goal**: Persist simulation runs, agent decisions, and forecasts to PostgreSQL so they survive restarts and can be queried with SQL.

**Planned work**:
- Alembic migrations for `simulation_runs`, `simulation_events`, `agent_decisions`, `forecast_bundles`, `optimization_results` tables
- Repository pattern wrapping SQLAlchemy async sessions
- Background task to flush in-memory replay store to DB at run completion
- `GET /api/v1/history` — paginated run history from DB
- `GET /api/v1/history/{run_id}` — full run from DB
- Export to Parquet via `pandas` + `pyarrow`

---

## Phase 8 — Authentication & Multi-Tenancy

**Goal**: Support multiple independent simulation environments with role-based access control.

**Planned work**:
- JWT authentication (HS256) via FastAPI `Depends`
- User model: `id`, `email`, `hashed_password`, `role` (viewer / operator / admin)
- Workspace model: each user/team gets an isolated engine + registry + replay store
- `POST /api/v1/auth/register`, `POST /api/v1/auth/token`
- Role-based guards on write endpoints (step, start, reset, optimize)
- API key support for programmatic access
- Rate limiting via Redis token bucket

---

## Phase 9 — Advanced Forecasting Models

**Goal**: Replace Holt's smoothing with production-grade statistical models.

**Planned work**:
- **Facebook Prophet** integration — handles seasonality (weekly, daily) and holidays
- **ARIMA / SARIMA** via `statsmodels` — for datasets with autocorrelation
- **XGBoost** demand forecasting — feature-rich, handles non-linearities
- Model selection: auto-fit multiple models, return best by AIC/BIC
- Confidence intervals: proper credible intervals (not just ±σ)
- `POST /api/v1/forecasting/train` — explicit model training endpoint
- `GET /api/v1/forecasting/model-info` — active model metadata

---

## Phase 10 — Real-World Data Integration

**Goal**: Feed historical hospital data into the simulation to calibrate parameters and validate predictions.

**Planned work**:
- CSV/FHIR data ingestion endpoint
- Parameter estimation: fit `mean_inter_arrival_minutes`, triage probabilities from historical data
- Backtesting: replay historical period with fitted model, measure forecast accuracy (MAPE, RMSE)
- Benchmark dashboard: predicted vs. actual metrics
- HL7 FHIR R4 patient resource parser
- De-identification pipeline for PHI compliance

---

## Backlog (Unscheduled)

### Simulation Enhancements
- [ ] Department routing (ED → ICU → step-down → discharge)
- [ ] Shift scheduling (day/night/weekend staffing patterns)
- [ ] Equipment maintenance events and downtime modelling
- [ ] Multi-facility network simulation (patient transfer between hospitals)
- [ ] Paediatric vs. adult patient sub-populations
- [ ] Infection control events (isolation, PPE constraints)

### Agent Enhancements
- [ ] LLM-powered reasoning (GPT-4 / Claude integration for natural-language decisions)
- [ ] Agent communication bus (agents can observe each other's decisions)
- [ ] Reinforcement learning agent (learns resource allocation policy from outcomes)
- [ ] Agent A/B testing framework

### Observability
- [ ] OpenTelemetry distributed tracing (OTLP export to Jaeger/Tempo)
- [ ] Pre-built Grafana dashboards (JSON provisioning in `infra/grafana/`)
- [ ] Alert rules for common thresholds (Prometheus Alertmanager)
- [ ] Structured event streaming via Kafka/Redis Streams

### Frontend
- [ ] WebSocket live updates (eliminate polling)
- [ ] Configurable scenario presets library
- [ ] PDF/PNG export of dashboard panels
- [ ] Multi-run comparison view
- [ ] Accessibility audit (WCAG 2.1 AA)

### Infrastructure
- [ ] Helm chart for Kubernetes deployment
- [ ] Terraform modules for AWS/GCP/Azure
- [ ] Horizontal scaling for the simulation engine (Redis-backed shared state)
- [ ] Database read replicas for analytics queries

---

## Contributing to the Roadmap

To propose a new feature:
1. Open a GitHub Issue with the label `roadmap`
2. Describe the use case and expected behaviour
3. Reference any relevant academic papers or industry standards

To implement a roadmap item:
1. Comment on the issue to claim it
2. Create a feature branch: `feature/phase-7-persistence`
3. Open a draft PR early for feedback
4. See [Contributing Guidelines](../README.md#contributing) for code standards
