.PHONY: help up down restart logs build shell migrate migrate-new test lint format check

# ─────────────────────────────────────────────────────────────────
# Venv
# ─────────────────────────────────────────────────────────────────
VENV     := .venv
PYTHON   := $(VENV)/bin/python
PIP      := $(VENV)/bin/pip
UVICORN  := $(VENV)/bin/uvicorn
PYTEST   := $(VENV)/bin/pytest
RUFF     := $(VENV)/bin/ruff
ALEMBIC  := cd backend && ../$(VENV)/bin/alembic
RQ       := $(VENV)/bin/rq


# ─────────────────────────────────────────────────────────────────
# Help
# ─────────────────────────────────────────────────────────────────
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ─────────────────────────────────────────────────────────────────
# Docker Compose
# ─────────────────────────────────────────────────────────────────
up: ## Start all services
	docker compose up -d

up-build: ## Build and start all services
	docker compose up -d --build

down: ## Stop all services
	docker compose down

restart: ## Restart all services
	docker compose restart

logs: ## Follow logs for all services
	docker compose logs -f

logs-backend: ## Follow backend logs only
	docker compose logs -f backend

shell: ## Open shell inside the backend container
	docker compose exec backend bash

# ─────────────────────────────────────────────────────────────────
# Database & Migrations
# ─────────────────────────────────────────────────────────────────
migrate: ## Run Alembic migrations
	$(ALEMBIC) upgrade head

migrate-new: ## Create a new migration (usage: make migrate-new MSG="describe change")
	$(ALEMBIC) revision --autogenerate -m "$(MSG)"

migrate-history: ## Show migration history
	$(ALEMBIC) history

migrate-rollback: ## Roll back one migration
	$(ALEMBIC) downgrade -1

# ─────────────────────────────────────────────────────────────────
# LocalStack bucket
# ─────────────────────────────────────────────────────────────────
bucket: ## Create LocalStack S3 bucket
	cd backend && $(PYTHON) scripts/create_localstack_bucket.py

# ─────────────────────────────────────────────────────────────────
# Development
# ─────────────────────────────────────────────────────────────────
dev: ## Run backend locally (outside docker)
	cd backend && $(UVICORN) app.main:app --host 0.0.0.0 --port 8000 --reload

worker: ## Run RQ worker locally
	cd backend && $(RQ) worker default normalization reconciliation exports

# ─────────────────────────────────────────────────────────────────
# Testing
# ─────────────────────────────────────────────────────────────────
test: ## Run all tests
	cd backend && $(PYTEST) -v

test-unit: ## Run unit tests only
	cd backend && $(PYTEST) app/tests/unit -v

test-integration: ## Run integration tests only
	cd backend && $(PYTEST) app/tests/integration -v

test-cov: ## Run tests with coverage report
	cd backend && $(PYTEST) --cov=app --cov-report=html --cov-report=term-missing

# ─────────────────────────────────────────────────────────────────
# Code quality
# ─────────────────────────────────────────────────────────────────
lint: ## Run ruff linter
	$(RUFF) check backend/app/

format: ## Format code with ruff
	$(RUFF) format backend/app/

check: ## Run lint + format check
	$(RUFF) check backend/app/ && $(RUFF) format --check backend/app/

# ─────────────────────────────────────────────────────────────────
# Demo
# ─────────────────────────────────────────────────────────────────
demo-load: ## Load sample data for demo
	cd backend && $(PYTHON) scripts/load_sample_data.py

demo-run: ## Run sample reconciliation for demo
	cd backend && $(PYTHON) scripts/run_demo_reconciliation.py

# ─────────────────────────────────────────────────────────────────
# Setup (first-time)
# ─────────────────────────────────────────────────────────────────
venv: ## Create Python virtual environment
	/opt/homebrew/bin/python3.13 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements.txt
	@echo "\n✅ venv ready. Activate with: source .venv/bin/activate"

setup: ## First-time local setup
	cp -n .env.example .env || true
	$(MAKE) venv
	$(MAKE) up
	sleep 8
	$(MAKE) migrate
	$(MAKE) bucket
	@echo "\n✅ Setup complete. API running at http://localhost:8000"
	@echo "📖 API docs at http://localhost:8000/docs"
