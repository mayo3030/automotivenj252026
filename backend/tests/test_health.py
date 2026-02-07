"""Smoke tests — verifies the app starts and core endpoints respond."""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_vehicles_list(client):
    r = await client.get("/api/vehicles")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_stats(client):
    r = await client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert "total_vehicles" in data
    assert "active_vehicles" in data
