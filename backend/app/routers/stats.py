"""Stats API endpoint."""

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Vehicle, ScrapeLog, ApiKey
from app.schemas import StatsResponse, MakeBreakdown
from app.auth import verify_api_key

router = APIRouter(prefix="/api/stats", tags=["Statistics"])


@router.get("", response_model=StatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _api_key=Depends(verify_api_key),
):
    """Get dashboard statistics: totals, averages, breakdown, last scrape info."""

    # Total vehicles
    total_result = await db.execute(select(func.count(Vehicle.id)))
    total_vehicles = total_result.scalar() or 0

    # Active vehicles
    active_result = await db.execute(
        select(func.count(Vehicle.id)).where(Vehicle.is_active == True)  # noqa: E712
    )
    active_vehicles = active_result.scalar() or 0

    # Average price (active only)
    avg_result = await db.execute(
        select(func.avg(Vehicle.price)).where(
            Vehicle.is_active == True,  # noqa: E712
            Vehicle.price.isnot(None),
        )
    )
    avg_price = avg_result.scalar()
    average_price = round(float(avg_price), 2) if avg_price else None

    # Makes breakdown (top makes by count)
    makes_result = await db.execute(
        select(Vehicle.make, func.count(Vehicle.id).label("count"))
        .where(Vehicle.is_active == True, Vehicle.make.isnot(None))  # noqa: E712
        .group_by(Vehicle.make)
        .order_by(desc("count"))
        .limit(20)
    )
    makes_breakdown = [
        MakeBreakdown(make=row.make, count=row.count)
        for row in makes_result
    ]

    # Last scrape info
    last_scrape_result = await db.execute(
        select(ScrapeLog).order_by(desc(ScrapeLog.started_at)).limit(1)
    )
    last_scrape = last_scrape_result.scalar_one_or_none()

    last_scrape_time = last_scrape.started_at if last_scrape else None
    last_scrape_status = last_scrape.status.value if last_scrape and last_scrape.status else None

    # Total scrapes
    scrape_count_result = await db.execute(select(func.count(ScrapeLog.id)))
    total_scrapes = scrape_count_result.scalar() or 0

    # API requests today
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    api_requests_result = await db.execute(
        select(func.sum(ApiKey.request_count)).where(
            ApiKey.last_used_at >= today_start
        )
    )
    api_requests_today = api_requests_result.scalar() or 0

    return StatsResponse(
        total_vehicles=total_vehicles,
        active_vehicles=active_vehicles,
        average_price=average_price,
        makes_breakdown=makes_breakdown,
        last_scrape_time=last_scrape_time,
        last_scrape_status=last_scrape_status,
        total_scrapes=total_scrapes,
        api_requests_today=api_requests_today,
    )
