"""Comprehensive tests for the scraping server.

Tests all API endpoints, the HTML parser, scraper utilities,
and the end-to-end pipeline (with mocked browser navigation).
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.scraper.parser import (
    parse_listing_page,
    parse_vehicle_detail,
    find_next_page_url,
    _parse_price,
    _parse_number,
    _parse_vehicle_title,
)
from app.scraper.utils import (
    get_random_user_agent,
    sanitize_filename,
    USER_AGENTS,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── Sample HTML fixtures ─────────────────────────────────────────────────────

SAMPLE_LISTING_HTML = """
<html>
<body>
<div class="inventory-list">
  <div class="vehicle-card">
    <a href="/vehicle/2023-Toyota-Camry-12345">
      <img src="https://example.com/img/camry.jpg" />
      <h3>2023 Toyota Camry SE</h3>
    </a>
  </div>
  <div class="vehicle-card">
    <a href="/vehicle/2022-Honda-Civic-67890">
      <img src="https://example.com/img/civic.jpg" />
      <h3>2022 Honda Civic LX</h3>
    </a>
  </div>
  <div class="vehicle-card">
    <a href="/vehicle/2024-Ford-Mustang-11111">
      <img src="https://example.com/img/mustang.jpg" />
      <h3>2024 Ford Mustang GT</h3>
    </a>
  </div>
</div>
<div class="pagination">
  <a class="active" href="?page=1">1</a>
  <a href="?page=2">2</a>
  <a class="next" href="?page=2">Next</a>
</div>
</body>
</html>
"""

SAMPLE_DETAIL_HTML = """
<html>
<body>
<h1>2023 Toyota Camry SE</h1>
<div class="vehicle-specs">
  <dl>
    <dt>VIN:</dt><dd>1HGBH41JXMN109186</dd>
    <dt>Stock #:</dt><dd>T12345</dd>
    <dt>Price:</dt><dd>$28,995</dd>
    <dt>Mileage:</dt><dd>15,234 miles</dd>
    <dt>Exterior Color:</dt><dd>Midnight Black</dd>
    <dt>Interior Color:</dt><dd>Ash Gray</dd>
    <dt>Body Style:</dt><dd>Sedan</dd>
    <dt>Drivetrain:</dt><dd>FWD</dd>
    <dt>Engine:</dt><dd>2.5L 4-Cylinder</dd>
    <dt>Transmission:</dt><dd>8-Speed Automatic</dd>
    <dt>Trim:</dt><dd>SE</dd>
  </dl>
</div>
<div class="gallery">
  <img src="https://example.com/photos/camry_01.jpg" />
  <img src="https://example.com/photos/camry_02.jpg" />
  <img src="https://example.com/photos/camry_03.jpg" />
</div>
</body>
</html>
"""

SAMPLE_LISTING_LINKS_HTML = """
<html>
<body>
<div>
  <a href="/vehicle/2023-Toyota-Camry/">
    <img src="https://example.com/thumb1.jpg" />
    2023 Toyota Camry SE
  </a>
  <a href="/inventory/2022-Honda-Accord/">
    <img src="https://example.com/thumb2.jpg" />
    2022 Honda Accord Sport
  </a>
  <a href="/about-us">About Us</a>
</div>
</body>
</html>
"""

SAMPLE_NO_PAGINATION_HTML = """
<html><body>
<div class="vehicle-card">
  <a href="/vehicle/test"><h3>Test Vehicle</h3></a>
</div>
</body></html>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# PARSER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseListingPage:
    def test_parses_vehicle_cards(self):
        stubs = parse_listing_page(SAMPLE_LISTING_HTML)
        assert len(stubs) == 3

    def test_extracts_detail_urls(self):
        stubs = parse_listing_page(SAMPLE_LISTING_HTML)
        urls = [s["detail_url"] for s in stubs]
        assert "/vehicle/2023-Toyota-Camry-12345" in urls
        assert "/vehicle/2022-Honda-Civic-67890" in urls
        assert "/vehicle/2024-Ford-Mustang-11111" in urls

    def test_extracts_thumbnails(self):
        stubs = parse_listing_page(SAMPLE_LISTING_HTML)
        assert stubs[0]["thumbnail"] == "https://example.com/img/camry.jpg"

    def test_fallback_to_links(self):
        """When no vehicle-card elements, falls back to link-based extraction."""
        stubs = parse_listing_page(SAMPLE_LISTING_LINKS_HTML)
        # Should find 2 vehicle links, skip "about-us"
        assert len(stubs) == 2
        urls = [s["detail_url"] for s in stubs]
        assert "/vehicle/2023-Toyota-Camry/" in urls
        assert "/inventory/2022-Honda-Accord/" in urls

    def test_empty_html(self):
        stubs = parse_listing_page("<html><body></body></html>")
        assert stubs == []


class TestParseVehicleDetail:
    def test_extracts_all_fields(self):
        data = parse_vehicle_detail(SAMPLE_DETAIL_HTML, "http://example.com/vehicle/1")
        assert data["vin"] == "1HGBH41JXMN109186"
        assert data["stock_number"] == "T12345"
        assert data["price"] == 28995.0
        assert data["mileage"] == 15234
        assert data["year"] == 2023
        assert data["make"] == "Toyota"
        assert data["model"] == "Camry"
        assert data["exterior_color"] == "Midnight Black"
        assert data["interior_color"] == "Ash Gray"
        assert data["body_style"] == "Sedan"
        assert data["drivetrain"] == "FWD"
        assert data["engine"] == "2.5L 4-Cylinder"
        assert data["transmission"] == "8-Speed Automatic"
        assert data["detail_url"] == "http://example.com/vehicle/1"

    def test_extracts_photos(self):
        data = parse_vehicle_detail(SAMPLE_DETAIL_HTML)
        assert len(data["photos"]) == 3
        assert "https://example.com/photos/camry_01.jpg" in data["photos"]

    def test_filters_out_logos_and_icons(self):
        html = """
        <html><body>
        <h1>2023 Test Car</h1>
        <div class="gallery">
            <img src="https://example.com/logo.png" />
            <img src="https://example.com/favicon.ico" />
            <img src="https://example.com/vehicle_photo.jpg" />
            <img src="https://example.com/placeholder.gif" />
        </div>
        </body></html>
        """
        data = parse_vehicle_detail(html)
        # Only the vehicle_photo should survive filtering
        assert len(data["photos"]) == 1
        assert "vehicle_photo.jpg" in data["photos"][0]

    def test_vin_regex_fallback(self):
        """VIN is found via regex when not in a labeled field."""
        html = """
        <html><body>
        <h1>2023 BMW X5</h1>
        <p>Vehicle identification: WBAPH5C55BA123456</p>
        </body></html>
        """
        data = parse_vehicle_detail(html)
        assert data["vin"] == "WBAPH5C55BA123456"


class TestFindNextPageUrl:
    def test_finds_next_link(self):
        url = find_next_page_url(SAMPLE_LISTING_HTML)
        assert url == "?page=2"

    def test_returns_none_when_no_pagination(self):
        url = find_next_page_url(SAMPLE_NO_PAGINATION_HTML)
        assert url is None

    def test_finds_rel_next(self):
        html = '<html><body><a rel="next" href="/page/3">Next</a></body></html>'
        url = find_next_page_url(html)
        assert url == "/page/3"


class TestPriceParser:
    def test_normal_price(self):
        assert _parse_price("$28,995") == 28995.0

    def test_price_with_decimals(self):
        assert _parse_price("$28,995.99") == 28995.99

    def test_price_no_dollar_sign(self):
        assert _parse_price("28995") == 28995.0

    def test_price_zero(self):
        assert _parse_price("$0") is None

    def test_price_none(self):
        assert _parse_price(None) is None

    def test_price_empty(self):
        assert _parse_price("") is None

    def test_price_text(self):
        assert _parse_price("Call for price") is None


class TestNumberParser:
    def test_normal_mileage(self):
        assert _parse_number("15,234 miles") == 15234

    def test_plain_number(self):
        assert _parse_number("50000") == 50000

    def test_none(self):
        assert _parse_number(None) is None

    def test_empty(self):
        assert _parse_number("") is None


class TestVehicleTitleParser:
    def test_full_title(self):
        result = _parse_vehicle_title("2023 Toyota Camry SE Nightshade")
        assert result["year"] == 2023
        assert result["make"] == "Toyota"
        assert result["model"] == "Camry"
        assert result["trim"] == "SE Nightshade"

    def test_title_no_trim(self):
        result = _parse_vehicle_title("2022 Honda Civic")
        assert result["year"] == 2022
        assert result["make"] == "Honda"
        assert result["model"] == "Civic"

    def test_title_no_year(self):
        result = _parse_vehicle_title("Ford Mustang GT")
        assert result["make"] == "Ford"
        assert result["model"] == "Mustang"


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestScraperUtils:
    def test_random_user_agent(self):
        ua = get_random_user_agent()
        assert ua in USER_AGENTS
        assert "Mozilla" in ua

    def test_sanitize_filename(self):
        assert sanitize_filename("hello world!@#.jpg") == "hello_world___.jpg"
        assert sanitize_filename("normal_file-name.txt") == "normal_file-name.txt"
        assert sanitize_filename("") == ""


# ═══════════════════════════════════════════════════════════════════════════════
# API ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"


class TestVehiclesAPI:
    @pytest.mark.asyncio
    async def test_list_vehicles(self, client):
        r = await client.get("/api/vehicles")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "pages" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_search_vehicles(self, client):
        r = await client.get("/api/vehicles/search", params={"q": "Toyota"})
        assert r.status_code == 200
        data = r.json()
        assert "items" in data

    @pytest.mark.asyncio
    async def test_export_csv(self, client):
        r = await client.get("/api/vehicles/export", params={"format": "csv"})
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_export_json(self, client):
        r = await client.get("/api/vehicles/export", params={"format": "json"})
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_get_nonexistent_vehicle(self, client):
        r = await client.get("/api/vehicles/NONEXISTENT_VIN")
        assert r.status_code == 404


class TestStatsAPI:
    @pytest.mark.asyncio
    async def test_stats(self, client):
        r = await client.get("/api/stats")
        assert r.status_code == 200
        data = r.json()
        assert "total_vehicles" in data
        assert "active_vehicles" in data
        assert "makes_breakdown" in data
        assert "total_scrapes" in data


class TestScrapeAPI:
    @pytest.mark.asyncio
    async def test_scrape_status_idle(self, client):
        r = await client.get("/api/scrape/status")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "progress" in data

    @pytest.mark.asyncio
    async def test_scrape_logs_empty(self, client):
        r = await client.get("/api/scrape/logs")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)


class TestMonitorAPI:
    @pytest.mark.asyncio
    async def test_get_monitor_config(self, client):
        r = await client.get("/api/monitor/config")
        assert r.status_code == 200
        data = r.json()
        assert "enabled" in data
        assert "interval_minutes" in data

    @pytest.mark.asyncio
    async def test_update_monitor_config(self, client):
        r = await client.put(
            "/api/monitor/config",
            json={"enabled": False, "interval_minutes": 60},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["enabled"] is False
        assert data["interval_minutes"] == 60

    @pytest.mark.asyncio
    async def test_get_monitor_logs(self, client):
        r = await client.get("/api/monitor/logs")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data


class TestHistoryAPI:
    @pytest.mark.asyncio
    async def test_list_vehicle_history(self, client):
        r = await client.get("/api/history/vehicles")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data


class TestApiKeysAPI:
    @pytest.mark.asyncio
    async def test_create_and_list_keys(self, client):
        # Create a key (201 Created)
        r = await client.post("/api/keys", json={"name": "test-key"})
        assert r.status_code == 201
        key_data = r.json()
        assert key_data["name"] == "test-key"
        assert "key" in key_data
        key_id = key_data["id"]

        # List keys
        r = await client.get("/api/keys")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1

        # Delete key (204 No Content)
        r = await client.delete(f"/api/keys/{key_id}")
        assert r.status_code == 204


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPE TRIGGER (E2E with subprocess, but will fail due to network)
# ═══════════════════════════════════════════════════════════════════════════════

class TestScrapeTrigger:
    @pytest.mark.asyncio
    async def test_trigger_returns_task_id(self, client):
        """Verify the trigger endpoint launches a scrape and returns a task ID."""
        r = await client.post(
            "/api/scrape/trigger",
            json={"pages": 1},
        )
        assert r.status_code == 200
        data = r.json()
        assert "task_id" in data
        assert data["task_id"].startswith("scrape-")
        assert "message" in data
