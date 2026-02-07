"""
Standalone scrape script: scrape the FIRST PAGE of Automotive Avenues NJ
inventory (via ebizautos.com), visit every vehicle detail page,
extract full specs + every photo URL, download all photos locally, write to DB.

Can be run from the CLI:
    python scrape_real.py                          # manual run
    python scrape_real.py --task-id scrape-abc123   # launched by the API

When --task-id is supplied the script writes real-time progress to
.scrape_progress/<task_id>.json so the /api/scrape/status endpoint can
stream updates to the frontend.

Real site: https://autoavenj.ebizautos.com/used-cars.aspx
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
import random
import traceback
import httpx
from pathlib import Path

# ── Environment ──────────────────────────────────────────────────────────────
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./autoavenue.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6480/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6480/0")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6480/1")
os.environ.setdefault("MEDIA_DIR", "./media")

from app.database import AsyncSessionLocal, init_db          # noqa: E402
from app.models import Vehicle, ScrapeLog, ScrapeStatus, VehiclePriceHistory, VehicleChangeLog  # noqa: E402
from sqlalchemy import select                                 # noqa: E402
from datetime import datetime, timezone                       # noqa: E402

BASE = "https://autoavenj.ebizautos.com"
INVENTORY_URL = f"{BASE}/used-cars.aspx"
# Real paginated inventory endpoint — the vanity URL only returns page 1,
# and ?pg=N has no server-side effect.  The actual pagination uses
# inventory.aspx?_vstatus=3&_used=true&_page=N  (10 per page, ~74 pages).
INVENTORY_PAGINATED_URL = f"{BASE}/inventory.aspx?_vstatus=3&_used=true"
MEDIA_DIR = Path("./media")
MEDIA_DIR.mkdir(exist_ok=True)

PROGRESS_DIR = Path(".scrape_progress")
PROGRESS_DIR.mkdir(exist_ok=True)


# ── Progress helper ──────────────────────────────────────────────────────────

class ProgressWriter:
    """Writes live progress to a JSON file that the API reads."""

    def __init__(self, task_id: str | None):
        self.task_id = task_id
        self._path = PROGRESS_DIR / f"{task_id}.json" if task_id else None
        self._data = {
            "task_id": task_id,
            "status": "running",
            "progress": 0,
            "vehicles_found": 0,
            "vehicles_new": 0,
            "vehicles_updated": 0,
            "current_page": 1,
            "total_pages": 1,
            "message": "Initialising...",
        }

    def update(self, **kwargs):
        self._data.update(kwargs)
        self._flush()

    def _flush(self):
        if self._path:
            try:
                self._path.write_text(json.dumps(self._data))
            except OSError:
                pass

    @property
    def data(self):
        return dict(self._data)


# ── Playwright helpers ───────────────────────────────────────────────────────

async def launch_browser():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    )
    ctx = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1920, "height": 1080},
        java_script_enabled=True,
        ignore_https_errors=True,
    )
    return pw, browser, ctx


async def navigate(page, url, retries=3):
    """Navigate with retry."""
    for attempt in range(retries):
        try:
            print(f"  Navigating: {url}  (attempt {attempt+1})")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(1.5 + random.random())
            return
        except Exception as e:
            print(f"    Navigation error: {e}")
            if attempt < retries - 1:
                wait = 3 * (2 ** attempt) + random.random() * 2
                print(f"    Retrying in {wait:.1f}s...")
                await asyncio.sleep(wait)
            else:
                raise


async def get_listing_vehicles_page(page, page_num: int = 1):
    """Extract vehicle data from a single inventory page using JSON-LD + links."""
    url = f"{INVENTORY_PAGINATED_URL}&_page={page_num}"
    await navigate(page, url)

    json_ld_text = await page.evaluate("""
        () => {
            const script = document.querySelector('#application-ld_json-vehicle');
            return script ? script.textContent : null;
        }
    """)

    vehicles_basic = []
    if json_ld_text:
        try:
            data = json.loads(json_ld_text)
            vehicles_basic = data if isinstance(data, list) else [data]
        except json.JSONDecodeError:
            pass

    detail_links = await page.evaluate("""
        () => {
            const links = document.querySelectorAll('a[href*="details-"]');
            return [...new Set([...links].map(a => a.href))];
        }
    """)

    # Detect if there's a next page using the real pagination URL pattern
    has_next = await page.evaluate(f"""
        () => {{
            const links = document.querySelectorAll('a[href*="_page="]');
            for (const a of links) {{
                if (a.href.includes('_page={page_num + 1}')) return true;
            }}
            return false;
        }}
    """)

    print(f"  Page {page_num}: JSON-LD vehicles: {len(vehicles_basic)}, Detail links: {len(detail_links)}, Has next: {has_next}")

    result = []
    ld_urls = {}
    for v in vehicles_basic:
        vurl = v.get("url", "")
        if vurl.startswith("//"):
            vurl = "https:" + vurl
        elif vurl.startswith("/"):
            vurl = BASE + vurl
        ld_urls[vurl.rstrip("/")] = v
        result.append({"json_ld": v, "detail_url": vurl})

    for link in detail_links:
        if link.rstrip("/") not in ld_urls:
            result.append({"json_ld": None, "detail_url": link})

    return result, has_next


async def get_all_listing_vehicles(page, max_pages: int = 1, progress: 'ProgressWriter' = None):
    """Scrape listings from one or more inventory pages.
    
    max_pages: 1 = first page only, N = first N pages, 0 = ALL pages.
    """
    all_listings = []
    page_num = 1
    seen_urls = set()

    while True:
        if progress:
            progress.update(message=f"Loading inventory page {page_num}...", current_page=page_num)

        listings, has_next = await get_listing_vehicles_page(page, page_num)

        # Deduplicate
        for item in listings:
            url_key = item["detail_url"].rstrip("/")
            if url_key not in seen_urls:
                seen_urls.add(url_key)
                all_listings.append(item)

        if not has_next:
            break
        if max_pages != 0 and page_num >= max_pages:
            break

        page_num += 1
        await asyncio.sleep(1.5 + random.random())  # polite delay between pages

    if progress:
        progress.update(total_pages=page_num)

    return all_listings, page_num


async def scrape_detail_page(page, detail_url):
    """Navigate to a vehicle detail page and extract ALL specs + ALL photos."""
    await navigate(page, detail_url)

    vehicle_json = await page.evaluate("""
        () => {
            const scripts = document.querySelectorAll('script[type="application/ld+json"]');
            for (const s of scripts) {
                try {
                    const data = JSON.parse(s.textContent);
                    if (data['@type'] === 'Vehicle') return data;
                } catch {}
            }
            return null;
        }
    """)

    specs = await page.evaluate("""
        () => {
            const result = {};
            const rows = document.querySelectorAll('table tr');
            for (const row of rows) {
                const cells = row.querySelectorAll('td, th');
                if (cells.length >= 2) {
                    const label = cells[0].textContent.trim().replace(/[:#]/g, '').toLowerCase();
                    const value = cells[1].textContent.trim();
                    if (label && value && label.length < 40) result[label] = value;
                }
            }
            const dts = document.querySelectorAll('dt');
            for (const dt of dts) {
                const dd = dt.nextElementSibling;
                if (dd && dd.tagName === 'DD') {
                    const label = dt.textContent.trim().replace(/[:#]/g, '').toLowerCase();
                    const value = dd.textContent.trim();
                    if (label && value) result[label] = value;
                }
            }
            return result;
        }
    """)

    raw_photo_urls = await page.evaluate("""
        () => {
            const urls = [];
            const allEls = document.querySelectorAll('img, a[data-src], [data-image]');
            for (const el of allEls) {
                for (const attr of ['src', 'data-src', 'data-lazy', 'data-image']) {
                    const val = el.getAttribute(attr);
                    if (val && val.includes('ebizautos.media')) {
                        let url = val;
                        if (url.startsWith('//')) url = 'https:' + url;
                        urls.push(url);
                    }
                }
            }
            return urls;
        }
    """)

    listing_id = None
    if vehicle_json and vehicle_json.get("image"):
        m = re.search(r'-(\d{7,8})-\d+-\d+\.jpg', vehicle_json["image"])
        if m:
            listing_id = m.group(1)
    if not listing_id:
        for u in raw_photo_urls:
            m = re.search(r'-(\d{7,8})-\d+-\d+\.jpg', u)
            if m:
                listing_id = m.group(1)
                break

    best_per_seq = {}
    for u in raw_photo_urls:
        m = re.search(r'-(\d{7,8})-(\d+)-(\d+)\.jpg', u)
        if not m:
            continue
        url_listing = m.group(1)
        photo_seq = int(m.group(2))
        resolution = int(m.group(3))
        if listing_id and url_listing != listing_id:
            continue
        if photo_seq not in best_per_seq or resolution > best_per_seq[photo_seq][0]:
            best_per_seq[photo_seq] = (resolution, u)

    photos = [url for _, (_, url) in sorted(best_per_seq.items())]

    title = await page.evaluate("""
        () => {
            const h1 = document.querySelector('h1');
            return h1 ? h1.textContent.trim() : '';
        }
    """)

    return {
        "json_ld": vehicle_json,
        "specs": specs,
        "photos": photos,
        "title": title,
        "detail_url": detail_url,
    }


# ── Vehicle record builder ───────────────────────────────────────────────────

def build_vehicle_record(listing_ld, detail_data):
    jld = detail_data.get("json_ld") or listing_ld or {}
    specs = detail_data.get("specs", {})
    title = detail_data.get("title", "")

    record = {}

    record["vin"] = (
        jld.get("vehicleIdentificationNumber", "")
        or specs.get("vin", "")
        or specs.get("vin #", "")
    ).upper().strip()

    record["stock_number"] = (
        jld.get("sku", "")
        or specs.get("stock", "")
        or specs.get("stock #", "")
    ).strip()

    year_str = jld.get("vehicleModelDate", "")
    if year_str:
        try:
            record["year"] = int(year_str)
        except (ValueError, TypeError):
            pass
    if not record.get("year") and title:
        m = re.search(r'\b(19|20)\d{2}\b', title)
        if m:
            record["year"] = int(m.group())

    record["make"] = (jld.get("brand") or jld.get("manufacturer") or "").strip()

    model_full = (jld.get("model") or "").strip()
    if model_full and record["make"]:
        parts = model_full.split(None, 1)
        record["model"] = parts[0] if parts else model_full
        record["trim"] = parts[1] if len(parts) > 1 else ""
    elif title:
        m = re.match(r'\d{4}\s+(\S+)\s+(\S+)\s*(.*)', title)
        if m:
            record["make"] = record["make"] or m.group(1)
            record["model"] = m.group(2)
            record["trim"] = m.group(3).strip()

    price_str = ""
    offers = jld.get("offers", [])
    if offers:
        offer = offers[0] if isinstance(offers, list) else offers
        price_str = str(offer.get("price", ""))
    if not price_str:
        price_str = specs.get("price", "") or specs.get("our price", "")
    cleaned = re.sub(r'[^\d.]', '', price_str)
    try:
        record["price"] = float(cleaned) if cleaned else None
    except ValueError:
        record["price"] = None

    mileage_str = (
        jld.get("mileageFromOdometer", "")
        or specs.get("miles", "")
        or specs.get("mileage", "")
    )
    cleaned = re.sub(r'[^\d]', '', str(mileage_str))
    try:
        record["mileage"] = int(cleaned) if cleaned else None
    except ValueError:
        record["mileage"] = None

    record["exterior_color"] = (
        jld.get("color", "")
        or specs.get("exterior color", "")
        or specs.get("exterior", "")
    ).strip()

    record["interior_color"] = (
        jld.get("vehicleInteriorColor", "")
        or specs.get("interior", "")
        or specs.get("interior color", "")
    ).strip()

    record["body_style"] = (
        specs.get("body style", "")
        or specs.get("body type", "")
        or specs.get("body", "")
    ).strip()

    record["drivetrain"] = (
        specs.get("drivetrain", "")
        or specs.get("drive type", "")
        or specs.get("drive", "")
    ).strip()

    record["engine"] = (
        specs.get("engine", "")
        or specs.get("motor", "")
    ).strip()

    record["transmission"] = (
        specs.get("transmission", "")
        or specs.get("trans", "")
    ).strip()

    record["detail_url"] = detail_data.get("detail_url", "")
    record["remote_photos"] = detail_data.get("photos", [])

    return record


# ── Dealer-frame detection / removal ─────────────────────────────────────────
# The "Automotive Avenues" frame has:
#   - Top-left: logo with blue swoosh + "AUTOMOTIVE Avenues" text (~13% of height)
#   - Bottom-right: "www.automotiveavenuesnj.com" URL bar (~7% of height)
# Old approach used inpainting which created ugly smeared artifacts.
# New approach: simple crop — removes the frame strips cleanly.

def has_dealer_frame(img_bytes):
    """Detect whether image has the Automotive Avenues dealer frame overlay."""
    import numpy as np
    from PIL import Image
    from io import BytesIO
    try:
        img = Image.open(BytesIO(img_bytes))
        arr = np.array(img)
        h, w = arr.shape[:2]
        if h < 100 or w < 100:
            return False

        # Check top-left area for white/bright region (logo background)
        tl_h, tl_w = int(h * 0.12), int(w * 0.30)
        tl = arr[0:tl_h, 0:tl_w, :]
        tl_white = np.sum(np.all(tl > 230, axis=2)) / (tl_h * tl_w) * 100

        # Check bottom-right area for white/bright region (URL bar)
        br_h, br_w = int(h * 0.07), int(w * 0.50)
        br = arr[-br_h:, -br_w:, :]
        br_white = np.sum(np.all(br > 230, axis=2)) / (br_h * br_w) * 100

        # Frame is present if BOTH top-left logo area AND bottom URL bar are
        # predominantly white/bright
        return tl_white > 40 and br_white > 30
    except Exception:
        return False


def remove_dealer_frame(img_bytes):
    """Remove dealer frame by cropping — much cleaner than inpainting.

    Crops away:
      - Top 13% (Automotive Avenues logo + blue swoosh)
      - Bottom 7% (www.automotiveavenuesnj.com URL bar)
    Returns the JPEG bytes of the cropped image.
    """
    from PIL import Image
    from io import BytesIO
    try:
        img = Image.open(BytesIO(img_bytes))
        w, h = img.size
        if h < 100 or w < 100:
            return img_bytes

        # Crop percentages — tuned for Automotive Avenues ebizautos frame
        top_pct = 0.13   # top 13% contains logo + blue swoosh
        bot_pct = 0.07   # bottom 7% contains URL bar

        top_px = int(h * top_pct)
        bot_px = int(h * bot_pct)

        cropped = img.crop((0, top_px, w, h - bot_px))

        out = BytesIO()
        cropped.save(out, format="JPEG", quality=95)
        return out.getvalue()
    except Exception as e:
        print(f"      Frame removal (crop) error: {e}")
        return img_bytes


# ── Photo downloader ─────────────────────────────────────────────────────────

async def download_photos(vin, photo_urls):
    """Download all photos for a vehicle. Returns only local /media/... paths."""
    if not photo_urls or not vin:
        return []
    vin_dir = MEDIA_DIR / vin
    vin_dir.mkdir(parents=True, exist_ok=True)

    local_paths = []
    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
        },
    ) as client:
        for idx, url in enumerate(photo_urls):
            try:
                hires_url = re.sub(r'-(\d+)\.jpg$', '-1024.jpg', url)
                resp = await client.get(hires_url)
                if resp.status_code != 200:
                    resp = await client.get(url)
                resp.raise_for_status()

                img_bytes = resp.content
                ct = resp.headers.get("content-type", "")
                ext = ".jpg"
                if "png" in ct:
                    ext = ".png"
                elif "webp" in ct:
                    ext = ".webp"

                frame_status = ""
                if ext == ".jpg" and has_dealer_frame(img_bytes):
                    img_bytes = remove_dealer_frame(img_bytes)
                    frame_status = " [FRAME REMOVED]"

                fname = f"{idx+1:03d}{ext}"
                fpath = vin_dir / fname
                fpath.write_bytes(img_bytes)
                local_paths.append(f"/media/{vin}/{fname}")
                size_kb = len(img_bytes) // 1024
                print(f"      [{idx+1}/{len(photo_urls)}] {fname} ({size_kb}KB){frame_status}")
            except Exception as e:
                print(f"      [{idx+1}/{len(photo_urls)}] FAILED: {e}")
    return local_paths


# ── Main ─────────────────────────────────────────────────────────────────────

async def main(task_id: str | None = None, max_pages: int = 1):
    start_time = time.time()
    pw_obj = None
    progress = ProgressWriter(task_id)
    pages_label = "all" if max_pages == 0 else str(max_pages)

    print("=" * 72)
    print("  AutoAvenue Real Scraper")
    print(f"  Task ID: {task_id or '(manual)'}")
    print(f"  Pages: {pages_label}")
    print("  Source: https://autoavenj.ebizautos.com/used-cars.aspx")
    print("=" * 72)

    progress.update(message="Initialising database...")

    # Initialise DB tables (idempotent)
    await init_db()

    # Launch browser
    print("\n[BROWSER] Launching Playwright Chromium...")
    progress.update(message="Launching browser...", progress=5)
    pw_obj, browser, ctx = await launch_browser()
    page = await ctx.new_page()

    all_vehicles = []
    errors = []

    try:
        # ── Step 1: Get listing data from pages ──────────────────────────
        print("\n" + "-" * 72)
        print(f"[STEP 1] Loading inventory pages (max={pages_label})...")
        print("-" * 72)
        progress.update(message=f"Loading inventory pages ({pages_label})...", progress=10)

        listings, total_pages = await get_all_listing_vehicles(page, max_pages, progress)
        total = len(listings)
        print(f"\n  => Found {total} vehicles across {total_pages} page(s).\n")

        if not total:
            errors.append("No vehicles found!")
            print("  ERROR: No vehicles found.")
            progress.update(
                status="failed", progress=0,
                message="No vehicles found on the inventory page.",
            )
            return

        progress.update(
            vehicles_found=total, total_pages=total_pages, current_page=total_pages,
            message=f"Found {total} vehicles across {total_pages} page(s). Scraping details...",
            progress=15,
        )

        # ── Step 2: Visit each detail page ───────────────────────────────
        print("-" * 72)
        print(f"[STEP 2] Scraping {total} detail pages...")
        print("-" * 72)

        for idx, listing in enumerate(listings):
            detail_url = listing["detail_url"]
            listing_ld = listing.get("json_ld")
            vin_hint = listing_ld.get("vehicleIdentificationNumber", "") if listing_ld else ""

            pct = 15 + int((idx / total) * 70)  # 15 -> 85 across vehicles
            progress.update(
                progress=pct,
                message=f"Scraping vehicle {idx+1}/{total}... {vin_hint}",
            )

            print(f"\n  ┌─ Vehicle {idx+1}/{total} {'─' * 40}")
            if vin_hint:
                print(f"  │ VIN hint: {vin_hint}")
            print(f"  │ URL: {detail_url}")

            delay = random.uniform(2, 4)
            await asyncio.sleep(delay)

            try:
                detail_data = await scrape_detail_page(page, detail_url)
                record = build_vehicle_record(listing_ld, detail_data)

                if not record.get("vin"):
                    err = f"No VIN found at {detail_url}"
                    print(f"  │ WARNING: {err}")
                    errors.append(err)
                    continue

                vin = record["vin"]
                print(f"  │ {record.get('year', '?')} {record.get('make', '?')} {record.get('model', '?')} {record.get('trim', '')}")
                print(f"  │ VIN: {vin}")
                price = record.get("price")
                print(f"  │ Price: ${price:,.0f}" if price else "  │ Price: N/A")
                mil = record.get("mileage")
                print(f"  │ Mileage: {mil:,}" if mil else "  │ Mileage: N/A")

                remote_photos = record.pop("remote_photos", [])
                print(f"  │ Photos found: {len(remote_photos)}")

                if remote_photos:
                    print("  │ Downloading photos...")
                    local_paths = await download_photos(vin, remote_photos)
                    record["photos"] = local_paths  # only local paths
                    print(f"  │ Downloaded: {len(local_paths)}/{len(remote_photos)}")
                else:
                    record["photos"] = []

                all_vehicles.append(record)
                print("  └─ OK")

            except Exception as e:
                err = f"Error scraping {detail_url}: {e}"
                print(f"  │ ERROR: {err}")
                print("  └─ FAILED")
                errors.append(err)

    finally:
        if pw_obj:
            try:
                await ctx.close()
                await browser.close()
                await pw_obj.stop()
            except Exception:
                pass
        print("\n[BROWSER] Closed.")

    # ── Step 3: Upsert to database ───────────────────────────────────────
    print("\n" + "-" * 72)
    print(f"[STEP 3] Saving {len(all_vehicles)} vehicles to database...")
    print("-" * 72)
    progress.update(progress=88, message="Saving to database...")

    vehicles_new = 0
    vehicles_updated = 0
    now = datetime.now(timezone.utc)
    _tracked_fields = (
        "stock_number", "year", "make", "model", "trim",
        "price", "mileage", "exterior_color", "interior_color",
        "body_style", "drivetrain", "engine", "transmission",
        "detail_url",
    )

    async with AsyncSessionLocal() as session:
        scraped_vins = set()

        for v in all_vehicles:
            vin = v.get("vin")
            if not vin:
                continue
            scraped_vins.add(vin)

            result = await session.execute(
                select(Vehicle).where(Vehicle.vin == vin)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # ── Detect per-field changes and log them ────────────────
                changed_fields = []
                for field in _tracked_fields:
                    old_val = getattr(existing, field)
                    new_val = v.get(field)
                    # Normalize for comparison
                    old_str = str(old_val) if old_val is not None else ""
                    new_str = str(new_val) if new_val is not None else ""
                    if old_str != new_str:
                        changed_fields.append((field, old_str, new_str))
                        session.add(VehicleChangeLog(
                            vin=vin, changed_at=now, change_type="updated",
                            field_name=field, old_value=old_str, new_value=new_str,
                            task_id=task_id,
                        ))

                # If price changed, also record in price history
                old_price = existing.price
                new_price = v.get("price")
                if str(old_price or "") != str(new_price or ""):
                    session.add(VehiclePriceHistory(
                        vin=vin, price=new_price, recorded_at=now, source="scrape",
                    ))

                # Was inactive, now back? Log reactivation
                if not existing.is_active:
                    session.add(VehicleChangeLog(
                        vin=vin, changed_at=now, change_type="reactivated",
                        field_name="is_active", old_value="False", new_value="True",
                        task_id=task_id,
                    ))

                # Apply all field updates
                for field in _tracked_fields:
                    setattr(existing, field, v.get(field))
                existing.photos = v.get("photos", existing.photos)
                existing.is_active = True
                existing.updated_at = now
                vehicles_updated += 1

                if changed_fields:
                    names = ", ".join(f[0] for f in changed_fields)
                    print(f"  Updated: {vin} (changed: {names})")
                else:
                    print(f"  Updated: {vin} (no data changes)")
            else:
                # ── New vehicle ──────────────────────────────────────────
                session.add(Vehicle(
                    vin=vin,
                    stock_number=v.get("stock_number"),
                    year=v.get("year"),
                    make=v.get("make"),
                    model=v.get("model"),
                    trim=v.get("trim"),
                    price=v.get("price"),
                    mileage=v.get("mileage"),
                    exterior_color=v.get("exterior_color"),
                    interior_color=v.get("interior_color"),
                    body_style=v.get("body_style"),
                    drivetrain=v.get("drivetrain"),
                    engine=v.get("engine"),
                    transmission=v.get("transmission"),
                    photos=v.get("photos", []),
                    detail_url=v.get("detail_url"),
                    is_active=True,
                ))
                session.add(VehicleChangeLog(
                    vin=vin, changed_at=now, change_type="new",
                    field_name=None, old_value=None, new_value=None,
                    task_id=task_id,
                ))
                if v.get("price") is not None:
                    session.add(VehiclePriceHistory(
                        vin=vin, price=v.get("price"), recorded_at=now, source="scrape",
                    ))
                vehicles_new += 1
                print(f"  New: {vin}")

        # Mark vehicles no longer on the page as inactive
        vehicles_removed = 0
        all_result = await session.execute(
            select(Vehicle).where(Vehicle.is_active == True)  # noqa: E712
        )
        for veh in all_result.scalars().all():
            if veh.vin not in scraped_vins:
                veh.is_active = False
                session.add(VehicleChangeLog(
                    vin=veh.vin, changed_at=now, change_type="removed",
                    field_name="is_active", old_value="True", new_value="False",
                    task_id=task_id,
                ))
                vehicles_removed += 1

        # ── Write / update the ScrapeLog row ──────────────────────────────
        elapsed = time.time() - start_time
        log_msg = (
            f"Scrape completed in {elapsed:.0f}s. "
            f"{len(all_vehicles)} vehicles found, "
            f"{vehicles_new} new, {vehicles_updated} updated, "
            f"{vehicles_removed} removed."
        )

        if task_id:
            # Update the ScrapeLog row that the API already created
            log_result = await session.execute(
                select(ScrapeLog).where(ScrapeLog.task_id == task_id)
            )
            log_row = log_result.scalar_one_or_none()
            if log_row:
                log_row.status = ScrapeStatus.COMPLETED
                log_row.finished_at = datetime.now(timezone.utc)
                log_row.vehicles_found = len(all_vehicles)
                log_row.vehicles_new = vehicles_new
                log_row.vehicles_updated = vehicles_updated
                log_row.vehicles_removed = vehicles_removed
                log_row.errors = errors
                log_row.log_output = log_msg
            else:
                # Shouldn't happen, but create one anyway
                session.add(ScrapeLog(
                    task_id=task_id,
                    status=ScrapeStatus.COMPLETED,
                    finished_at=datetime.now(timezone.utc),
                    vehicles_found=len(all_vehicles),
                    vehicles_new=vehicles_new,
                    vehicles_updated=vehicles_updated,
                    vehicles_removed=vehicles_removed,
                    errors=errors,
                    log_output=log_msg,
                ))
        else:
            # Manual CLI run — always create a new log row
            session.add(ScrapeLog(
                task_id=f"manual-{int(time.time())}",
                status=ScrapeStatus.COMPLETED,
                finished_at=datetime.now(timezone.utc),
                vehicles_found=len(all_vehicles),
                vehicles_new=vehicles_new,
                vehicles_updated=vehicles_updated,
                vehicles_removed=vehicles_removed,
                errors=errors,
                log_output=log_msg,
            ))

        await session.commit()
        print(f"  => Committed to DB. New={vehicles_new}, Updated={vehicles_updated}, Removed={vehicles_removed}")

    # ── Final progress update ────────────────────────────────────────────
    progress.update(
        status="completed",
        progress=100,
        vehicles_found=len(all_vehicles),
        vehicles_new=vehicles_new,
        vehicles_updated=vehicles_updated,
        message=log_msg,
    )

    elapsed = time.time() - start_time
    total_local = sum(
        len([p for p in v.get("photos", []) if p.startswith("/media")])
        for v in all_vehicles
    )
    print(f"\n{'=' * 72}")
    print(f"  SCRAPE COMPLETE — {len(all_vehicles)} vehicles, {len(errors)} errors, {elapsed:.1f}s")
    print(f"  Photos downloaded: {total_local}")
    print(f"{'=' * 72}")


# ── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AutoAvenue real scraper")
    parser.add_argument("--task-id", default=None, help="Task ID from the API trigger")
    parser.add_argument("--pages", default="1", help="Pages to scrape: 1, N, or 0 for all")
    args = parser.parse_args()

    try:
        max_pages = int(args.pages)
    except ValueError:
        max_pages = 1

    try:
        asyncio.run(main(task_id=args.task_id, max_pages=max_pages))
    except Exception:
        # If launched with a task_id, write a failure progress file so the
        # frontend shows the error instead of spinning forever.
        if args.task_id:
            fail_path = PROGRESS_DIR / f"{args.task_id}.json"
            fail_path.write_text(json.dumps({
                "task_id": args.task_id,
                "status": "failed",
                "progress": 0,
                "vehicles_found": 0,
                "vehicles_new": 0,
                "vehicles_updated": 0,
                "current_page": 0,
                "total_pages": 0,
                "message": f"Scraper crashed: {traceback.format_exc()[-300:]}",
            }))

            # Also update the DB row
            try:
                import sqlite3
                db_path = Path("autoavenue.db")
                if db_path.exists():
                    conn = sqlite3.connect(str(db_path))
                    conn.execute(
                        "UPDATE scrape_logs SET status = 'FAILED', "
                        "log_output = ? WHERE task_id = ?",
                        (f"Crashed: {traceback.format_exc()[-500:]}", args.task_id),
                    )
                    conn.commit()
                    conn.close()
            except Exception:
                pass

        traceback.print_exc()
        sys.exit(1)
