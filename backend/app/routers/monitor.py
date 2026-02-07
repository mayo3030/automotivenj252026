"""24/7 Auto-Monitor and Inventory Comparison endpoints.

The monitor runs as a background asyncio task inside the FastAPI process.
It periodically:
  1. Quick-checks the website to count vehicles + grab VINs (no Playwright needed).
  2. Compares with the local DB.
  3. If differences are found, auto-triggers a full scrape.
  4. Logs everything to system_logs.
"""

import asyncio
import json
import math
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, AsyncSessionLocal
from app.models import (
    Vehicle, ScrapeLog, ScrapeStatus,
    SystemLog, LogLevel, MonitorConfig,
)
from app.schemas import (
    MonitorConfigResponse, MonitorConfigUpdate,
    SystemLogResponse, SystemLogListResponse,
    InventoryComparison, InventoryComparisonVehicle,
)
from app.auth import verify_api_key

router = APIRouter(prefix="/api/monitor", tags=["Monitor"])

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_PROGRESS_DIR = _BACKEND_DIR / ".scrape_progress"
_PROGRESS_DIR.mkdir(exist_ok=True)

BASE = "https://autoavenj.ebizautos.com"
INVENTORY_URL = f"{BASE}/used-cars.aspx"
# The real paginated inventory endpoint (the vanity URL only shows page 1)
INVENTORY_PAGINATED_URL = f"{BASE}/inventory.aspx?_vstatus=3&_used=true"

# ── Background monitor task handle ───────────────────────────────────────────
_monitor_task: Optional[asyncio.Task] = None

# ── Sync progress tracking ───────────────────────────────────────────────────
_SYNC_PROGRESS_FILE = _BACKEND_DIR / ".sync_progress.json"

def _write_sync_progress(data: dict):
    """Write sync check progress to a JSON file for frontend polling."""
    try:
        _SYNC_PROGRESS_FILE.write_text(json.dumps(data))
    except OSError:
        pass

def _read_sync_progress() -> dict | None:
    """Read current sync progress."""
    try:
        if _SYNC_PROGRESS_FILE.exists():
            return json.loads(_SYNC_PROGRESS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return None

def _clear_sync_progress():
    """Remove the sync progress file."""
    try:
        if _SYNC_PROGRESS_FILE.exists():
            _SYNC_PROGRESS_FILE.unlink()
    except OSError:
        pass


# ── Helper: log to system_logs ───────────────────────────────────────────────

async def _write_log(
    level: LogLevel, source: str, message: str,
    details: dict | None = None, task_id: str | None = None,
):
    async with AsyncSessionLocal() as session:
        session.add(SystemLog(
            level=level, source=source, message=message,
            details=details or {}, task_id=task_id,
        ))
        await session.commit()


# ── Helper: quick inventory check via Playwright ────────────────────────────

async def _quick_website_check(max_pages: int = 0, track_progress: bool = False) -> list[dict]:
    """Fetch ALL inventory pages via Playwright to get accurate vehicle list.

    The website blocks plain HTTP requests (returns 202 empty body).
    Playwright with a real browser engine is required.

    If track_progress is True, writes progress to a JSON file that the
    frontend can poll via GET /api/monitor/sync-progress.

    The website uses ``inventory.aspx?_vstatus=3&_used=true&_page=N`` for
    real server-side pagination (10 vehicles per page).

    Returns list of dicts: vin, year, make, model, price, detail_url.
    """
    from playwright.async_api import async_playwright

    all_vehicles: list[dict] = []
    seen_vins: set[str] = set()
    page_num = 1

    def _update_progress(msg: str, pg: int = 0, found: int = 0, total_est: int = 0):
        if track_progress:
            _write_sync_progress({
                "status": "scanning",
                "message": msg,
                "current_page": pg,
                "vehicles_found": found,
                "total_pages_estimate": total_est,
            })

    pw = None
    browser = None
    try:
        _update_progress("Launching browser...", 0, 0, 0)

        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            java_script_enabled=True,
            ignore_https_errors=True,
        )
        page = await ctx.new_page()

        total_pages_est = 0

        while True:
            url = f"{INVENTORY_PAGINATED_URL}&_page={page_num}"
            _update_progress(
                f"Scanning page {page_num}...",
                page_num, len(all_vehicles), total_pages_est,
            )
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_load_state("networkidle", timeout=30000)
                await asyncio.sleep(1.0)

                # Extract detail links + JSON-LD data from the page
                page_data = await page.evaluate(r"""
                    () => {
                        const results = [];
                        // Get detail links
                        const links = document.querySelectorAll('a[href*="details-"]');
                        const uniqueUrls = [...new Set([...links].map(a => a.href))];
                        for (const href of uniqueUrls) {
                            results.push(href);
                        }

                        // Check for JSON-LD vehicle data for prices
                        let jsonLdVehicles = [];
                        const ldScript = document.querySelector('#application-ld_json-vehicle');
                        if (ldScript) {
                            try {
                                const data = JSON.parse(ldScript.textContent);
                                jsonLdVehicles = Array.isArray(data) ? data : [data];
                            } catch {}
                        }

                        // Check if next page exists
                        const nextPageLinks = document.querySelectorAll('a[href*="_page="]');
                        let hasNext = false;
                        const pageNums = [];
                        for (const a of nextPageLinks) {
                            const m = a.href.match(/_page=(\d+)/);
                            if (m) pageNums.push(parseInt(m[1]));
                        }

                        return { detailUrls: results, jsonLdVehicles, pageNums };
                    }
                """)

                detail_urls = page_data.get("detailUrls", [])
                json_ld_vehicles = page_data.get("jsonLdVehicles", [])
                page_nums_found = page_data.get("pageNums", [])

                # Update total pages estimate from pagination links
                if page_nums_found:
                    total_pages_est = max(total_pages_est, max(page_nums_found))

                if not detail_urls:
                    break  # past last page

                # Build a VIN->price map from JSON-LD
                ld_price_map: dict[str, str] = {}
                for jv in json_ld_vehicles:
                    vin_ld = (jv.get("vehicleIdentificationNumber") or "").upper()
                    offers = jv.get("offers", [])
                    if offers:
                        offer = offers[0] if isinstance(offers, list) else offers
                        price_raw = str(offer.get("price", ""))
                        price_clean = re.sub(r'[^\d.]', '', price_raw)
                        if vin_ld and price_clean:
                            ld_price_map[vin_ld] = price_clean

                page_found = 0
                for link in detail_urls:
                    norm = link.rstrip("/")
                    if norm.startswith("//"):
                        norm = "https:" + norm

                    m = re.search(
                        r'/details-(\d{4})-([^-]+)-([^-]+)-([^-]*)-used-([A-HJ-NPR-Z0-9]{17})',
                        norm, re.IGNORECASE,
                    )
                    if not m:
                        continue
                    vin = m.group(5).upper()
                    if vin in seen_vins:
                        continue
                    seen_vins.add(vin)

                    year = m.group(1)
                    make = m.group(2).replace("_", " ").replace("~", " ").title()
                    model = m.group(3).replace("_", " ").replace("~", " ").title()
                    price = ld_price_map.get(vin, "")

                    all_vehicles.append({
                        "vin": vin,
                        "year": year,
                        "make": make,
                        "model": model,
                        "price": price,
                        "detail_url": norm,
                    })
                    page_found += 1

                _update_progress(
                    f"Page {page_num}: found {page_found} vehicles ({len(all_vehicles)} total)",
                    page_num, len(all_vehicles), total_pages_est,
                )

                if page_found == 0:
                    break  # no new vehicles — past the last page

                # Determine if there's a next page
                has_next = (page_num + 1) in page_nums_found
                if not has_next and page_nums_found:
                    max_page = max(page_nums_found)
                    if page_num < max_page:
                        has_next = True

                if not has_next:
                    break

                page_num += 1
                if max_pages and page_num > max_pages:
                    break

                await asyncio.sleep(0.5)

            except Exception as e:
                await _write_log(LogLevel.ERROR, "monitor", f"Page {page_num} fetch error: {e}")
                break

    except Exception as e:
        await _write_log(LogLevel.ERROR, "monitor", f"Playwright launch error: {e}")
    finally:
        try:
            if browser:
                await browser.close()
            if pw:
                await pw.stop()
        except Exception:
            pass

    await _write_log(
        LogLevel.INFO, "monitor",
        f"Website scan complete: found {len(all_vehicles)} vehicles across {page_num} page(s)",
    )

    return all_vehicles


# ── Inventory comparison ─────────────────────────────────────────────────────

async def _compare_inventory(max_pages: int = 0, track_progress: bool = False) -> dict:
    """Compare website inventory against local DB. Returns comparison dict.

    For large inventories (hundreds of vehicles) this does a VIN-based
    comparison first (fast — only listing page scraping required).
    Vehicles that exist in both are compared on VIN only; price comparison
    requires visiting every detail page which is too slow for 700+ cars
    during a quick check.  Price changes will be detected during the actual
    scrape.
    """
    website_vehicles = await _quick_website_check(max_pages, track_progress=track_progress)
    if track_progress:
        _write_sync_progress({
            "status": "comparing",
            "message": f"Comparing {len(website_vehicles)} website vehicles with local database...",
            "current_page": 0,
            "vehicles_found": len(website_vehicles),
            "total_pages_estimate": 0,
        })

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Vehicle).where(Vehicle.is_active == True)  # noqa
        )
        local_vehicles = {v.vin: v for v in result.scalars().all()}

    website_vins = {v["vin"] for v in website_vehicles}
    website_map = {v["vin"]: v for v in website_vehicles}
    local_vins = set(local_vehicles.keys())

    comparison_list: list[InventoryComparisonVehicle] = []
    matched = 0
    changed = 0

    # Matched vehicles (exist on both website and DB)
    for vin in sorted(website_vins & local_vins):
        wv = website_map[vin]
        lv = local_vehicles[vin]
        display_year = lv.year or (int(wv.get("year") or 0) or None)
        display_make = lv.make or wv.get("make")
        display_model = lv.model or wv.get("model")
        display_price = f"${lv.price:,.0f}" if lv.price else None

        comparison_list.append(InventoryComparisonVehicle(
            vin=vin, year=display_year,
            make=display_make, model=display_model,
            price=display_price,
            status="match", detail_url=wv.get("detail_url"),
        ))
        matched += 1

    # New on website (missing locally)
    for vin in sorted(website_vins - local_vins):
        wv = website_map[vin]
        comparison_list.append(InventoryComparisonVehicle(
            vin=vin, year=int(wv.get("year") or 0) or None,
            make=wv.get("make"), model=wv.get("model"),
            price=None,
            status="missing_local", detail_url=wv.get("detail_url"),
        ))

    # Extra in DB (no longer on website = removed)
    for vin in sorted(local_vins - website_vins):
        lv = local_vehicles[vin]
        comparison_list.append(InventoryComparisonVehicle(
            vin=vin, year=lv.year, make=lv.make, model=lv.model,
            price=f"${lv.price:,.0f}" if lv.price else None,
            status="missing_remote",
        ))

    missing_locally = len(website_vins - local_vins)
    extra_locally = len(local_vins - website_vins)

    return InventoryComparison(
        website_count=len(website_vehicles),
        local_count=len(local_vehicles),
        matched=matched, missing_locally=missing_locally,
        extra_locally=extra_locally, changed=changed,
        vehicles=comparison_list,
        checked_at=datetime.now(timezone.utc),
        pages_checked=max_pages or 99,
    )


# ── Background monitor loop ─────────────────────────────────────────────────

async def _monitor_loop():
    """Runs forever. Checks inventory on a configurable interval."""
    await _write_log(LogLevel.INFO, "monitor", "Background monitor started")

    while True:
        try:
            # Read config from DB
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(MonitorConfig).where(MonitorConfig.id == 1))
                config = result.scalar_one_or_none()
                if not config:
                    config = MonitorConfig(id=1, enabled=False, interval_minutes=30)
                    session.add(config)
                    await session.commit()

            if not config.enabled:
                await asyncio.sleep(15)
                continue

            interval = max(config.interval_minutes, 5)
            pages = config.pages_to_scrape

            await _write_log(LogLevel.INFO, "monitor", f"Running inventory check (pages={'all' if pages == 0 else pages})...")

            comparison = await _compare_inventory(pages)

            summary = (
                f"Website: {comparison.website_count} | Local: {comparison.local_count} | "
                f"Matched: {comparison.matched} | Missing: {comparison.missing_locally} | "
                f"Extra: {comparison.extra_locally} | Changed: {comparison.changed}"
            )

            # Update config with last check info
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(MonitorConfig).where(MonitorConfig.id == 1))
                cfg = result.scalar_one_or_none()
                if cfg:
                    cfg.last_check_at = datetime.now(timezone.utc)
                    cfg.last_check_result = summary
                    await session.commit()

            needs_scrape = comparison.missing_locally > 0 or comparison.extra_locally > 0 or comparison.changed > 0

            if needs_scrape:
                await _write_log(
                    LogLevel.WARNING, "monitor",
                    f"Inventory drift detected! {summary}. Auto-triggering scrape...",
                    details={"missing": comparison.missing_locally, "extra": comparison.extra_locally, "changed": comparison.changed},
                )
                # Auto-trigger a scrape
                task_id = f"auto-{uuid.uuid4().hex[:12]}"
                async with AsyncSessionLocal() as session:
                    session.add(ScrapeLog(
                        task_id=task_id, status=ScrapeStatus.RUNNING,
                        log_output=f"Auto-scrape triggered by monitor. {summary}",
                    ))
                    await session.commit()

                _PROGRESS_DIR.mkdir(exist_ok=True)
                (Path(_PROGRESS_DIR) / f"{task_id}.json").write_text(json.dumps({
                    "task_id": task_id, "status": "running", "progress": 0,
                    "vehicles_found": 0, "vehicles_new": 0, "vehicles_updated": 0,
                    "current_page": 0, "total_pages": 0,
                    "message": "Auto-scrape triggered by monitor...",
                }))

                scraper = _BACKEND_DIR / "scrape_real.py"
                subprocess.Popen(
                    [sys.executable, str(scraper), "--task-id", task_id, "--pages", str(pages)],
                    cwd=str(_BACKEND_DIR),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                await _write_log(LogLevel.INFO, "monitor", f"Auto-scrape launched: {task_id}")
            else:
                await _write_log(LogLevel.INFO, "monitor", f"Inventory up to date. {summary}")

            # Sleep for the configured interval
            await asyncio.sleep(interval * 60)

        except asyncio.CancelledError:
            await _write_log(LogLevel.INFO, "monitor", "Monitor stopped")
            return
        except Exception as e:
            await _write_log(LogLevel.ERROR, "monitor", f"Monitor error: {e}")
            await asyncio.sleep(60)  # backoff on error


# ── API Endpoints ────────────────────────────────────────────────────────────

@router.get("/config", response_model=MonitorConfigResponse)
async def get_monitor_config(
    db: AsyncSession = Depends(get_db),
    _api_key=Depends(verify_api_key),
):
    result = await db.execute(select(MonitorConfig).where(MonitorConfig.id == 1))
    config = result.scalar_one_or_none()
    if not config:
        config = MonitorConfig(id=1, enabled=False, interval_minutes=30)
        db.add(config)
        await db.flush()
    return MonitorConfigResponse.model_validate(config)


@router.put("/config", response_model=MonitorConfigResponse)
async def update_monitor_config(
    body: MonitorConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _api_key=Depends(verify_api_key),
):
    global _monitor_task

    result = await db.execute(select(MonitorConfig).where(MonitorConfig.id == 1))
    config = result.scalar_one_or_none()
    if not config:
        config = MonitorConfig(id=1)
        db.add(config)

    if body.enabled is not None:
        config.enabled = body.enabled
    if body.interval_minutes is not None:
        config.interval_minutes = body.interval_minutes
    if body.pages_to_scrape is not None:
        config.pages_to_scrape = body.pages_to_scrape
    await db.flush()

    # Start or stop the background loop
    if config.enabled:
        if _monitor_task is None or _monitor_task.done():
            _monitor_task = asyncio.create_task(_monitor_loop())
            await _write_log(LogLevel.INFO, "monitor", "Monitor enabled and started")
    else:
        if _monitor_task and not _monitor_task.done():
            _monitor_task.cancel()
            _monitor_task = None
            await _write_log(LogLevel.INFO, "monitor", "Monitor disabled and stopped")

    return MonitorConfigResponse.model_validate(config)


@router.get("/compare", response_model=InventoryComparison)
async def compare_inventory(
    pages: int = Query(0, ge=0, description="Pages to check (0 = all)"),
    _api_key=Depends(verify_api_key),
):
    """Quick inventory comparison: website vs local DB."""
    await _write_log(LogLevel.INFO, "monitor", f"Manual inventory comparison (pages={'all' if pages == 0 else pages})")

    # Clear old progress and track the new scan
    _clear_sync_progress()
    _write_sync_progress({"status": "starting", "message": "Initializing sync check...", "current_page": 0, "vehicles_found": 0, "total_pages_estimate": 0})

    try:
        comparison = await _compare_inventory(pages, track_progress=True)
    finally:
        _clear_sync_progress()

    # Update MonitorConfig so the Last Check section stays accurate
    summary = (
        f"Website: {comparison.website_count} | Local: {comparison.local_count} | "
        f"Matched: {comparison.matched} | Missing: {comparison.missing_locally} | "
        f"Extra: {comparison.extra_locally} | Changed: {comparison.changed}"
    )
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MonitorConfig).where(MonitorConfig.id == 1))
        cfg = result.scalar_one_or_none()
        if cfg:
            cfg.last_check_at = datetime.now(timezone.utc)
            cfg.last_check_result = summary
            await session.commit()

    return comparison


@router.get("/sync-progress")
async def get_sync_progress(
    _api_key=Depends(verify_api_key),
):
    """Poll real-time progress of a running sync check."""
    progress = _read_sync_progress()
    if not progress:
        return {"status": "idle", "message": "No sync check running", "current_page": 0, "vehicles_found": 0, "total_pages_estimate": 0}
    return progress


# ── System Logs ──────────────────────────────────────────────────────────────

@router.get("/logs", response_model=SystemLogListResponse)
async def list_system_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    level: Optional[str] = Query(None, description="Filter by level: debug,info,warning,error,critical"),
    source: Optional[str] = Query(None, description="Filter by source: scraper,monitor,api"),
    db: AsyncSession = Depends(get_db),
    _api_key=Depends(verify_api_key),
):
    query = select(SystemLog)
    count_query = select(func.count(SystemLog.id))

    if level:
        try:
            lv = LogLevel(level.lower())
            query = query.where(SystemLog.level == lv)
            count_query = count_query.where(SystemLog.level == lv)
        except ValueError:
            pass
    if source:
        query = query.where(SystemLog.source == source)
        count_query = count_query.where(SystemLog.source == source)

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * per_page
    result = await db.execute(
        query.order_by(desc(SystemLog.timestamp)).offset(offset).limit(per_page)
    )
    logs = result.scalars().all()

    return SystemLogListResponse(
        items=[SystemLogResponse.model_validate(log) for log in logs],
        total=total, page=page, per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.delete("/logs", status_code=204)
async def clear_system_logs(
    db: AsyncSession = Depends(get_db),
    _api_key=Depends(verify_api_key),
):
    """Clear all system logs."""
    from sqlalchemy import delete
    await db.execute(delete(SystemLog))
    await db.flush()
