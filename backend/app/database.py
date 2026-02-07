"""SQLAlchemy async engine and session management."""

import sys
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import create_engine

from app.config import settings

# Async engine for FastAPI
_async_kw: dict = {"echo": False}
if not settings.is_sqlite:
    _async_kw.update(pool_size=20, max_overflow=10, pool_pre_ping=True)

async_engine = create_async_engine(settings.DATABASE_URL, **_async_kw)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Sync engine for Celery tasks
_sync_kw: dict = {"echo": False}
if not settings.is_sqlite:
    _sync_kw.update(pool_size=10, max_overflow=5, pool_pre_ping=True)

sync_engine = create_engine(settings.sync_database_url, **_sync_kw)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """Dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables."""
    async with async_engine.begin() as conn:
        from app.models import Vehicle, ScrapeLog, ApiKey, SystemLog, MonitorConfig, VehiclePriceHistory, VehicleChangeLog  # noqa
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    import asyncio

    if "--init" in sys.argv:
        asyncio.run(init_db())
        print("Database tables created successfully.")
