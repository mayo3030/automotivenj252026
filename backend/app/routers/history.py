"""Vehicle history API — price charts, change timelines, audit trail."""

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Vehicle, VehiclePriceHistory, VehicleChangeLog
from app.schemas import (
    PricePointResponse,
    ChangeLogResponse,
    VehicleHistoryResponse,
    VehicleHistorySummary,
    VehicleHistoryListResponse,
)
from app.auth import verify_api_key

router = APIRouter(prefix="/api/history", tags=["Vehicle History"])


def _price_direction(prices: list[VehiclePriceHistory]) -> tuple[str, float | None]:
    """Compute direction + amount from the most recent two distinct prices."""
    if len(prices) < 2:
        return ("new" if prices else "stable"), None

    vals = [float(p.price) for p in prices if p.price is not None]
    if len(vals) < 2:
        return "stable", None

    latest = vals[-1]
    previous = vals[-2]
    diff = latest - previous
    if abs(diff) < 0.01:
        return "stable", 0.0
    return ("up" if diff > 0 else "down"), round(diff, 2)


# ── List all vehicles with history summaries ─────────────────────────────────

@router.get("/vehicles", response_model=VehicleHistoryListResponse)
async def list_vehicle_histories(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    active_only: bool = Query(False),
    direction: Optional[str] = Query(None, description="Filter: up, down, stable"),
    db: AsyncSession = Depends(get_db),
    _api_key=Depends(verify_api_key),
):
    """List all vehicles with a summary of their price history."""
    query = select(Vehicle)
    count_query = select(func.count(Vehicle.id))

    if active_only:
        query = query.where(Vehicle.is_active == True)  # noqa
        count_query = count_query.where(Vehicle.is_active == True)  # noqa

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * per_page
    result = await db.execute(
        query.order_by(desc(Vehicle.updated_at)).offset(offset).limit(per_page)
    )
    vehicles = result.scalars().all()

    items: list[VehicleHistorySummary] = []
    for v in vehicles:
        # Price history for this VIN
        ph_result = await db.execute(
            select(VehiclePriceHistory)
            .where(VehiclePriceHistory.vin == v.vin)
            .order_by(asc(VehiclePriceHistory.recorded_at))
        )
        prices = ph_result.scalars().all()
        direction_val, change_amt = _price_direction(prices)

        # Total changes count
        cl_count = (await db.execute(
            select(func.count(VehicleChangeLog.id))
            .where(VehicleChangeLog.vin == v.vin)
        )).scalar() or 0

        # Last change
        last_cl = (await db.execute(
            select(VehicleChangeLog.changed_at)
            .where(VehicleChangeLog.vin == v.vin)
            .order_by(desc(VehicleChangeLog.changed_at))
            .limit(1)
        )).scalar_one_or_none()

        # Hero photo
        hero = v.photos[0] if v.photos else None

        items.append(VehicleHistorySummary(
            vin=v.vin, year=v.year, make=v.make, model=v.model, trim=v.trim,
            current_price=float(v.price) if v.price else None,
            is_active=v.is_active,
            price_direction=direction_val,
            price_change_amount=change_amt,
            total_changes=cl_count,
            last_change_at=last_cl,
            hero_photo=hero,
        ))

    # Optional client-side filter by direction
    if direction and direction in ("up", "down", "stable", "new"):
        items = [i for i in items if i.price_direction == direction]

    return VehicleHistoryListResponse(
        items=items, total=total, page=page, per_page=per_page,
        pages=math.ceil(total / per_page) if total else 0,
    )


# ── Full history for a single vehicle ────────────────────────────────────────

@router.get("/vehicles/{vin}", response_model=VehicleHistoryResponse)
async def get_vehicle_history(
    vin: str,
    db: AsyncSession = Depends(get_db),
    _api_key=Depends(verify_api_key),
):
    """Full history for one vehicle: price chart + change timeline."""
    result = await db.execute(select(Vehicle).where(Vehicle.vin == vin.upper()))
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # Price history
    ph_result = await db.execute(
        select(VehiclePriceHistory)
        .where(VehiclePriceHistory.vin == vehicle.vin)
        .order_by(asc(VehiclePriceHistory.recorded_at))
    )
    prices = ph_result.scalars().all()
    direction_val, change_amt = _price_direction(prices)

    # Change log
    cl_result = await db.execute(
        select(VehicleChangeLog)
        .where(VehicleChangeLog.vin == vehicle.vin)
        .order_by(desc(VehicleChangeLog.changed_at))
    )
    changes = cl_result.scalars().all()

    return VehicleHistoryResponse(
        vin=vehicle.vin,
        year=vehicle.year,
        make=vehicle.make,
        model=vehicle.model,
        trim=vehicle.trim,
        current_price=float(vehicle.price) if vehicle.price else None,
        first_seen=vehicle.created_at,
        last_updated=vehicle.updated_at,
        is_active=vehicle.is_active,
        price_history=[
            PricePointResponse(
                id=p.id,
                price=float(p.price) if p.price else None,
                recorded_at=p.recorded_at,
                source=p.source,
            )
            for p in prices
        ],
        change_log=[ChangeLogResponse.model_validate(c) for c in changes],
        price_direction=direction_val,
        price_change_amount=change_amt,
    )
