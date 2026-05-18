# Deployment Guide

## Local Development

The fastest way to get started:

```bash
# 1. Clone and configure
git clone https://github.com/theqasimkhan/openhospital-sim.git
cd openhospital-sim
cp .env.example .env

# 2. Install dependencies
make setup

# 3. Start all infrastructure (Postgres + Redis)
docker compose up postgres redis -d

# 4. Start backend (port 8000)
make dev-backend

# 5. Start frontend (port 3001) — in a second terminal
make dev-frontend
```

Access:
- Frontend: http://localhost:3001
- API docs: http://localhost:8000/api/v1/docs
- OpenAPI JSON: http://localhost:8000/api/v1/openapi.json

---

## Docker Compose (Full Stack)

Starts all 6 services: Postgres, Redis, Backend, Frontend, Prometheus, Grafana.

```bash
cp .env.example .env
docker compose up --build
```

| Service | Port | URL |
|---------|------|-----|
| Frontend | 3001 | http://localhost:3001 |
| Backend API | 8000 | http://localhost:8000 |
| Prometheus | 9090 | http://localhost:9090 |
| Grafana | 3000 | http://localhost:3000 (admin/admin) |
| PostgreSQL | 5432 | — |
| Redis | 6379 | — |

To rebuild after code changes:
```bash
docker compose build --no-cache backend frontend
docker compose up -d
```

---

## Environment Variables

See `.env.example` for the complete reference. Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes (production) | JWT signing key — generate with `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | Yes | Database password |
| `APP_ENV` | No | `development` \| `staging` \| `production` |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins |
| `LOG_JSON` | No | `true` for JSON logs (production), `false` for console |

In production, set `APP_ENV=production`. This disables the Swagger UI and OpenAPI JSON endpoint.

---

## Kubernetes

### Prerequisites
- Kubernetes 1.27+
- `kubectl` configured for your cluster
- `nginx-ingress-controller` installed
- `metrics-server` installed (for HPA)
- (Optional) `cert-manager` for automatic TLS

### Deploy

```bash
# 1. Fill in secrets (base64-encode your values)
echo -n "mypassword" | base64
# → bXlwYXNzd29yZA==

# 2. Edit k8s/secret.yaml with your encoded values

# 3. Update k8s/configmap.yaml with your domain and settings

# 4. Update image references in deployment yamls
# Images from CI: ghcr.io/theqasimkhan/ohsim-backend:latest
# With your actual registry path

# 5. Apply all manifests
make k8s-apply

# 6. Watch rollout
kubectl rollout status deployment/ohsim-backend -n ohsim
kubectl rollout status deployment/ohsim-frontend -n ohsim

# 7. Check status
make k8s-status
```

### Manifest Overview

| File | Resource | Description |
|------|----------|-------------|
| `namespace.yaml` | Namespace | Isolated `ohsim` namespace |
| `configmap.yaml` | ConfigMap | Non-secret configuration |
| `secret.yaml` | Secret | DB passwords, secret keys |
| `postgres-statefulset.yaml` | StatefulSet + Service | PostgreSQL with PVC |
| `redis-deployment.yaml` | Deployment + Service | Redis cache |
| `backend-deployment.yaml` | Deployment + Service | FastAPI (2 replicas) |
| `frontend-deployment.yaml` | Deployment + Service | Next.js (2 replicas) |
| `ingress.yaml` | Ingress | nginx ingress with TLS |
| `hpa.yaml` | HPA | Auto-scale backend (2–8) and frontend (2–6) |

### Scaling

Horizontal Pod Autoscaler scales the backend (CPU threshold 70%) and frontend automatically. Manual override:

```bash
kubectl scale deployment ohsim-backend --replicas=4 -n ohsim
```

---

## Production Checklist

### Security
- [ ] `SECRET_KEY` is a securely generated 256-bit hex string
- [ ] `POSTGRES_PASSWORD` and `REDIS_PASSWORD` are strong random values
- [ ] `APP_ENV=production` (disables Swagger UI)
- [ ] `ALLOWED_ORIGINS` only contains your actual frontend domain
- [ ] Kubernetes secrets are managed via Vault or Sealed Secrets
- [ ] Ingress has TLS certificates (cert-manager or manual)
- [ ] `/api/v1/metrics` is network-restricted (not publicly exposed)
- [ ] Container images run as non-root users (`appuser`)

### Performance
- [ ] PostgreSQL connection pool sized appropriately (`DB_POOL_SIZE`)
- [ ] Redis `maxmemory` set to match available RAM
- [ ] Uvicorn worker count set to `2 × CPU_count + 1` in Dockerfile
- [ ] HPA min/max replicas reviewed for expected traffic

### Observability
- [ ] Prometheus scraping `/api/v1/metrics` every 10–15s
- [ ] Grafana dashboards imported (see `infra/grafana/`)
- [ ] Alert rules configured for `ohsim_icu_occupancy_ratio > 0.9`
- [ ] Log aggregation configured (Loki, Datadog, CloudWatch)
- [ ] Uptime monitoring on `/api/v1/ping` and `/api/v1/health`

### Reliability
- [ ] PostgreSQL backed by durable PVC (not emptyDir)
- [ ] Redis AOF persistence enabled (already set in compose/k8s)
- [ ] PodDisruptionBudget configured for backend
- [ ] Backup strategy for PostgreSQL volumes

---

## CI/CD

GitHub Actions workflow at `.github/workflows/ci.yml`:

| Job | Trigger | Steps |
|-----|---------|-------|
| `backend-lint` | All PRs + push | ruff + mypy |
| `backend-test` | After lint | pytest with coverage (Postgres + Redis services) |
| `frontend-build` | All PRs + push | tsc + next build |
| `docker-build` | Push to main/develop | Build both images |
| `publish` | Push to main | Push to GHCR |

To trigger manually:
```bash
gh workflow run ci.yml
```

---

## Health Monitoring

### Liveness
```http
GET /api/v1/ping
→ 200 {"status": "ok", "message": "pong"}
```

### Readiness
```http
GET /api/v1/health
→ 200 {"status": "healthy", "checks": {"postgres": {...}, "redis": {...}}}
→ 503 if any dependency is unavailable
```

Both endpoints are used by Docker healthchecks and Kubernetes probes.

---

## Logs

In development (`LOG_JSON=false`): colored console output via structlog.

In production (`LOG_JSON=true`): structured JSON — one JSON object per line.

```json
{
  "timestamp": "2026-05-18T05:30:00Z",
  "level": "info",
  "event": "simulation_stepped",
  "step": 5,
  "sim_time_before": 240.0,
  "sim_time_after": 300.0,
  "new_events": 12,
  "agent_decisions": 4,
  "logger": "app.api.v1.endpoints.simulation"
}
```

Stream logs from Docker:
```bash
docker compose logs -f backend | jq .
```
