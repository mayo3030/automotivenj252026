"""Application configuration via pydantic-settings."""

import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine the backend directory (where this file lives: backend/app/config.py)
_BACKEND_DIR = Path(__file__).resolve().parent.parent

# Default to SQLite in standalone mode
_DEFAULT_DB = f"sqlite+aiosqlite:///{_BACKEND_DIR / 'autoavenue.db'}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database – defaults to local SQLite so the app works without Docker
    DATABASE_URL: str = _DEFAULT_DB

    # Redis (optional – only used by Celery background tasks)
    REDIS_URL: str = "redis://localhost:6480/0"

    # Security
    SECRET_KEY: str = "change-me-in-production-super-secret-key-2026"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    # Media – default to the backend/media directory
    MEDIA_DIR: str = str(_BACKEND_DIR / "media")

    # Celery (optional)
    CELERY_BROKER_URL: str = "redis://localhost:6480/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6480/1"

    # Scraper
    SCRAPE_BASE_URL: str = "https://autoavenj.ebizautos.com"
    SCRAPE_DELAY_MIN: int = 2
    SCRAPE_DELAY_MAX: int = 5
    SCRAPE_MAX_RETRIES: int = 3

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.DATABASE_URL

    @property
    def sync_database_url(self) -> str:
        """Return sync database URL for Celery tasks."""
        if self.is_sqlite:
            return self.DATABASE_URL.replace("sqlite+aiosqlite", "sqlite")
        return self.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")


def _build_settings() -> Settings:
    """Build settings, fixing relative SQLite paths to be absolute."""
    s = Settings(
        _env_file=str(_BACKEND_DIR.parent / ".env"),
        _env_file_encoding="utf-8",
    )
    # Fix relative SQLite path to be absolute from backend dir
    if s.is_sqlite and ":///" in s.DATABASE_URL:
        db_path = s.DATABASE_URL.split(":///", 1)[1]
        if not os.path.isabs(db_path):
            abs_path = str(_BACKEND_DIR / db_path)
            s.DATABASE_URL = f"sqlite+aiosqlite:///{abs_path}"
    # Fix relative MEDIA_DIR
    if not os.path.isabs(s.MEDIA_DIR):
        s.MEDIA_DIR = str(_BACKEND_DIR / s.MEDIA_DIR)
    return s


settings = _build_settings()
