# =============================================================================
# Screenshot API - Makefile
# =============================================================================

.PHONY: help build up down logs shell test migrate seed clean lint format

# Default target
help:
	@echo "Screenshot API - Available Commands"
	@echo "===================================="
	@echo ""
	@echo "Development:"
	@echo "  make build        - Build Docker images"
	@echo "  make up           - Start all services"
	@echo "  make down         - Stop all services"
	@echo "  make restart      - Restart all services"
	@echo "  make logs         - View logs (all services)"
	@echo "  make logs-api     - View API logs"
	@echo "  make logs-worker  - View worker logs"
	@echo ""
	@echo "Database:"
	@echo "  make migrate      - Run database migrations"
	@echo "  make migrate-new  - Create new migration (NAME=migration_name)"
	@echo "  make seed         - Seed database with initial data"
	@echo "  make db-shell     - Open PostgreSQL shell"
	@echo ""
	@echo "Testing:"
	@echo "  make test         - Run all tests"
	@echo "  make test-unit    - Run unit tests"
	@echo "  make test-int     - Run integration tests"
	@echo "  make test-cov     - Run tests with coverage"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint         - Run linters"
	@echo "  make format       - Format code"
	@echo "  make typecheck    - Run type checker"
	@echo ""
	@echo "Utilities:"
	@echo "  make shell        - Open shell in API container"
	@echo "  make worker-shell - Open shell in worker container"
	@echo "  make redis-cli    - Open Redis CLI"
	@echo "  make clean        - Clean up containers and volumes"
	@echo ""

# =============================================================================
# Docker Commands
# =============================================================================

build:
	docker-compose -f docker/docker-compose.yml build

up:
	docker-compose -f docker/docker-compose.yml up -d

down:
	docker-compose -f docker/docker-compose.yml down

restart:
	docker-compose -f docker/docker-compose.yml restart

logs:
	docker-compose -f docker/docker-compose.yml logs -f

logs-api:
	docker-compose -f docker/docker-compose.yml logs -f api

logs-worker:
	docker-compose -f docker/docker-compose.yml logs -f worker worker-high worker-webhooks

logs-beat:
	docker-compose -f docker/docker-compose.yml logs -f beat

status:
	docker-compose -f docker/docker-compose.yml ps

# =============================================================================
# Database Commands
# =============================================================================

migrate:
	docker-compose -f docker/docker-compose.yml exec api alembic upgrade head

migrate-new:
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make migrate-new NAME=migration_name"; \
		exit 1; \
	fi
	docker-compose -f docker/docker-compose.yml exec api alembic revision --autogenerate -m "$(NAME)"

migrate-down:
	docker-compose -f docker/docker-compose.yml exec api alembic downgrade -1

seed:
	docker-compose -f docker/docker-compose.yml exec api python -m scripts.seed_db

db-shell:
	docker-compose -f docker/docker-compose.yml exec postgres psql -U postgres -d screenshot_api

# =============================================================================
# Testing Commands
# =============================================================================

test:
	docker-compose -f docker/docker-compose.yml exec api pytest -v

test-unit:
	docker-compose -f docker/docker-compose.yml exec api pytest tests/unit -v

test-int:
	docker-compose -f docker/docker-compose.yml exec api pytest tests/integration -v

test-cov:
	docker-compose -f docker/docker-compose.yml exec api pytest --cov=app --cov-report=html --cov-report=term-missing

# =============================================================================
# Code Quality Commands
# =============================================================================

lint:
	docker-compose -f docker/docker-compose.yml exec api ruff check app tests

lint-fix:
	docker-compose -f docker/docker-compose.yml exec api ruff check --fix app tests

format:
	docker-compose -f docker/docker-compose.yml exec api ruff format app tests

typecheck:
	docker-compose -f docker/docker-compose.yml exec api mypy app

# =============================================================================
# Shell Commands
# =============================================================================

shell:
	docker-compose -f docker/docker-compose.yml exec api /bin/bash

worker-shell:
	docker-compose -f docker/docker-compose.yml exec worker /bin/bash

redis-cli:
	docker-compose -f docker/docker-compose.yml exec redis redis-cli

# =============================================================================
# Celery Commands
# =============================================================================

flower:
	@echo "Flower is available at http://localhost:5555"
	@docker-compose -f docker/docker-compose.yml logs -f flower

celery-inspect:
	docker-compose -f docker/docker-compose.yml exec worker celery -A app.workers.celery_app inspect active

celery-stats:
	docker-compose -f docker/docker-compose.yml exec worker celery -A app.workers.celery_app inspect stats

# =============================================================================
# Cleanup Commands
# =============================================================================

clean:
	docker-compose -f docker/docker-compose.yml down -v --remove-orphans

clean-images:
	docker-compose -f docker/docker-compose.yml down --rmi all -v --remove-orphans

prune:
	docker system prune -af

# =============================================================================
# Local Development (without Docker)
# =============================================================================

install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	playwright install chromium

run-api:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-worker:
	celery -A app.workers.celery_app worker --loglevel=info

run-beat:
	celery -A app.workers.celery_app beat --loglevel=info

# =============================================================================
# Production Commands
# =============================================================================

build-prod:
	docker-compose -f docker/docker-compose.prod.yml build

deploy-prod:
	docker-compose -f docker/docker-compose.prod.yml up -d

# =============================================================================
# Generate Commands
# =============================================================================

generate-api-key:
	@if [ -z "$(USER_ID)" ]; then \
		echo "Usage: make generate-api-key USER_ID=uuid"; \
		exit 1; \
	fi
	docker-compose -f docker/docker-compose.yml exec api python -m scripts.generate_api_key $(USER_ID)

# =============================================================================
# Monitoring
# =============================================================================

metrics:
	@echo "API Metrics: http://localhost:8000/metrics"
	@echo "Flower Dashboard: http://localhost:5555"
	@echo "MinIO Console: http://localhost:9001"

