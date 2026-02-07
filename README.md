# AutoAvenue Scraper

Inventory scraper and management dashboard for [Automotive Avenue NJ](https://www.automotiveavenuenj.com) (powered by ebizautos).

| Component | Stack | Port |
|-----------|-------|------|
| Backend   | FastAPI, SQLAlchemy, Playwright | `:8100` |
| Frontend  | React 18, Vite, Tailwind CSS | `:5273` (dev) / `:3100` (Docker) |
| Database  | SQLite (dev) / PostgreSQL 16 (Docker) | `:5533` |
| Queue     | Redis + Celery (optional) | `:6480` |

---

## Quick Start (Local)

```bash
# 1. Clone & enter
git clone https://github.com/mayo3030/automotivenj252026.git
cd automotivenj252026

# 2. One-command setup (venv, deps, Playwright, DB)
bash scripts/setup.sh

# 3. Start developing
make dev          # backend :8100 + frontend :5273
```

Open [http://localhost:5273](http://localhost:5273) — the UI proxies `/api/*` to the backend automatically.

> **Swagger docs:** [http://localhost:8100/docs](http://localhost:8100/docs)

---

## Quick Start (Docker)

```bash
cp .env.example .env
# Uncomment the PostgreSQL lines in .env, then:
docker compose up --build

# With Celery workers (scheduled scrapes):
docker compose --profile celery up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3100 |
| Backend API | http://localhost:8100 |
| Swagger UI | http://localhost:8100/docs |

---

## Project Structure

```
automotivenj252026/
├── Makefile                     # Dev commands (make help)
├── docker-compose.yml           # Full stack: pg, redis, backend, frontend, celery
├── .env.example                 # Copy to .env — all config documented inline
├── scripts/
│   ├── setup.sh                 # One-time bootstrap (venv, deps, DB, Playwright)
│   └── dev.sh                   # Start dev servers (both/back/front)
│
├── backend/
│   ├── Dockerfile               # Python 3.12 + Playwright Chromium
│   ├── requirements.txt         # Production deps (pinned)
│   ├── requirements-dev.txt     # Dev/test deps (ruff, pytest, mypy)
│   ├── pytest.ini               # Test runner config
│   ├── scrape_real.py           # Standalone CLI scraper (Playwright)
│   │
│   ├── app/
│   │   ├── main.py              # FastAPI app — CORS, lifespan, router registration
│   │   ├── config.py            # pydantic-settings: DB, Redis, scraper config
│   │   ├── database.py          # SQLAlchemy async engine, session, init_db()
│   │   ├── models.py            # ORM models (7 tables — see DB Schema below)
│   │   ├── schemas.py           # Pydantic request/response models
│   │   ├── auth.py              # API key auth dependency (X-API-Key header)
│   │   ├── export.py            # CSV, JSON, PDF export helpers
│   │   ├── tasks.py             # Celery tasks + daily beat schedule
│   │   │
│   │   ├── routers/
│   │   │   ├── vehicles.py      # /api/vehicles — CRUD, search, export
│   │   │   ├── scrape.py        # /api/scrape  — trigger, status, logs
│   │   │   ├── monitor.py       # /api/monitor — 24/7 auto-sync, compare, progress
│   │   │   ├── stats.py         # /api/stats   — dashboard aggregates
│   │   │   ├── history.py       # /api/history — price history, change logs
│   │   │   └── api_keys.py      # /api/keys    — key management
│   │   │
│   │   └── scraper/
│   │       ├── scraper.py       # Playwright browser automation (AutoAvenueScaper)
│   │       ├── parser.py        # HTML/JSON-LD extraction
│   │       └── utils.py         # UA rotation, delays, retry, dealer-frame removal
│   │
│   ├── media/                   # Downloaded vehicle photos: media/{VIN}/001.jpg
│   └── tests/
│       └── test_health.py       # Smoke tests (health, vehicles, stats)
│
└── frontend/
    ├── Dockerfile               # Node 20 build → Nginx serve
    ├── package.json
    ├── vite.config.ts           # Dev server :5273, proxy /api → :8100
    ├── tailwind.config.js       # Custom "brand" color palette
    ├── nginx.conf               # Production reverse proxy
    ├── serve.py                 # Lightweight SPA server (optional)
    │
    └── src/
        ├── main.tsx             # React entry point
        ├── App.tsx              # Routes: /, /scrape, /history, /logs, /inventory, /api-docs
        ├── index.css            # Tailwind base + custom components
        │
        ├── api/
        │   └── client.ts        # Axios client, TypeScript models, all API functions
        │
        ├── components/
        │   ├── Layout.tsx       # Sidebar nav + main content area
        │   ├── StatCard.tsx     # Dashboard stat cards
        │   ├── VehicleCard.tsx  # Vehicle grid card
        │   ├── Pagination.tsx   # Page navigation
        │   └── Spinner.tsx      # Loading spinner
        │
        ├── pages/
        │   ├── Dashboard.tsx    # Stats overview (totals, makes, last scrape)
        │   ├── Scrape.tsx       # 2-step workflow: Inventory Sync → Scrape Control
        │   ├── Inventory.tsx    # Vehicle grid/table with filters + sorting
        │   ├── VehicleDetail.tsx# Single vehicle detail + photo gallery
        │   ├── History.tsx      # Price history + change timeline
        │   ├── Logs.tsx         # System logs viewer
        │   └── ApiDocs.tsx      # API docs + key management
        │
        └── hooks/
            ├── useFetch.ts      # Generic data fetcher
            └── usePolling.ts    # Interval-based polling
```

---

## Make Commands

```bash
make help          # Show all commands

# Setup
make setup         # Full bootstrap (venv, deps, DB, Playwright)
make install-back  # Backend deps only
make install-front # Frontend deps only
make db-init       # Initialize database tables

# Development
make dev           # Start both servers (parallel)
make dev-back      # Backend only (uvicorn --reload)
make dev-front     # Frontend only (Vite HMR)

# Scraping
make scrape        # Scrape page 1 only
make scrape-all    # Scrape ALL pages (~740 vehicles)
make scrape-n N=5  # Scrape N pages

# Code Quality
make lint          # Ruff linter
make format        # Ruff formatter
make typecheck     # TypeScript type-check
make test          # Pytest

# Build & Deploy
make build         # Build frontend for production
make docker-up     # Docker Compose up
make docker-down   # Docker Compose down

# Database
make db-reset      # Drop and recreate SQLite DB
make db-shell      # Open SQLite shell

# Utilities
make health        # Check backend health
make status        # Show project status
make clean         # Remove caches/builds
make clean-all     # Remove everything (venv, node_modules)
```

---

## How the Scraper Works

### Target Site

Automotive Avenue NJ uses the **ebizautos** dealer platform:
- **Base URL:** `https://autoavenj.ebizautos.com`
- **Inventory page 1 (vanity):** `/used-cars.aspx`
- **Paginated:** `/inventory.aspx?_vstatus=3&_used=true&_page=N`
- **~74 pages, ~740 vehicles, 10 per page**

### Two-Step Workflow (UI: `/scrape`)

1. **Step 1 — Inventory Sync Check**
   - Playwright visits inventory pages (site blocks plain HTTP with 202 empty body)
   - Extracts VINs, year/make/model, prices from JSON-LD + detail links
   - Compares against local DB: matched, new on site, removed, price changed
   - Real-time progress via `/api/monitor/sync-progress` (polled every 2s)

2. **Step 2 — Targeted Scrape**
   - Only scrapes new/changed vehicles (not the full inventory again)
   - Visits each detail page for full specs + all photo URLs
   - Downloads images to `backend/media/{VIN}/`
   - Updates DB with new/changed records; marks removed VINs as inactive

### 24/7 Auto-Monitor

Background async loop within FastAPI (no Celery needed):
- Configurable interval (5 min – 24 hr) and page range
- If drift detected → auto-triggers a full scrape
- Logs all activity to `system_logs` table

### Standalone CLI Scraper

```bash
# From backend/ with venv activated:
python scrape_real.py                           # page 1
python scrape_real.py --pages 5                 # first 5 pages
python scrape_real.py --pages 0                 # ALL pages
python scrape_real.py --task-id scrape-custom   # with progress tracking
```

---

## API Endpoints

### Vehicles
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/vehicles` | Paginated list (filters: make, model, year, price, mileage, body_style) |
| `GET`  | `/api/vehicles/search?q=` | Search by VIN, stock#, make, model |
| `GET`  | `/api/vehicles/export?format=csv\|json\|pdf` | Bulk export |
| `GET`  | `/api/vehicles/{vin}` | Single vehicle detail |

### Scrape Control
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/scrape/trigger` | Start scrape (body: `{pages: N}`, 0=all) |
| `GET`  | `/api/scrape/status` | Real-time scrape progress |
| `GET`  | `/api/scrape/logs` | Paginated scrape history |

### Monitor / Sync
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/monitor/compare?pages=N` | Manual inventory comparison (Playwright) |
| `GET`  | `/api/monitor/sync-progress` | Real-time sync check progress |
| `GET`  | `/api/monitor/config` | Monitor settings |
| `PUT`  | `/api/monitor/config` | Update monitor settings |
| `GET`  | `/api/monitor/logs` | System event logs |

### Stats & History
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/stats` | Dashboard aggregates |
| `GET`  | `/api/history/vehicles` | All vehicles with price history summary |
| `GET`  | `/api/history/vehicles/{vin}` | Full history for one vehicle |

### API Keys
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/keys` | List API keys |
| `POST` | `/api/keys` | Create key (body: `{name: "..."}`) |
| `DELETE`| `/api/keys/{id}` | Revoke key |

**Authentication:** External consumers use `X-API-Key` header. Internal frontend requests (localhost origins) are auto-allowed.

---

## Database Schema

7 tables managed by SQLAlchemy ORM (`backend/app/models.py`):

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `vehicles` | Inventory records | vin (unique), year, make, model, price, mileage, photos (JSON), is_active |
| `scrape_logs` | Scrape run history | task_id, status, vehicles_found/new/updated/removed |
| `api_keys` | API authentication | key (unique), name, is_active, request_count |
| `system_logs` | Monitor event log | timestamp, level, source, message, details |
| `monitor_config` | Singleton config | enabled, interval_minutes, pages_to_scrape |
| `vehicle_price_history` | Price tracking | vin, price, recorded_at, source |
| `vehicle_change_log` | Field-level audit | vin, change_type, field_name, old_value, new_value |

---

## Environment Configuration

Copy `.env.example` to `.env`. All variables are documented inline.

| Variable | Default (Local Dev) | Notes |
|----------|-------------------|-------|
| `DATABASE_URL` | `sqlite+aiosqlite:///autoavenue.db` | Switch to PostgreSQL for Docker |
| `REDIS_URL` | `redis://localhost:6480/0` | Only needed for Celery |
| `SECRET_KEY` | placeholder | Change in production |
| `SCRAPE_BASE_URL` | `https://autoavenj.ebizautos.com` | Target dealer site |
| `SCRAPE_DELAY_MIN/MAX` | `2` / `5` | Politeness delay range (seconds) |
| `MEDIA_DIR` | `media` | Relative to backend/ |
| `VITE_API_BASE_URL` | `http://localhost:8100` | Vite dev proxy target |

---

## Development Workflow

### Daily Development
```bash
make dev                    # start both servers
# Edit code — backend auto-reloads, frontend has HMR
# Open http://localhost:5273
```

### Running a Scrape
```bash
# Option 1: From the UI
# Go to /scrape → Step 1: Sync Check → Step 2: Scrape

# Option 2: From the API
curl -X POST http://localhost:8100/api/scrape/trigger \
  -H "Content-Type: application/json" \
  -d '{"pages": 1}'

# Option 3: CLI
make scrape                 # page 1
make scrape-all             # all pages
```

### Adding a New API Endpoint
1. Add Pydantic schema in `backend/app/schemas.py`
2. Add route in the appropriate `backend/app/routers/*.py`
3. If new table needed, add model in `backend/app/models.py`
4. Import router in `backend/app/main.py` (if new file)
5. Add corresponding API function in `frontend/src/api/client.ts`

### Adding a New Frontend Page
1. Create page component in `frontend/src/pages/NewPage.tsx`
2. Add route in `frontend/src/App.tsx`
3. Add nav link in `frontend/src/components/Layout.tsx`

---

## Key Technical Decisions

| Decision | Rationale |
|----------|-----------|
| **Playwright over httpx** | Site returns `202 + empty body` for plain HTTP; requires full browser rendering |
| **SQLite for dev** | Zero setup; `aiosqlite` driver for async; swap to PostgreSQL via env var |
| **Background monitor (no Celery)** | AsyncIO task within FastAPI; simpler deployment; Celery optional for heavy workloads |
| **Dealer-frame removal** | Vehicle photos have logo overlays; auto-detected and cropped via Pillow/numpy |
| **JSON-LD extraction** | ebizautos embeds structured Vehicle data in `<script type="application/ld+json">` |
| **2-step workflow** | Compare first, scrape only what changed; avoids unnecessary load on target site |
