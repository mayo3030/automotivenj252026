"""Playwright-based scraper for automotiveavenuenj.com inventory."""

import asyncio
import hashlib
import logging
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional
from urllib.parse import urljoin

import httpx
from playwright.async_api import async_playwright, Browser, Page, BrowserContext

from app.config import settings
from app.scraper.parser import parse_listing_page, parse_vehicle_detail, find_next_page_url
from app.scraper.utils import get_random_user_agent, random_delay, retry_with_backoff, has_dealer_frame, remove_dealer_frame

logger = logging.getLogger(__name__)

INVENTORY_PATH = "/inventory"


class AutoAvenueScaper:
    """
    Scrapes vehicle inventory from automotiveavenuenj.com.

    Uses Playwright with Chromium in headless mode, with anti-detection
    measures: random user agents, delays, and retry logic.
    """

    def __init__(
        self,
        base_url: str = None,
        media_dir: str = None,
        progress_callback: Optional[Callable] = None,
    ):
        self.base_url = (base_url or settings.SCRAPE_BASE_URL).rstrip("/")
        self.media_dir = media_dir or settings.MEDIA_DIR
        self.delay_min = settings.SCRAPE_DELAY_MIN
        self.delay_max = settings.SCRAPE_DELAY_MAX
        self.max_retries = settings.SCRAPE_MAX_RETRIES
        self.progress_callback = progress_callback
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def _report_progress(self, **kwargs):
        """Report progress to the callback if set."""
        if self.progress_callback:
            self.progress_callback(**kwargs)

    async def start_browser(self):
        """Launch Playwright browser with stealth settings."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        self._context = await self._browser.new_context(
            user_agent=get_random_user_agent(),
            viewport={"width": 1920, "height": 1080},
            java_script_enabled=True,
            ignore_https_errors=True,
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            },
        )
        # Anti-detection: override navigator.webdriver
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            window.chrome = { runtime: {} };
        """)
        logger.info("Browser launched successfully.")

    async def stop_browser(self):
        """Close browser and cleanup."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed.")

    async def _navigate_with_retry(self, page: Page, url: str) -> str:
        """Navigate to a URL with retry logic and return page HTML."""
        async def _do_navigate():
            response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            # Wait for dynamic content to load
            await page.wait_for_load_state("networkidle", timeout=30000)
            # Additional wait for JS-rendered content
            await asyncio.sleep(2)

            # Handle potential bot-detection / verification pages
            content = await page.content()
            if _is_challenge_page(content):
                logger.warning(f"Bot detection challenge detected on {url}, waiting...")
                await asyncio.sleep(10)
                # Try clicking any verification buttons
                try:
                    verify_btn = page.locator("button, input[type='submit'], [class*='verify']").first
                    if await verify_btn.is_visible(timeout=3000):
                        await verify_btn.click()
                        await page.wait_for_load_state("networkidle", timeout=30000)
                except Exception:
                    pass
                content = await page.content()

            return content

        return await retry_with_backoff(
            _do_navigate,
            max_retries=self.max_retries,
            base_delay=3.0,
        )

    async def scrape_inventory(self) -> List[Dict]:
        """
        Scrape all vehicle listings from the inventory pages.

        Returns a list of vehicle data dicts with all specs and photos.
        """
        all_vehicles: List[Dict] = []
        errors: List[str] = []

        try:
            await self.start_browser()
            page = await self._context.new_page()

            # Navigate to inventory page
            inventory_url = f"{self.base_url}{INVENTORY_PATH}"
            current_page_num = 1
            total_pages_estimate = 1

            while inventory_url:
                logger.info(f"Scraping listing page {current_page_num}: {inventory_url}")
                await self._report_progress(
                    current_page=current_page_num,
                    total_pages=max(total_pages_estimate, current_page_num),
                    message=f"Scraping listing page {current_page_num}...",
                )

                try:
                    html = await self._navigate_with_retry(page, inventory_url)
                except Exception as e:
                    error_msg = f"Failed to load listing page {current_page_num}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    break

                # Parse vehicle stubs from listing
                stubs = parse_listing_page(html)
                logger.info(f"Found {len(stubs)} vehicle stubs on page {current_page_num}")

                if not stubs:
                    logger.info("No vehicles found on page, stopping pagination.")
                    break

                # Visit each vehicle detail page
                for idx, stub in enumerate(stubs):
                    detail_url = stub.get("detail_url", "")
                    if not detail_url:
                        continue

                    # Make URL absolute
                    if detail_url.startswith("/"):
                        detail_url = f"{self.base_url}{detail_url}"
                    elif not detail_url.startswith("http"):
                        detail_url = urljoin(inventory_url, detail_url)

                    await self._report_progress(
                        message=f"Page {current_page_num}: Scraping vehicle {idx + 1}/{len(stubs)}",
                        vehicles_found=len(all_vehicles),
                    )

                    await random_delay(self.delay_min, self.delay_max)

                    try:
                        detail_html = await self._navigate_with_retry(page, detail_url)
                        vehicle_data = parse_vehicle_detail(detail_html, detail_url)

                        if vehicle_data.get("vin"):
                            all_vehicles.append(vehicle_data)
                            logger.info(
                                f"Scraped: {vehicle_data.get('year')} "
                                f"{vehicle_data.get('make')} {vehicle_data.get('model')} "
                                f"VIN={vehicle_data.get('vin')}"
                            )
                        else:
                            logger.warning(f"No VIN found for vehicle at {detail_url}")
                            errors.append(f"No VIN found at {detail_url}")
                    except Exception as e:
                        error_msg = f"Error scraping detail page {detail_url}: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)

                # Check for next page
                next_url = find_next_page_url(html)
                if next_url:
                    if next_url.startswith("/"):
                        next_url = f"{self.base_url}{next_url}"
                    elif not next_url.startswith("http"):
                        next_url = urljoin(inventory_url, next_url)
                    inventory_url = next_url
                    current_page_num += 1
                    await random_delay(self.delay_min, self.delay_max)
                else:
                    inventory_url = None

            await self._report_progress(
                current_page=current_page_num,
                total_pages=current_page_num,
                vehicles_found=len(all_vehicles),
                message="Listing scrape complete.",
            )

        finally:
            await self.stop_browser()

        return all_vehicles, errors

    async def download_vehicle_images(self, vin: str, photo_urls: List[str]) -> List[str]:
        """
        Download vehicle images to media/{vin}/ directory.
        Automatically detects and removes dealer frame overlays.

        Returns list of local file paths.
        """
        if not photo_urls:
            return []

        vin_dir = Path(self.media_dir) / vin
        vin_dir.mkdir(parents=True, exist_ok=True)

        local_paths = []
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": get_random_user_agent()},
        ) as client:
            for idx, url in enumerate(photo_urls):
                try:
                    response = await client.get(url)
                    response.raise_for_status()

                    img_bytes = response.content

                    # Determine file extension
                    content_type = response.headers.get("content-type", "")
                    ext = ".jpg"
                    if "png" in content_type:
                        ext = ".png"
                    elif "webp" in content_type:
                        ext = ".webp"

                    # Detect and remove dealer frame overlay
                    if ext == ".jpg" and has_dealer_frame(img_bytes):
                        img_bytes = remove_dealer_frame(img_bytes)
                        logger.info(f"Removed dealer frame from {vin} photo {idx}")

                    filename = f"{idx:03d}{ext}"
                    filepath = vin_dir / filename
                    filepath.write_bytes(img_bytes)
                    local_paths.append(f"/media/{vin}/{filename}")

                except Exception as e:
                    logger.warning(f"Failed to download image {url}: {e}")

        return local_paths


def _is_challenge_page(html: str) -> bool:
    """Detect common bot-detection challenge pages."""
    indicators = [
        "challenge-running",
        "cf-browser-verification",
        "captcha",
        "recaptcha",
        "hcaptcha",
        "please verify",
        "checking your browser",
        "just a moment",
        "cloudflare",
        "ddos-guard",
    ]
    html_lower = html.lower()
    return any(indicator in html_lower for indicator in indicators)
