"""Celery tasks for background scraping jobs."""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from celery import Celery
from celery.schedules import crontab
from sqlalchemy import create_engine, select, update, func
from sqlalchemy.orm import Session as SyncSession, sessionmaker

from app.config import settings
from app.models import Vehicle, ScrapeLog, ScrapeStatus

logger = logging.getLogger(__name__)

# ── Celery App ───────────────────────────────────────────────────────────────

celery_app = Celery(
    "autoavenue",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="US/Eastern",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    beat_schedule={
        "daily-scrape": {
            "task": "app.tasks.run_scrape",
            "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM ET
            "kwargs": {"scheduled": True},
        },
    },
)

# Sync database session for Celery tasks
sync_engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
SyncSessionLocal = sessionmaker(bind=sync_engine)


def _get_redis():
    """Get a Redis client for progress reporting."""
    import redis
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def _update_progress(task_id: str, **kwargs):
    """Store scrape progress in Redis for polling."""
    try:
        r = _get_redis()
        key = f"scrape_progress:{task_id}"
        data = r.get(key)
        progress = json.loads(data) if data else {}
        progress.update(kwargs)
        progress["task_id"] = task_id
        r.setex(key, 300, json.dumps(progress))  # TTL 5 min
    except Exception as e:
        logger.warning(f"Failed to update progress in Redis: {e}")


@celery_app.task(bind=True, name="app.tasks.run_scrape", max_retries=1)
def run_scrape(self, scheduled: bool = False):
    """
    Main scraping task. Runs the full Playwright scraper and syncs
    results to the database.
    """
    task_id = self.request.id
    logger.info(f"Starting scrape task {task_id} (scheduled={scheduled})")

    # Create scrape log entry
    db: SyncSession = SyncSessionLocal()
    log = ScrapeLog(
        task_id=task_id,
        status=ScrapeStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    log_id = log.id

    _update_progress(task_id, status="running", progress=5, message="Initializing scraper...")

    try:
        # Run the async scraper in a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        from app.scraper.scraper import AutoAvenueScaper

        def progress_cb(**kwargs):
            vehicles_found = kwargs.get("vehicles_found", 0)
            current_page = kwargs.get("current_page", 0)
            total_pages = kwargs.get("total_pages", 1)
            message = kwargs.get("message", "")
            pct = min(int((current_page / max(total_pages, 1)) * 70) + 10, 80)
            _update_progress(
                task_id,
                status="running",
                progress=pct,
                vehicles_found=vehicles_found,
                current_page=current_page,
                total_pages=total_pages,
                message=message,
            )

        scraper = AutoAvenueScaper(progress_callback=progress_cb)
        all_vehicles, scrape_errors = loop.run_until_complete(scraper.scrape_inventory())
        loop.close()

        _update_progress(task_id, progress=85, message="Syncing to database...")

        # ── Sync scraped data to database ────────────────────────────────
        scraped_vins = set()
        new_count = 0
        updated_count = 0

        for v_data in all_vehicles:
            vin = v_data.get("vin")
            if not vin:
                continue
            scraped_vins.add(vin)

            existing = db.execute(
                select(Vehicle).where(Vehicle.vin == vin)
            ).scalar_one_or_none()

            if existing:
                # Update existing vehicle
                changed = False
                for field in [
                    "stock_number", "year", "make", "model", "trim", "price",
                    "mileage", "exterior_color", "interior_color", "body_style",
                    "drivetrain", "engine", "transmission", "photos", "detail_url",
                ]:
                    new_val = v_data.get(field)
                    if new_val is not None and new_val != getattr(existing, field, None):
                        setattr(existing, field, new_val)
                        changed = True
                if changed:
                    existing.updated_at = datetime.now(timezone.utc)
                    existing.is_active = True
                    updated_count += 1
            else:
                # Insert new vehicle
                vehicle = Vehicle(
                    vin=vin,
                    stock_number=v_data.get("stock_number"),
                    year=v_data.get("year"),
                    make=v_data.get("make"),
                    model=v_data.get("model"),
                    trim=v_data.get("trim"),
                    price=v_data.get("price"),
                    mileage=v_data.get("mileage"),
                    exterior_color=v_data.get("exterior_color"),
                    interior_color=v_data.get("interior_color"),
                    body_style=v_data.get("body_style"),
                    drivetrain=v_data.get("drivetrain"),
                    engine=v_data.get("engine"),
                    transmission=v_data.get("transmission"),
                    photos=v_data.get("photos", []),
                    detail_url=v_data.get("detail_url"),
                    is_active=True,
                )
                db.add(vehicle)
                new_count += 1

        # Mark vehicles not found in scrape as inactive
        removed_count = 0
        if scraped_vins:
            active_vehicles = db.execute(
                select(Vehicle).where(Vehicle.is_active == True)  # noqa: E712
            ).scalars().all()
            for v in active_vehicles:
                if v.vin not in scraped_vins:
                    v.is_active = False
                    v.updated_at = datetime.now(timezone.utc)
                    removed_count += 1

        db.commit()

        # Download images in background (async)
        _update_progress(task_id, progress=90, message="Downloading images...")

        loop2 = asyncio.new_event_loop()
        asyncio.set_event_loop(loop2)

        async def download_all_images():
            from app.scraper.scraper import AutoAvenueScaper
            scraper = AutoAvenueScaper()
            for v_data in all_vehicles:
                vin = v_data.get("vin")
                photos = v_data.get("photos", [])
                if vin and photos:
                    try:
                        local_paths = await scraper.download_vehicle_images(vin, photos)
                        if local_paths:
                            db.execute(
                                update(Vehicle)
                                .where(Vehicle.vin == vin)
                                .values(photos=local_paths + photos)
                            )
                    except Exception as e:
                        logger.warning(f"Image download failed for VIN {vin}: {e}")
            db.commit()

        try:
            loop2.run_until_complete(download_all_images())
        except Exception as e:
            logger.warning(f"Image download phase failed: {e}")
        finally:
            loop2.close()

        # Update scrape log
        scrape_log = db.get(ScrapeLog, log_id)
        scrape_log.status = ScrapeStatus.COMPLETED
        scrape_log.finished_at = datetime.now(timezone.utc)
        scrape_log.vehicles_found = len(all_vehicles)
        scrape_log.vehicles_new = new_count
        scrape_log.vehicles_updated = updated_count
        scrape_log.vehicles_removed = removed_count
        scrape_log.errors = scrape_errors
        scrape_log.log_output = (
            f"Scrape completed. Found {len(all_vehicles)} vehicles. "
            f"New: {new_count}, Updated: {updated_count}, Removed: {removed_count}."
        )
        db.commit()

        _update_progress(
            task_id,
            status="completed",
            progress=100,
            vehicles_found=len(all_vehicles),
            vehicles_new=new_count,
            vehicles_updated=updated_count,
            message="Scrape completed successfully!",
        )

        logger.info(
            f"Scrape task {task_id} completed. "
            f"Found={len(all_vehicles)}, New={new_count}, "
            f"Updated={updated_count}, Removed={removed_count}"
        )
        return {
            "status": "completed",
            "vehicles_found": len(all_vehicles),
            "vehicles_new": new_count,
            "vehicles_updated": updated_count,
            "vehicles_removed": removed_count,
        }

    except Exception as e:
        logger.error(f"Scrape task {task_id} failed: {e}", exc_info=True)

        # Update scrape log with failure
        try:
            scrape_log = db.get(ScrapeLog, log_id)
            if scrape_log:
                scrape_log.status = ScrapeStatus.FAILED
                scrape_log.finished_at = datetime.now(timezone.utc)
                scrape_log.errors = [str(e)]
                scrape_log.log_output = f"Scrape failed: {e}"
                db.commit()
        except Exception:
            pass

        _update_progress(
            task_id,
            status="failed",
            progress=0,
            message=f"Scrape failed: {str(e)[:200]}",
        )
        raise

    finally:
        db.close()
