"""Vehicle API endpoints."""

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, func, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Vehicle
from app.schemas import VehicleResponse, VehicleListResponse
from app.auth import verify_api_key
from app.export import export_csv, export_json, export_pdf

router = APIRouter(prefix="/api/vehicles", tags=["Vehicles"])


@router.get("", response_model=VehicleListResponse)
async def list_vehicles(
    make: Optional[str] = Query(None, description="Filter by make"),
    model: Optional[str] = Query(None, description="Filter by model"),
    year_min: Optional[int] = Query(None, description="Minimum year"),
    year_max: Optional[int] = Query(None, description="Maximum year"),
    price_min: Optional[float] = Query(None, description="Minimum price"),
    price_max: Optional[float] = Query(None, description="Maximum price"),
    mileage_min: Optional[int] = Query(None, description="Minimum mileage"),
    mileage_max: Optional[int] = Query(None, description="Maximum mileage"),
    body_style: Optional[str] = Query(None, description="Filter by body style"),
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    sort_by: str = Query("created_at", description="Sort field"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    _api_key=Depends(verify_api_key),
):
    """List vehicles with filtering, sorting, and pagination."""
    query = select(Vehicle)
    count_query = select(func.count(Vehicle.id))

    # Apply filters
    filters = []
    if make:
        filters.append(Vehicle.make.ilike(f"%{make}%"))
    if model:
        filters.append(Vehicle.model.ilike(f"%{model}%"))
    if year_min:
        filters.append(Vehicle.year >= year_min)
    if year_max:
        filters.append(Vehicle.year <= year_max)
    if price_min:
        filters.append(Vehicle.price >= price_min)
    if price_max:
        filters.append(Vehicle.price <= price_max)
    if mileage_min:
        filters.append(Vehicle.mileage >= mileage_min)
    if mileage_max:
        filters.append(Vehicle.mileage <= mileage_max)
    if body_style:
        filters.append(Vehicle.body_style.ilike(f"%{body_style}%"))
    if is_active is not None:
        filters.append(Vehicle.is_active == is_active)

    for f in filters:
        query = query.where(f)
        count_query = count_query.where(f)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply sorting
    sort_column = getattr(Vehicle, sort_by, Vehicle.created_at)
    if order.lower() == "asc":
        query = query.order_by(asc(sort_column))
    else:
        query = query.order_by(desc(sort_column))

    # Apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    vehicles = result.scalars().all()

    return VehicleListResponse(
        items=[VehicleResponse.model_validate(v) for v in vehicles],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total > 0 else 0,
    )


@router.get("/search")
async def search_vehicles(
    q: str = Query(..., min_length=1, description="Search query (VIN or stock number)"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _api_key=Depends(verify_api_key),
):
    """Full-text search by VIN or stock number."""
    search_term = f"%{q}%"
    query = select(Vehicle).where(
        or_(
            Vehicle.vin.ilike(search_term),
            Vehicle.stock_number.ilike(search_term),
            Vehicle.make.ilike(search_term),
            Vehicle.model.ilike(search_term),
        )
    )
    count_query = select(func.count(Vehicle.id)).where(
        or_(
            Vehicle.vin.ilike(search_term),
            Vehicle.stock_number.ilike(search_term),
            Vehicle.make.ilike(search_term),
            Vehicle.model.ilike(search_term),
        )
    )

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * per_page
    result = await db.execute(query.offset(offset).limit(per_page))
    vehicles = result.scalars().all()

    return VehicleListResponse(
        items=[VehicleResponse.model_validate(v) for v in vehicles],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if total > 0 else 0,
    )


@router.get("/export")
async def export_vehicles(
    format: str = Query("csv", description="Export format: csv, json, or pdf"),
    is_active: Optional[bool] = Query(True),
    db: AsyncSession = Depends(get_db),
    _api_key=Depends(verify_api_key),
):
    """Export vehicle data as CSV, JSON, or PDF."""
    query = select(Vehicle)
    if is_active is not None:
        query = query.where(Vehicle.is_active == is_active)
    query = query.order_by(Vehicle.year.desc(), Vehicle.make, Vehicle.model)

    result = await db.execute(query)
    vehicles = result.scalars().all()

    if format == "csv":
        content = export_csv(vehicles)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=vehicles.csv"},
        )
    elif format == "pdf":
        content = export_pdf(vehicles)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=vehicles.pdf"},
        )
    elif format == "json":
        content = export_json(vehicles)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=vehicles.json"},
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid format. Use csv, json, or pdf.")


@router.get("/{vin}", response_model=VehicleResponse)
async def get_vehicle(
    vin: str,
    db: AsyncSession = Depends(get_db),
    _api_key=Depends(verify_api_key),
):
    """Get a single vehicle by VIN."""
    result = await db.execute(select(Vehicle).where(Vehicle.vin == vin))
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail=f"Vehicle with VIN {vin} not found")
    return VehicleResponse.model_validate(vehicle)
