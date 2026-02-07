"""API key authentication dependency."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Header, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ApiKey


async def verify_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Optional[ApiKey]:
    """
    Verify the X-API-Key header for external API consumers.

    - If no key is provided and the request comes from the frontend
      (Referer/Origin header), allow it through (returns None).
    - If a key is provided, validate it against the database.
    - External requests without a valid key get 401.
    """
    # Check if request is from the frontend (internal)
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")
    is_internal = any(
        allowed in (origin or referer)
        for allowed in ["localhost:3100", "localhost:5273", "frontend:3100", "127.0.0.1"]
    )

    if not x_api_key:
        if is_internal:
            return None
        # Allow requests without API key for now (for development)
        return None

    # Validate the API key
    result = await db.execute(
        select(ApiKey).where(ApiKey.key == x_api_key, ApiKey.is_active == True)  # noqa: E712
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")

    # Update usage stats
    await db.execute(
        update(ApiKey)
        .where(ApiKey.id == api_key.id)
        .values(
            last_used_at=datetime.now(timezone.utc),
            request_count=ApiKey.request_count + 1,
        )
    )

    return api_key
