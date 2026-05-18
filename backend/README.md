# OpenHospital Sim — Backend

Production-grade **FastAPI** backend for the OpenHospital AI digital twin simulator.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.115+ / Python 3.12 |
| Validation | Pydantic v2 + pydantic-settings |
| Database | PostgreSQL 16 (SQLAlchemy 2 async + asyncpg) |
| Cache / Pub-Sub | Redis 7 (redis-py asyncio) |
| Migrations | Alembic |
| Logging | structlog (JSON in production) |
| Containerisation | Docker + docker-compose |
| Testing | pytest + pytest-asyncio + httpx |
| Linting | Ruff + mypy |

---

## Project Layout

```
backend/
├── app/
│   ├── main.py              # App factory, lifespan, middleware
│   ├── api/
│   │   ├── deps.py          # Annotated dependency aliases
│   │   └── v1/
│   │       ├── router.py    # Aggregated v1 router
│   │       └── endpoints/
│   │           └── health.py
│   ├── core/
│   │   ├── config.py        # Pydantic settings (env-driven)
│   │   ├── logging.py       # structlog configuration
│   │   └── exceptions.py    # Domain exceptions + handlers
│   ├── db/
│   │   ├── session.py       # Async SQLAlchemy engine & session
│   │   └── redis.py         # Async Redis client
│   ├── models/
│   │   └── base.py          # Declarative base + mixins
│   ├── schemas/
│   │   └── health.py        # Pydantic response/request schemas
│   └── services/            # Business-logic layer (add modules here)
├── tests/
│   ├── conftest.py          # Fixtures & dependency overrides
│   └── test_health.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── .env.example
```

---

## Quick Start

### 1. Prerequisites

- Python 3.12+
- Docker & docker-compose

### 2. Environment

```bash
cp .env.example .env
# Edit .env with your local secrets
```

### 3a. Run with Docker (recommended)

```bash
docker compose up --build
```

Services:
- Backend API → `http://localhost:8000`
- Swagger UI  → `http://localhost:8000/api/v1/docs`
- PostgreSQL  → `localhost:5432`
- Redis       → `localhost:6379`

### 3b. Run locally (virtualenv)

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# Start dependencies
docker compose up postgres redis -d

python -m app.main               # or: uvicorn app.main:app --reload
```

---

## API Endpoints (Phase 1)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/ping` | Liveness probe |
| `GET` | `/api/v1/health` | Readiness + dependency check |

---

## Running Tests

```bash
pytest
# With coverage:
pytest --cov=app --cov-report=term-missing
```

---

## Adding a New Domain Module

1. Create `app/models/my_model.py` (inherits `AuditMixin + Base`)
2. Create `app/schemas/my_schema.py` (Pydantic request/response)
3. Create `app/services/my_service.py` (business logic)
4. Create `app/api/v1/endpoints/my_router.py`
5. Register the router in `app/api/v1/router.py`
6. Add an Alembic migration: `alembic revision --autogenerate -m "add my_model"`

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | `development` / `staging` / `production` |
| `DEBUG` | `false` | Enable SQLAlchemy echo + hot reload |
| `SECRET_KEY` | *(must set)* | JWT signing secret |
| `POSTGRES_*` | see `.env.example` | PostgreSQL connection |
| `REDIS_*` | see `.env.example` | Redis connection |
| `LOG_LEVEL` | `INFO` | Log verbosity |
| `LOG_JSON` | `true` | Emit JSON log lines |
| `SIM_TICK_SECONDS` | `60` | Simulation engine tick interval |
