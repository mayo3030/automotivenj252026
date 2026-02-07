"""API key management endpoints."""

import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ApiKey
from app.schemas import ApiKeyCreate, ApiKeyResponse, ApiKeyListResponse

router = APIRouter(prefix="/api/keys", tags=["API Keys"])


@router.get("", response_model=ApiKeyListResponse)
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
):
    """List all API keys."""
    result = await db.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
    keys = result.scalars().all()

    count_result = await db.execute(select(func.count(ApiKey.id)))
    total = count_result.scalar() or 0

    return ApiKeyListResponse(
        items=[ApiKeyResponse.model_validate(k) for k in keys],
        total=total,
    )


@router.post("", response_model=ApiKeyResponse, status_code=201)
async def create_api_key(
    body: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
):
    """Generate a new API key."""
    key_value = secrets.token_hex(32)  # 64-char hex string

    api_key = ApiKey(
        key=key_value,
        name=body.name,
        is_active=True,
    )
    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)

    return ApiKeyResponse.model_validate(api_key)


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Revoke (deactivate) an API key."""
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.is_active = False
    return None
