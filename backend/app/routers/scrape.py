"""Scrape control API endpoints.

Standalone mode: launches scrape_real.py as a subprocess (no Celery/Redis).
Progress is communicated via a JSON file on disk that the subprocess updates.

Includes:
  - POST /trigger  — launch a scrape (supports pages param: 1, N, or 0=all)
  - GET  /status   — real-time progress from JSON file
  - GET  /logs     — paginated scrape history
  - GET  /compare  — lightweight inventory comparison (website vs DB)
"""

import json
import math
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ScrapeLog, ScrapeStatus
from app.schemas import (
    ScrapeLogResponse,
    ScrapeLogListResponse,
    ScrapeTriggerRequest,
    ScrapeTriggerResponse,
    ScrapeProgress,
)
from app.auth import verify_api_key

router = APIRouter(prefix="/api/scrape", tags=["Scraping"])

# __file__ is app/routers/scrape.py  →  .parent.parent.parent = backend/
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_PROGRESS_DIR = _BACKEND_DIR / ".scrape_progress"
_PROGRESS_DIR.mkdir(exist_ok=True)

# Track running subprocess PIDs so we don't double-launch
_running_pids: dict[str, int] = {}  # task_id -> pid


def _progress_file(task_id: str) -> Path:
    return _PROGRESS_DIR / f"{task_id}.json"


def _read_progress(task_id: str) -> Optional[dict]:
    p = _progress_file(task_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _is_subprocess_alive(pid: int) -> bool:
    import os
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


# ── Trigger ──────────────────────────────────────────────────────────────────

@router.post("/trigger", response_model=ScrapeTriggerResponse)
async def trigger_scrape(
    body: ScrapeTriggerRequest = ScrapeTriggerRequest(),
    db: AsyncSession = Depends(get_db),
    _api_key=Depends(verify_api_key),
):
    """Launch a scrape job.

    ``pages``:
      - **1** (default) — first page only
      - **N** — first N pages
      - **0** — ALL pages
    """
    # Guard: is a scrape already running?
    result = await db.execute(
        select(ScrapeLog)
        .where(ScrapeLog.status == ScrapeStatus.RUNNING)
        .order_by(desc(ScrapeLog.started_at))
        .limit(1)
    )
    running_log = result.scalar_one_or_none()
    if running_log:
        pid = _running_pids.get(running_log.task_id)
        if pid and _is_subprocess_alive(pid):
            raise HTTPException(
                status_code=409,
                detail=f"A scrape is already running (task_id={running_log.task_id}).",
            )
        running_log.status = ScrapeStatus.FAILED
        running_log.log_output = "Process exited unexpectedly."
        await db.flush()

    task_id = f"scrape-{uuid.uuid4().hex[:12]}"
    pages = body.pages

    new_log = ScrapeLog(
        task_id=task_id,
        status=ScrapeStatus.RUNNING,
        log_output=f"Scrape starting (pages={'all' if pages == 0 else pages})...",
    )
    db.add(new_log)
    await db.flush()

    _progress_file(task_id).write_text(json.dumps({
        "task_id": task_id,
        "status": "running",
        "progress": 0,
        "vehicles_found": 0,
        "vehicles_new": 0,
        "vehicles_updated": 0,
        "current_page": 0,
        "total_pages": 0,
        "message": "Starting scraper...",
    }))

    scraper_script = _BACKEND_DIR / "scrape_real.py"
    if not scraper_script.exists():
        raise HTTPException(status_code=500, detail="scrape_real.py not found.")

    cmd = [sys.executable, str(scraper_script), "--task-id", task_id, "--pages", str(pages)]
    proc = subprocess.Popen(
        cmd, cwd=str(_BACKEND_DIR),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    _running_pids[task_id] = proc.pid

    return ScrapeTriggerResponse(
        task_id=task_id,
        message=f"Scrape job launched (pages={'all' if pages == 0 else pages}).",
    )


# ── Status ───────────────────────────────────────────────────────────────────

@router.get("/status", response_model=ScrapeProgress)
async def get_scrape_status(
    task_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _api_key=Depends(verify_api_key),
):
    if task_id:
        progress = _read_progress(task_id)
        if progress:
            return ScrapeProgress(**progress)

    if task_id:
        query = select(ScrapeLog).where(ScrapeLog.task_id == task_id)
    else:
        query = select(ScrapeLog).order_by(desc(ScrapeLog.started_at)).limit(1)

    result = await db.execute(query)
    log = result.scalar_one_or_none()

    if not log:
        return ScrapeProgress(status="idle", progress=0, message="No scrape has been run yet.")

    pct = {ScrapeStatus.RUNNING: 50, ScrapeStatus.COMPLETED: 100, ScrapeStatus.FAILED: 0}.get(log.status, 0)
    return ScrapeProgress(
        task_id=log.task_id,
        status=log.status.value if log.status else "unknown",
        progress=pct,
        vehicles_found=log.vehicles_found or 0,
        vehicles_new=log.vehicles_new or 0,
        vehicles_updated=log.vehicles_updated or 0,
        message=log.log_output or "",
    )


# ── Logs ─────────────────────────────────────────────────────────────────────

@router.get("/logs", response_model=ScrapeLogListResponse)
async def list_scrape_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _api_key=Depends(verify_api_key),
):
    total = (await db.execute(select(func.count(ScrapeLog.id)))).scalar() or 0
    offset = (page - 1) * per_page
    result = await db.execute(
        select(ScrapeLog).order_by(desc(ScrapeLog.started_at)).offset(offset).limit(per_page)
    )
    logs = result.scalars().all()
    return ScrapeLogListResponse(
        items=[ScrapeLogResponse.model_validate(log) for log in logs],
        total=total, page=page, per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )
