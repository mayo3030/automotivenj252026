"""Pydantic request/response schemas."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field


# ── Vehicle Schemas ──────────────────────────────────────────────────────────

class VehicleBase(BaseModel):
    stock_number: Optional[str] = None
    vin: str
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    trim: Optional[str] = None
    price: Optional[Decimal] = None
    mileage: Optional[int] = None
    exterior_color: Optional[str] = None
    interior_color: Optional[str] = None
    body_style: Optional[str] = None
    drivetrain: Optional[str] = None
    engine: Optional[str] = None
    transmission: Optional[str] = None
    photos: List[str] = Field(default_factory=list)
    detail_url: Optional[str] = None


class VehicleResponse(VehicleBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class VehicleListResponse(BaseModel):
    items: List[VehicleResponse]
    total: int
    page: int
    per_page: int
    pages: int


# ── Scrape Schemas ───────────────────────────────────────────────────────────

class ScrapeLogResponse(BaseModel):
    id: int
    task_id: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str
    vehicles_found: int = 0
    vehicles_new: int = 0
    vehicles_updated: int = 0
    vehicles_removed: int = 0
    errors: List[str] = Field(default_factory=list)
    log_output: str = ""

    class Config:
        from_attributes = True


class ScrapeLogListResponse(BaseModel):
    items: List[ScrapeLogResponse]
    total: int
    page: int
    per_page: int
    pages: int


class ScrapeTriggerResponse(BaseModel):
    task_id: str
    message: str


class ScrapeProgress(BaseModel):
    task_id: Optional[str] = None
    status: str
    progress: int = 0  # 0-100
    vehicles_found: int = 0
    vehicles_new: int = 0
    vehicles_updated: int = 0
    current_page: int = 0
    total_pages: int = 0
    message: str = ""


# ── Stats Schemas ────────────────────────────────────────────────────────────

class MakeBreakdown(BaseModel):
    make: str
    count: int


class StatsResponse(BaseModel):
    total_vehicles: int
    active_vehicles: int
    average_price: Optional[float] = None
    makes_breakdown: List[MakeBreakdown]
    last_scrape_time: Optional[datetime] = None
    last_scrape_status: Optional[str] = None
    total_scrapes: int
    api_requests_today: int = 0


# ── API Key Schemas ──────────────────────────────────────────────────────────

class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class ApiKeyResponse(BaseModel):
    id: int
    key: str
    name: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None
    request_count: int = 0

    class Config:
        from_attributes = True


class ApiKeyListResponse(BaseModel):
    items: List[ApiKeyResponse]
    total: int


# ── Scrape Trigger with options ──────────────────────────────────────────────

class ScrapeTriggerRequest(BaseModel):
    pages: int = Field(default=1, ge=0, description="Pages to scrape (0 = all)")


# ── System Log Schemas ───────────────────────────────────────────────────────

class SystemLogResponse(BaseModel):
    id: int
    timestamp: datetime
    level: str
    source: str
    message: str
    details: dict = Field(default_factory=dict)
    task_id: Optional[str] = None

    class Config:
        from_attributes = True


class SystemLogListResponse(BaseModel):
    items: List[SystemLogResponse]
    total: int
    page: int
    per_page: int
    pages: int


# ── Monitor Schemas ──────────────────────────────────────────────────────────

class MonitorConfigResponse(BaseModel):
    enabled: bool
    interval_minutes: int
    last_check_at: Optional[datetime] = None
    last_check_result: str = ""
    pages_to_scrape: int = 0

    class Config:
        from_attributes = True


class MonitorConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    interval_minutes: Optional[int] = Field(None, ge=5, le=1440)
    pages_to_scrape: Optional[int] = Field(None, ge=0)


# ── Inventory Comparison Schemas ─────────────────────────────────────────────

class InventoryComparisonVehicle(BaseModel):
    vin: str
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    price: Optional[str] = None
    status: str  # "match", "missing_local", "missing_remote", "changed"
    detail_url: Optional[str] = None


class InventoryComparison(BaseModel):
    website_count: int
    local_count: int
    matched: int
    missing_locally: int  # on website but not in our DB
    extra_locally: int    # in our DB but not on website
    changed: int          # price or other info differs
    vehicles: List[InventoryComparisonVehicle]
    checked_at: datetime
    pages_checked: int


# ── Vehicle History Schemas ──────────────────────────────────────────────────

class PricePointResponse(BaseModel):
    id: int
    price: Optional[float] = None
    recorded_at: datetime
    source: str = "scrape"

    class Config:
        from_attributes = True


class ChangeLogResponse(BaseModel):
    id: int
    vin: str
    changed_at: datetime
    change_type: str
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    task_id: Optional[str] = None

    class Config:
        from_attributes = True


class VehicleHistoryResponse(BaseModel):
    """Full history for one vehicle: info + price chart data + change timeline."""
    vin: str
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    trim: Optional[str] = None
    current_price: Optional[float] = None
    first_seen: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    is_active: bool = True
    price_history: List[PricePointResponse]
    change_log: List[ChangeLogResponse]
    price_direction: str = "stable"  # "up", "down", "stable", "new"
    price_change_amount: Optional[float] = None


class VehicleHistorySummary(BaseModel):
    """Summary for the vehicle history list page."""
    vin: str
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    trim: Optional[str] = None
    current_price: Optional[float] = None
    is_active: bool = True
    price_direction: str = "stable"
    price_change_amount: Optional[float] = None
    total_changes: int = 0
    last_change_at: Optional[datetime] = None
    hero_photo: Optional[str] = None


class VehicleHistoryListResponse(BaseModel):
    items: List[VehicleHistorySummary]
    total: int
    page: int
    per_page: int
    pages: int
