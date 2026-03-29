# Makefile — Task Manager Backend
# Run from the backend/ directory. Type `make help` to list all commands.

.PHONY: help install install-dev dev start start-render \
        test test-v test-fast test-cov \
        lint lint-fix format format-check \
        migrate migrate-create migrate-rollback migrate-history migrate-status \
        docker-up docker-down docker-clean docker-logs docker-rebuild docker-shell docker-psql \
        env clean

BOLD  := \033[1m
CYAN  := \033[36m
RESET := \033[0m

help:
	@echo ""
	@echo "$(BOLD)Task Manager — Makefile$(RESET)"
	@echo "────────────────────────────────────────"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*?##/ \
		{ printf "  $(CYAN)%-22s$(RESET) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────────
install:       ## Install production dependencies
	pip install --upgrade pip && pip install -r requirements.txt

install-dev:   ## Install production + test/lint dependencies
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install pytest pytest-asyncio httpx ruff black

# ── Dev server ────────────────────────────────────────────────────────────────
dev:           ## Start dev server with hot-reload (SQLite)
	uvicorn main:app --host 0.0.0.0 --port 8000 --reload

start:         ## Start production server
	uvicorn main:app --host 0.0.0.0 --port 8000

start-render:  ## Start on Render's required port 10000
	uvicorn main:app --host 0.0.0.0 --port 10000

# ── Tests ─────────────────────────────────────────────────────────────────────
test:          ## Run full test suite (in-memory SQLite)
	DATABASE_URL="sqlite:///:memory:" pytest

test-v:        ## Run tests verbose
	DATABASE_URL="sqlite:///:memory:" pytest -v

test-fast:     ## Stop on first failure
	DATABASE_URL="sqlite:///:memory:" pytest -x

test-cov:      ## Run tests with HTML coverage report
	DATABASE_URL="sqlite:///:memory:" \
		pytest --cov=. --cov-report=html --cov-report=term-missing \
		--cov-omit="tests/*,alembic/*"
	@echo "Coverage → htmlcov/index.html"

# ── Linting ───────────────────────────────────────────────────────────────────
lint:          ## Run ruff linter
	ruff check . --select E,F,W,I --ignore E501

lint-fix:      ## Run ruff and auto-fix safe issues
	ruff check . --select E,F,W,I --ignore E501 --fix

format:        ## Format with black
	black .

format-check:  ## Check formatting (no changes)
	black --check --diff .

# ── Migrations ────────────────────────────────────────────────────────────────
migrate:           ## Apply all pending migrations
	alembic upgrade head

migrate-create:    ## New migration: make migrate-create MSG="description"
	@if [ -z "$(MSG)" ]; then echo "Usage: make migrate-create MSG=\"description\""; exit 1; fi
	alembic revision --autogenerate -m "$(MSG)"

migrate-rollback:  ## Roll back one migration
	alembic downgrade -1

migrate-history:   ## Show migration history
	alembic history --verbose

migrate-status:    ## Show current revision
	alembic current

# ── Docker ────────────────────────────────────────────────────────────────────
docker-up:      ## Start full stack (API + PostgreSQL)
	docker compose up --build -d
	@echo "API  → http://localhost:8000"
	@echo "Docs → http://localhost:8000/docs"

docker-down:    ## Stop containers (keeps DB volume)
	docker compose down

docker-clean:   ## Stop containers and wipe DB volume
	docker compose down -v

docker-logs:    ## Tail API logs
	docker compose logs -f api

docker-rebuild: ## Force rebuild API image
	docker compose up --build --force-recreate api

docker-shell:   ## Shell inside API container
	docker compose exec api /bin/bash

docker-psql:    ## psql inside DB container
	docker compose exec db psql -U taskuser -d taskdb

# ── Utilities ─────────────────────────────────────────────────────────────────
env:    ## Copy .env.example → .env (skips if .env exists)
	@if [ -f .env ]; then echo ".env already exists."; \
	else cp .env.example .env && echo ".env created."; fi

clean:  ## Remove Python cache and test artefacts
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .ruff_cache
	@echo "Cleaned."
