"""FastAPI application entry point with CORS, routers, and static media."""

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.config import settings
from app.database import init_db
from app.routers import vehicles, scrape, stats, api_keys, monitor, history


import re as _re


def _add_utc_to_datetimes(obj):
    """Recursively walk a JSON-serializable structure and append +00:00
    to any ISO 8601 datetime strings that lack timezone info.
    
    This fixes the issue where SQLite returns naive datetimes, Pydantic
    serializes them without tz, and JavaScript's new Date() treats them
    as local time — causing dates to appear shifted for users.
    """
    _ISO_DT_RE = _re.compile(
        r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$'
    )
    if isinstance(obj, dict):
        return {k: _add_utc_to_datetimes(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_add_utc_to_datetimes(v) for v in obj]
    elif isinstance(obj, str) and _ISO_DT_RE.match(obj):
        return obj + "+00:00"
    return obj


class UTCJSONResponse(JSONResponse):
    """JSONResponse that adds UTC timezone to all naive datetime strings."""

    def render(self, content) -> bytes:
        patched = _add_utc_to_datetimes(content)
        return json.dumps(
            patched,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup: create tables
    await init_db()
    # Start the 24/7 background monitor (reads config from DB to decide if active)
    import asyncio
    from app.routers.monitor import _monitor_loop, _monitor_task
    import app.routers.monitor as mon_mod
    mon_mod._monitor_task = asyncio.create_task(_monitor_loop())
    yield
    # Shutdown: cancel the monitor
    if mon_mod._monitor_task and not mon_mod._monitor_task.done():
        mon_mod._monitor_task.cancel()


app = FastAPI(
    title="AutoAvenue Scraper API",
    description=(
        "REST API for scraping and managing vehicle inventory from "
        "Automotive Avenue NJ. Provides endpoints for vehicle listings, "
        "scrape management, statistics, and data export."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    default_response_class=UTCJSONResponse,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount media directory for serving downloaded images
media_path = Path(settings.MEDIA_DIR)
try:
    media_path.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(media_path)), name="media")
except (PermissionError, OSError):
    # Fallback to a local media directory when /app/media is not available
    fallback = Path(__file__).resolve().parent.parent / "media"
    fallback.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(fallback)), name="media")

# Register API routers
app.include_router(vehicles.router)
app.include_router(scrape.router)
app.include_router(stats.router)
app.include_router(api_keys.router)
app.include_router(monitor.router)
app.include_router(history.router)


# ── Frontend SPA serving ─────────────────────────────────────────────────────
# Serve the production React build from ../frontend/dist when it exists.
# This allows running the full stack on a single port.
_frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
_has_frontend = (_frontend_dist / "index.html").is_file()

if _has_frontend:
    # Serve Vite-built assets
    app.mount(
        "/assets",
        StaticFiles(directory=str(_frontend_dist / "assets")),
        name="frontend_assets",
    )

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon():
        return FileResponse(str(_frontend_dist / "favicon.svg"))

    @app.get("/health", tags=["Health"])
    async def health_check():
        """Detailed health check."""
        return {"status": "healthy"}

    # SPA catch-all: any path that is NOT an API/docs/media route → index.html
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(request: Request, full_path: str):
        # Let API, docs, media, and other registered routes through
        if full_path.startswith(("api/", "docs", "redoc", "openapi.json", "media/", "health")):
            return None  # won't reach here because routers are registered first
        return FileResponse(str(_frontend_dist / "index.html"))
else:
    @app.get("/", tags=["Health"])
    async def root():
        """Health check / root endpoint."""
        return {
            "service": "AutoAvenue Scraper API",
            "version": "1.0.0",
            "status": "running",
            "docs": "/docs",
        }

    @app.get("/health", tags=["Health"])
    async def health_check():
        """Detailed health check."""
        return {"status": "healthy"}
