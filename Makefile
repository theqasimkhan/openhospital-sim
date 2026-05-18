# ══════════════════════════════════════════════════════════════════════════════
# OpenHospital Sim – Developer Makefile
# ══════════════════════════════════════════════════════════════════════════════
.DEFAULT_GOAL := help
SHELL         := /bin/bash
.PHONY: help setup dev-backend dev-frontend dev test lint format type-check \
        docker-up docker-down docker-build docker-logs \
        k8s-apply k8s-delete \
        clean migrate seed

# ── Colours ───────────────────────────────────────────────────────────────────
CYAN  := \033[0;36m
RESET := \033[0m

# ══════════════════════════════════════════════════════════════════════════════
# HELP
# ══════════════════════════════════════════════════════════════════════════════
help:
	@echo ""
	@echo "  $(CYAN)OpenHospital Sim – Makefile targets$(RESET)"
	@echo ""
	@echo "  Setup"
	@echo "    make setup          Install all dependencies (backend + frontend)"
	@echo ""
	@echo "  Development"
	@echo "    make dev            Start backend + frontend in parallel"
	@echo "    make dev-backend    Start FastAPI dev server only"
	@echo "    make dev-frontend   Start Next.js dev server only"
	@echo ""
	@echo "  Quality"
	@echo "    make test           Run full test suite with coverage"
	@echo "    make lint           Run ruff linter"
	@echo "    make format         Auto-format with ruff + black"
	@echo "    make type-check     Run mypy type checker"
	@echo ""
	@echo "  Docker"
	@echo "    make docker-up      Start full stack with docker compose"
	@echo "    make docker-down    Stop and remove containers"
	@echo "    make docker-build   Rebuild all images"
	@echo "    make docker-logs    Tail logs from all services"
	@echo ""
	@echo "  Kubernetes"
	@echo "    make k8s-apply      Apply all manifests to current context"
	@echo "    make k8s-delete     Delete all ohsim resources from cluster"
	@echo ""
	@echo "  Maintenance"
	@echo "    make clean          Remove build artifacts and caches"
	@echo ""

# ══════════════════════════════════════════════════════════════════════════════
# SETUP
# ══════════════════════════════════════════════════════════════════════════════
setup: setup-backend setup-frontend
	@echo "$(CYAN)✓ Setup complete$(RESET)"

setup-backend:
	@echo "$(CYAN)→ Installing backend dependencies…$(RESET)"
	cd backend && python -m pip install --upgrade pip
	cd backend && pip install -r requirements.txt -r requirements-dev.txt

setup-frontend:
	@echo "$(CYAN)→ Installing frontend dependencies…$(RESET)"
	cd frontend && npm ci

# ══════════════════════════════════════════════════════════════════════════════
# DEVELOPMENT
# ══════════════════════════════════════════════════════════════════════════════
dev:
	@echo "$(CYAN)→ Starting backend and frontend…$(RESET)"
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	@echo "$(CYAN)→ FastAPI dev server on :8000$(RESET)"
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

dev-frontend:
	@echo "$(CYAN)→ Next.js dev server on :3001$(RESET)"
	cd frontend && npm run dev

# ══════════════════════════════════════════════════════════════════════════════
# QUALITY GATES
# ══════════════════════════════════════════════════════════════════════════════
test:
	@echo "$(CYAN)→ Running test suite…$(RESET)"
	cd backend && python -m pytest tests/ \
		-v \
		--cov=app \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-fail-under=70 \
		-x

lint:
	@echo "$(CYAN)→ Linting…$(RESET)"
	cd backend && ruff check app/ tests/

format:
	@echo "$(CYAN)→ Formatting…$(RESET)"
	cd backend && ruff format app/ tests/
	cd backend && ruff check --fix app/ tests/

type-check:
	@echo "$(CYAN)→ Type checking…$(RESET)"
	cd backend && mypy app/ --ignore-missing-imports

# ══════════════════════════════════════════════════════════════════════════════
# DOCKER
# ══════════════════════════════════════════════════════════════════════════════
docker-up:
	@echo "$(CYAN)→ Starting full stack…$(RESET)"
	docker compose up -d

docker-down:
	@echo "$(CYAN)→ Stopping full stack…$(RESET)"
	docker compose down

docker-build:
	@echo "$(CYAN)→ Building images…$(RESET)"
	docker compose build --no-cache

docker-logs:
	docker compose logs -f

docker-restart-backend:
	docker compose restart backend

# ══════════════════════════════════════════════════════════════════════════════
# KUBERNETES
# ══════════════════════════════════════════════════════════════════════════════
k8s-apply:
	@echo "$(CYAN)→ Applying Kubernetes manifests…$(RESET)"
	kubectl apply -f k8s/namespace.yaml
	kubectl apply -f k8s/configmap.yaml
	kubectl apply -f k8s/secret.yaml
	kubectl apply -f k8s/postgres-statefulset.yaml
	kubectl apply -f k8s/redis-deployment.yaml
	kubectl apply -f k8s/backend-deployment.yaml
	kubectl apply -f k8s/frontend-deployment.yaml
	kubectl apply -f k8s/ingress.yaml
	kubectl apply -f k8s/hpa.yaml
	@echo "$(CYAN)✓ Manifests applied$(RESET)"

k8s-delete:
	@echo "$(CYAN)→ Deleting ohsim namespace…$(RESET)"
	kubectl delete namespace ohsim --ignore-not-found

k8s-status:
	kubectl get all -n ohsim

# ══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════════════════
clean:
	@echo "$(CYAN)→ Cleaning build artifacts…$(RESET)"
	find backend -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find backend -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find backend -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find backend -name "*.pyc" -delete 2>/dev/null || true
	find frontend -name ".next" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "$(CYAN)✓ Clean$(RESET)"

# Quick API smoke-test (requires running backend)
smoke-test:
	@echo "$(CYAN)→ Smoke testing API…$(RESET)"
	curl -sf http://localhost:8000/api/v1/ping      | python -m json.tool
	curl -sf http://localhost:8000/api/v1/health     | python -m json.tool
	curl -sfX POST http://localhost:8000/api/v1/simulation/start \
		-H "Content-Type: application/json" \
		-d '{"config": {"seed": 42}}' | python -m json.tool
