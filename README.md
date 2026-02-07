# AutoAvenue Scraper

A full-stack web application for scraping and managing vehicle inventory from [Automotive Avenue NJ](https://www.automotiveavenuenj.com). Features a React frontend, FastAPI backend, Playwright-powered scraper, Celery background tasks, PostgreSQL database, and Redis cache/broker.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Docker Compose                                                 │
│                                                                 │
│  ┌──────────────┐   REST API   ┌──────────────────────────────┐ │
│  │   Frontend   │◄────────────►│   Backend (FastAPI)          │ │
│  │  React+Vite  │              │   ├── Playwright Scraper     │ │
│  │  +Tailwind   │              │   └── Celery Worker          │ │
│  └──────────────┘              └───────────┬──────────────────┘ │
│                                            │                    │
│                         ┌──────────────────┼──────────────┐     │
│                         ▼                  ▼              │     │
│                  ┌─────────────┐   ┌─────────────┐        │     │
│                  │  PostgreSQL │   │    Redis    │        │     │
│                  │  (Database) │   │   (Broker)  │        │     │
│                  └─────────────┘   └─────────────┘        │     │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites
- Docker and Docker Compose

### Run with Docker

```bash
# Clone and start all services
docker-compose up --build

# Access the application:
# - Frontend:    http://localhost:3100
# - Backend API: http://localhost:8100
# - Swagger UI:  http://localhost:8100/docs
```

### Environment Variables

Copy `.env` and adjust as needed. Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_USER` | Database user | `autoavenue` |
| `POSTGRES_PASSWORD` | Database password | `autoavenue_secret_2026` |
| `DATABASE_URL` | Full DB connection string | see `.env` |
| `REDIS_URL` | Redis connection | `redis://redis:6480/0` |
| `SCRAPE_BASE_URL` | Target site URL | `https://www.automotiveavenuenj.com` |
| `VITE_API_BASE_URL` | API URL for frontend | `http://localhost:8100` |

## Project Structure

```
automotiveavenue/
├── docker-compose.yml           # 5 services: frontend, backend, celery, postgres, redis
├── .env                         # Environment variables
├── backend/
│   ├── Dockerfile               # Python 3.12 + Playwright Chromium
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py              # FastAPI app entry, CORS, routers
│   │   ├── config.py            # Settings via pydantic-settings
│   │   ├── database.py          # SQLAlchemy async engine + session
│   │   ├── models.py            # ORM: Vehicle, ScrapeLog, ApiKey
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── auth.py              # API key authentication dependency
│   │   ├── export.py            # CSV, JSON, PDF export
│   │   ├── tasks.py             # Celery tasks (scrape jobs, scheduling)
│   │   ├── routers/
│   │   │   ├── vehicles.py      # /api/vehicles endpoints
│   │   │   ├── scrape.py        # /api/scrape endpoints
│   │   │   ├── stats.py         # /api/stats endpoint
│   │   │   └── api_keys.py      # API key management
│   │   └── scraper/
│   │       ├── scraper.py       # Playwright scraping logic
│   │       ├── parser.py        # HTML parsing + data extraction
│   │       └── utils.py         # User-agent rotation, delays
│   └── media/                   # Downloaded vehicle images
├── frontend/
│   ├── Dockerfile               # Node 20 build + Nginx serve
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── nginx.conf               # Reverse proxy config
│   └── src/
│       ├── main.tsx
│       ├── App.tsx              # React Router setup
│       ├── api/client.ts        # Axios API client + types
│       ├── components/          # Layout, StatCard, Spinner, Pagination, VehicleCard
│       ├── pages/
│       │   ├── Dashboard.tsx    # Stats overview
│       │   ├── Scrape.tsx       # Scrape control panel
│       │   ├── Inventory.tsx    # Vehicle grid/table + filters
│       │   ├── VehicleDetail.tsx # Single vehicle + image gallery
│       │   └── ApiDocs.tsx      # API docs + key management
│       └── hooks/               # useFetch, usePolling
└── README.md
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/vehicles` | Paginated list with filters & sorting |
| `GET` | `/api/vehicles/search?q=` | Search by VIN, stock#, make, or model |
| `GET` | `/api/vehicles/export?format=` | Export as CSV, JSON, or PDF |
| `GET` | `/api/vehicles/{vin}` | Single vehicle with all fields |
| `POST` | `/api/scrape/trigger` | Start a new scrape job |
| `GET` | `/api/scrape/status` | Real-time scrape progress |
| `GET` | `/api/scrape/logs` | Paginated scrape history |
| `GET` | `/api/stats` | Dashboard statistics |
| `GET` | `/api/keys` | List API keys |
| `POST` | `/api/keys` | Create a new API key |
| `DELETE` | `/api/keys/{id}` | Revoke an API key |

### Query Parameters for `/api/vehicles`

| Parameter | Type | Description |
|-----------|------|-------------|
| `make` | string | Filter by make (fuzzy) |
| `model` | string | Filter by model (fuzzy) |
| `year_min` / `year_max` | int | Year range |
| `price_min` / `price_max` | float | Price range |
| `mileage_min` / `mileage_max` | int | Mileage range |
| `body_style` | string | Filter by body style |
| `sort_by` | string | Sort field (price, year, mileage, make, created_at) |
| `order` | string | asc or desc |
| `page` / `per_page` | int | Pagination (default 1/20) |

### Authentication

External API consumers must pass an API key via the `X-API-Key` header. Keys are managed through the UI or API.

```bash
curl -H "X-API-Key: your_key_here" http://localhost:8100/api/vehicles
```

## Database Schema

### `vehicles` table
- `id`, `stock_number`, `vin` (unique), `year`, `make`, `model`, `trim`
- `price`, `mileage`, `exterior_color`, `interior_color`
- `body_style`, `drivetrain`, `engine`, `transmission`
- `photos` (JSON array), `detail_url`, `is_active`, `created_at`, `updated_at`

### `scrape_logs` table
- `id`, `task_id`, `started_at`, `finished_at`, `status` (running/completed/failed)
- `vehicles_found`, `vehicles_new`, `vehicles_updated`, `vehicles_removed`
- `errors` (JSON), `log_output`

### `api_keys` table
- `id`, `key` (unique), `name`, `is_active`, `created_at`, `last_used_at`, `request_count`

## Scraper Details

- **Engine**: Playwright async API with headless Chromium
- **Anti-detection**: Random user agents, 2-5s delays, navigator.webdriver override
- **Pagination**: Automatic next-page detection and traversal
- **Retry logic**: Up to 3 retries with exponential backoff per page
- **Image download**: Saves to `media/{vin}/` directory
- **Diff detection**: Compares scraped VINs vs DB to track new/updated/removed vehicles
- **Scheduling**: Celery Beat runs daily at 3 AM ET (configurable)

## Development

### Backend (local)
```bash
cd backend
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload --port 8100
```

### Frontend (local)
```bash
cd frontend
npm install
npm run dev
```

### Celery Worker (local)
```bash
cd backend
celery -A app.tasks worker --loglevel=info
```
