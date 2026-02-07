# ╔════════════════════════════════════════════════════════════════════╗
# ║  AutoAvenue Scraper — Developer Makefile                          ║
# ╚════════════════════════════════════════════════════════════════════╝
#
#  make setup      → one-time project bootstrap (venv, deps, DB, Playwright)
#  make dev        → start backend + frontend dev servers
#  make dev-back   → backend only
#  make dev-front  → frontend only
#  make scrape     → run standalone scraper (page 1)
#  make scrape-all → run standalone scraper (all pages)
#  make docker-up  → full Docker Compose stack
#
# ────────────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help
SHELL := /bin/bash

# Paths
ROOT        := $(shell pwd)
BACKEND     := $(ROOT)/backend
FRONTEND    := $(ROOT)/frontend
VENV        := $(BACKEND)/.venv
PYTHON      := $(VENV)/bin/python
PIP         := $(VENV)/bin/pip
UVICORN     := $(VENV)/bin/uvicorn

# ── Help ────────────────────────────────────────────────────────────

.PHONY: help
help: ## Show this help message
	@echo ""
	@echo "  AutoAvenue Scraper — available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ── Setup ───────────────────────────────────────────────────────────

.PHONY: setup
setup: venv install-back install-front db-init ## Full project bootstrap
	@echo ""
	@echo "  ✅  Setup complete.  Run 'make dev' to start developing."
	@echo ""

.PHONY: venv
venv: ## Create Python virtual environment
	@test -d $(VENV) || python3 -m venv $(VENV)
	@echo "  ✅  venv ready at $(VENV)"

.PHONY: install-back
install-back: venv ## Install backend dependencies
	$(PIP) install --upgrade pip -q
	$(PIP) install -r $(BACKEND)/requirements.txt -q
	$(PIP) install -r $(BACKEND)/requirements-dev.txt -q 2>/dev/null || true
	$(PYTHON) -m playwright install chromium --with-deps 2>/dev/null || \
		$(PYTHON) -m playwright install chromium
	@echo "  ✅  Backend deps installed"

.PHONY: install-front
install-front: ## Install frontend dependencies
	cd $(FRONTEND) && npm install --silent
	@echo "  ✅  Frontend deps installed"

.PHONY: db-init
db-init: venv ## Initialize database tables
	cd $(BACKEND) && $(PYTHON) -m app.database --init
	@echo "  ✅  Database initialized"

# ── Development ─────────────────────────────────────────────────────

.PHONY: dev
dev: ## Start backend + frontend (parallel)
	@echo "  🚀  Starting backend on :8100 and frontend on :5273 ..."
	@trap 'kill 0' SIGINT; \
		$(MAKE) dev-back & \
		$(MAKE) dev-front & \
		wait

.PHONY: dev-back
dev-back: ## Start backend (uvicorn, auto-reload)
	cd $(BACKEND) && $(UVICORN) app.main:app \
		--host 0.0.0.0 --port 8100 --reload \
		--reload-dir app

.PHONY: dev-front
dev-front: ## Start frontend (Vite dev server)
	cd $(FRONTEND) && npm run dev

# ── Scraping ────────────────────────────────────────────────────────

.PHONY: scrape
scrape: ## Run scraper (page 1 only)
	cd $(BACKEND) && $(PYTHON) scrape_real.py --pages 1

.PHONY: scrape-all
scrape-all: ## Run scraper (ALL pages, ~740 vehicles)
	cd $(BACKEND) && $(PYTHON) scrape_real.py --pages 0

.PHONY: scrape-n
scrape-n: ## Run scraper for N pages (usage: make scrape-n N=5)
	cd $(BACKEND) && $(PYTHON) scrape_real.py --pages $(N)

# ── Code Quality ────────────────────────────────────────────────────

.PHONY: lint
lint: ## Run linter (ruff)
	cd $(BACKEND) && $(VENV)/bin/ruff check app/ scrape_real.py

.PHONY: format
format: ## Auto-format code (ruff)
	cd $(BACKEND) && $(VENV)/bin/ruff format app/ scrape_real.py

.PHONY: typecheck
typecheck: ## TypeScript type-check (frontend)
	cd $(FRONTEND) && npx tsc --noEmit

.PHONY: test
test: ## Run backend tests
	cd $(BACKEND) && $(PYTHON) -m pytest tests/ -v

# ── Build ───────────────────────────────────────────────────────────

.PHONY: build-front
build-front: ## Build frontend for production
	cd $(FRONTEND) && npm run build

.PHONY: build
build: build-front ## Build everything

# ── Docker ──────────────────────────────────────────────────────────

.PHONY: docker-up
docker-up: ## Start full stack with Docker Compose
	docker compose up --build

.PHONY: docker-down
docker-down: ## Stop Docker Compose
	docker compose down

.PHONY: docker-logs
docker-logs: ## Tail Docker Compose logs
	docker compose logs -f

.PHONY: docker-clean
docker-clean: ## Remove Docker volumes + images
	docker compose down -v --rmi local

# ── Database ────────────────────────────────────────────────────────

.PHONY: db-reset
db-reset: ## Drop and recreate database (SQLite only)
	rm -f $(BACKEND)/autoavenue.db
	$(MAKE) db-init
	@echo "  ✅  Database reset"

.PHONY: db-shell
db-shell: ## Open SQLite shell
	sqlite3 $(BACKEND)/autoavenue.db

# ── Utilities ───────────────────────────────────────────────────────

.PHONY: clean
clean: ## Remove generated files (caches, builds)
	find $(BACKEND) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find $(BACKEND) -name '*.pyc' -delete 2>/dev/null || true
	rm -rf $(FRONTEND)/dist $(FRONTEND)/node_modules/.cache
	rm -rf $(BACKEND)/.scrape_progress $(BACKEND)/app/.scrape_progress
	@echo "  ✅  Cleaned"

.PHONY: clean-all
clean-all: clean ## Remove everything (including venv, node_modules)
	rm -rf $(VENV) $(FRONTEND)/node_modules
	@echo "  ✅  Deep cleaned (run 'make setup' to restore)"

.PHONY: health
health: ## Check if backend is running
	@curl -sf http://localhost:8100/health | python3 -m json.tool 2>/dev/null || \
		echo "  ❌  Backend not running on :8100"

.PHONY: status
status: ## Show project status
	@echo ""
	@echo "  📁  Project root: $(ROOT)"
	@echo "  🐍  Python venv:  $(VENV)"
	@echo ""
	@echo "  Backend:"
	@curl -sf http://localhost:8100/health > /dev/null 2>&1 && \
		echo "    ✅  Running on :8100" || echo "    ⏹  Not running"
	@echo ""
	@echo "  Frontend:"
	@curl -sf http://localhost:5273 > /dev/null 2>&1 && \
		echo "    ✅  Running on :5273" || echo "    ⏹  Not running"
	@echo ""
	@test -f $(BACKEND)/autoavenue.db && \
		echo "  Database: ✅  $(BACKEND)/autoavenue.db" || \
		echo "  Database: ⏹  Not initialized (run 'make db-init')"
	@echo ""
