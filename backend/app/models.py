"""SQLAlchemy ORM models."""

import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Numeric, DateTime, Enum, JSON, Index
)
from app.database import Base


class ScrapeStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class LogLevel(str, enum.Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_number = Column(String(50), nullable=True, index=True)
    vin = Column(String(17), unique=True, nullable=False, index=True)
    year = Column(Integer, nullable=True, index=True)
    make = Column(String(100), nullable=True, index=True)
    model = Column(String(100), nullable=True, index=True)
    trim = Column(String(200), nullable=True)

    price = Column(Numeric(12, 2), nullable=True)
    mileage = Column(Integer, nullable=True)
    exterior_color = Column(String(100), nullable=True)
    interior_color = Column(String(100), nullable=True)

    body_style = Column(String(100), nullable=True, index=True)
    drivetrain = Column(String(100), nullable=True)
    engine = Column(String(200), nullable=True)
    transmission = Column(String(100), nullable=True)

    photos = Column(JSON, default=list)
    detail_url = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_vehicles_make_model", "make", "model"),
        Index("ix_vehicles_year_price", "year", "price"),
    )

    def __repr__(self):
        return f"<Vehicle {self.year} {self.make} {self.model} VIN={self.vin}>"


class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(255), nullable=True, index=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(Enum(ScrapeStatus), default=ScrapeStatus.RUNNING)

    vehicles_found = Column(Integer, default=0)
    vehicles_new = Column(Integer, default=0)
    vehicles_updated = Column(Integer, default=0)
    vehicles_removed = Column(Integer, default=0)

    errors = Column(JSON, default=list)
    log_output = Column(Text, default="")

    def __repr__(self):
        return f"<ScrapeLog {self.id} status={self.status}>"


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    request_count = Column(Integer, default=0)

    def __repr__(self):
        return f"<ApiKey {self.name} active={self.is_active}>"


class SystemLog(Base):
    """Structured log entries for monitoring, debugging, and audit trail."""
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    level = Column(Enum(LogLevel), default=LogLevel.INFO, index=True)
    source = Column(String(100), nullable=False, index=True)  # e.g. "scraper", "monitor", "api"
    message = Column(Text, nullable=False)
    details = Column(JSON, default=dict)  # extra structured data
    task_id = Column(String(255), nullable=True, index=True)  # link to a scrape task

    def __repr__(self):
        return f"<SystemLog {self.id} [{self.level}] {self.source}: {self.message[:50]}>"


class MonitorConfig(Base):
    """Singleton table for the 24/7 auto-monitor settings."""
    __tablename__ = "monitor_config"

    id = Column(Integer, primary_key=True, default=1)
    enabled = Column(Boolean, default=False)
    interval_minutes = Column(Integer, default=30)  # how often to check
    last_check_at = Column(DateTime(timezone=True), nullable=True)
    last_check_result = Column(Text, default="")
    pages_to_scrape = Column(Integer, default=0)  # 0 = all pages

    def __repr__(self):
        return f"<MonitorConfig enabled={self.enabled} interval={self.interval_minutes}m>"


class VehiclePriceHistory(Base):
    """Tracks every price snapshot for a vehicle over time."""
    __tablename__ = "vehicle_price_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vin = Column(String(17), nullable=False, index=True)
    price = Column(Numeric(12, 2), nullable=True)
    recorded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    source = Column(String(50), default="scrape")  # "scrape", "manual", "seed"

    __table_args__ = (
        Index("ix_price_history_vin_date", "vin", "recorded_at"),
    )

    def __repr__(self):
        return f"<PriceHistory {self.vin} ${self.price} @ {self.recorded_at}>"


class VehicleChangeLog(Base):
    """Tracks every field change for a vehicle — full audit trail."""
    __tablename__ = "vehicle_change_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vin = Column(String(17), nullable=False, index=True)
    changed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    change_type = Column(String(30), nullable=False, index=True)  # "new", "updated", "removed", "reactivated"
    field_name = Column(String(100), nullable=True)   # e.g. "price", "mileage", "is_active"
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    task_id = Column(String(255), nullable=True)       # link to the scrape task

    __table_args__ = (
        Index("ix_change_log_vin_date", "vin", "changed_at"),
    )

    def __repr__(self):
        return f"<ChangeLog {self.vin} {self.change_type} {self.field_name}>"
