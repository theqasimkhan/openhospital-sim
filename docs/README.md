# OpenHospital Sim — Project Documentation

OpenHospital Sim is an **AI-powered hospital digital twin simulator** designed to
model, optimise, and forecast hospital operations in real time.

---

## Repository Layout

```
OpenHospital SIM/
├── backend/        # FastAPI async API — Phase 1 ✅
├── frontend/       # React / Next.js dashboard — Phase 2
├── agents/         # Autonomous AI agents (LLM-driven decision makers)
├── simulation/     # Discrete-event simulation engine
├── optimization/   # Resource allocation & scheduling solvers
├── forecasting/    # Demand forecasting & time-series models
├── analytics/      # Reporting, KPIs, data pipelines
├── infrastructure/ # Terraform / Helm / Kubernetes manifests
├── docker/         # Shared Docker utilities and base images
├── docs/           # Project-level documentation (this folder)
├── experiments/    # Notebooks & research experiments
└── tests/          # Cross-module integration / E2E tests
```

---

## Development Phases

| Phase | Scope | Status |
|---|---|---|
| **1** | Backend skeleton (FastAPI, DB, Redis, health checks) | ✅ Complete |
| **2** | Core domain models: patients, departments, staff | Planned |
| **3** | Discrete-event simulation engine | Planned |
| **4** | AI agents: triage, scheduling, resource allocation | Planned |
| **5** | Forecasting & optimisation services | Planned |
| **6** | Real-time dashboard (React) | Planned |
| **7** | Infrastructure as code + CI/CD | Planned |

---

## Getting Started

See [`backend/README.md`](../backend/README.md) for the backend quick-start guide.
