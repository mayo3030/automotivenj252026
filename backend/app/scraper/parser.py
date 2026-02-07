"""HTML parsing and data extraction for vehicle listings."""

import re
import logging
from typing import Dict, List, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def parse_listing_page(html: str) -> List[Dict[str, str]]:
    """
    Parse the inventory listing page and return a list of vehicle stubs.

    Each stub contains:
        - detail_url: link to the vehicle detail page
        - thumbnail: primary image URL (if available)
        - basic info parsed from the card
    """
    soup = BeautifulSoup(html, "lxml")
    vehicles = []

    # Common patterns for dealer inventory pages
    # Try multiple selectors for robustness
    cards = (
        soup.select(".vehicle-card")
        or soup.select("[class*='vehicle']")
        or soup.select("[class*='inventory'] a[href*='/vehicle/']")
        or soup.select(".listing-item")
        or soup.select("[data-vehicle]")
    )

    # Fallback: find all links that look like vehicle detail URLs
    if not cards:
        links = soup.find_all("a", href=True)
        for link in links:
            href = link["href"]
            if any(p in href.lower() for p in ["/vehicle/", "/inventory/", "/vdp/"]):
                # Avoid duplicate URLs
                if href not in [v.get("detail_url") for v in vehicles]:
                    vehicle_stub = _extract_stub_from_link(link, href)
                    if vehicle_stub:
                        vehicles.append(vehicle_stub)
        return vehicles

    for card in cards:
        stub = _extract_stub_from_card(card)
        if stub:
            vehicles.append(stub)

    return vehicles


def _extract_stub_from_link(element, href: str) -> Optional[Dict]:
    """Extract basic vehicle info from a link element."""
    text = element.get_text(separator=" ", strip=True)
    if len(text) < 3:
        return None

    img = element.find("img")
    thumbnail = img.get("src", "") or img.get("data-src", "") if img else ""

    return {
        "detail_url": href,
        "thumbnail": thumbnail,
        "title": text[:200],
    }


def _extract_stub_from_card(card) -> Optional[Dict]:
    """Extract basic vehicle info from a card element."""
    link = card.find("a", href=True) if card.name != "a" else card
    if not link:
        return None

    href = link.get("href", "")
    img = card.find("img")
    thumbnail = ""
    if img:
        thumbnail = img.get("src", "") or img.get("data-src", "") or img.get("data-lazy", "")

    title_el = card.find(["h2", "h3", "h4", ".vehicle-title", "[class*='title']"])
    title = title_el.get_text(strip=True) if title_el else card.get_text(separator=" ", strip=True)[:200]

    return {
        "detail_url": href,
        "thumbnail": thumbnail,
        "title": title,
    }


def find_next_page_url(html: str) -> Optional[str]:
    """Find the URL for the next page of listings."""
    soup = BeautifulSoup(html, "lxml")

    # Try common pagination patterns
    next_link = (
        soup.select_one("a.next")
        or soup.select_one("a[rel='next']")
        or soup.select_one("[class*='next'] a")
        or soup.select_one("a[aria-label='Next']")
        or soup.select_one("li.next a")
        or soup.select_one(".pagination a.next")
    )

    if next_link and next_link.get("href"):
        return next_link["href"]

    # Try numbered pagination: find the current active page + 1
    active = soup.select_one(".pagination .active, .pagination .current")
    if active:
        next_sib = active.find_next_sibling()
        if next_sib:
            link = next_sib.find("a", href=True) if next_sib.name != "a" else next_sib
            if link and link.get("href"):
                return link["href"]

    return None


def parse_vehicle_detail(html: str, detail_url: str = "") -> Dict:
    """
    Parse a vehicle detail page and extract all available specs.

    Returns a dict with keys matching the Vehicle model fields.
    """
    soup = BeautifulSoup(html, "lxml")
    data: Dict = {"detail_url": detail_url}

    # ── Extract title (year make model trim) ────────────────────────────────
    title_el = soup.select_one(
        "h1, .vehicle-title, [class*='vehicle-name'], [class*='vdp-title']"
    )
    if title_el:
        title_text = title_el.get_text(strip=True)
        parsed_title = _parse_vehicle_title(title_text)
        data.update(parsed_title)

    # ── Extract VIN ─────────────────────────────────────────────────────────
    vin = _extract_field(soup, ["vin"])
    if not vin:
        # Try regex on full page text
        text = soup.get_text()
        vin_match = re.search(r"\b([A-HJ-NPR-Z0-9]{17})\b", text)
        if vin_match:
            vin = vin_match.group(1)
    data["vin"] = vin

    # ── Extract stock number ────────────────────────────────────────────────
    data["stock_number"] = _extract_field(soup, ["stock", "stk", "stock number", "stock #", "stock no"])

    # ── Extract price ───────────────────────────────────────────────────────
    price_text = _extract_field(soup, ["price", "our price", "sale price", "internet price"])
    if not price_text:
        price_el = soup.select_one("[class*='price'], [data-price]")
        if price_el:
            price_text = price_el.get("data-price", "") or price_el.get_text(strip=True)
    data["price"] = _parse_price(price_text)

    # ── Extract mileage ─────────────────────────────────────────────────────
    mileage_text = _extract_field(soup, ["mileage", "miles", "odometer"])
    data["mileage"] = _parse_number(mileage_text)

    # ── Extract colors ──────────────────────────────────────────────────────
    data["exterior_color"] = _extract_field(soup, ["exterior color", "ext. color", "exterior", "ext color"])
    data["interior_color"] = _extract_field(soup, ["interior color", "int. color", "interior", "int color"])

    # ── Extract mechanical specs ────────────────────────────────────────────
    data["body_style"] = _extract_field(soup, ["body style", "body type", "body", "type"])
    data["drivetrain"] = _extract_field(soup, ["drivetrain", "drive type", "drive", "awd", "fwd", "rwd", "4wd"])
    data["engine"] = _extract_field(soup, ["engine", "motor"])
    data["transmission"] = _extract_field(soup, ["transmission", "trans"])
    data["trim"] = data.get("trim") or _extract_field(soup, ["trim", "trim level"])

    # ── Extract photos ──────────────────────────────────────────────────────
    data["photos"] = _extract_photos(soup)

    return data


def _parse_vehicle_title(title: str) -> Dict:
    """Parse 'YEAR MAKE MODEL TRIM' from title string."""
    result = {}
    title = title.strip()

    # Try to extract year
    year_match = re.search(r"\b(19|20)\d{2}\b", title)
    if year_match:
        result["year"] = int(year_match.group())
        # Remove year from title to parse make/model
        remaining = title[year_match.end():].strip()
    else:
        remaining = title

    # Split remaining into parts: first word = make, second = model, rest = trim
    parts = remaining.split()
    if len(parts) >= 1:
        result["make"] = parts[0]
    if len(parts) >= 2:
        result["model"] = parts[1]
    if len(parts) >= 3:
        result["trim"] = " ".join(parts[2:])

    return result


def _extract_field(soup: BeautifulSoup, labels: List[str]) -> Optional[str]:
    """
    Find a spec value by looking for label text in definition lists,
    tables, and label/value pairs.
    """
    text_lower_map = {}

    # Strategy 1: Look in <dt>/<dd> or <th>/<td> pairs
    for dt in soup.find_all(["dt", "th", "span", "label", "strong", "b"]):
        dt_text = dt.get_text(strip=True).lower().rstrip(":")
        for label in labels:
            if label.lower() in dt_text:
                # Find the next sibling value element
                value_el = dt.find_next_sibling(["dd", "td", "span", "div"])
                if value_el:
                    value = value_el.get_text(strip=True)
                    if value and len(value) < 200:
                        return value

    # Strategy 2: Look in list items or divs with label: value pattern
    for el in soup.find_all(["li", "div", "p", "tr"]):
        text = el.get_text(separator=" ", strip=True)
        for label in labels:
            pattern = re.compile(rf"{re.escape(label)}\s*[:|\-|–]\s*(.+)", re.IGNORECASE)
            match = pattern.search(text)
            if match:
                value = match.group(1).strip()
                if value and len(value) < 200:
                    return value

    return None


def _extract_photos(soup: BeautifulSoup) -> List[str]:
    """Extract all vehicle photo URLs from the page."""
    photos = []
    seen = set()

    # Look in gallery containers, sliders, or main image areas
    gallery = (
        soup.select("[class*='gallery'] img, [class*='slider'] img, [class*='carousel'] img")
        or soup.select("[class*='photo'] img, [class*='image'] img")
    )

    if not gallery:
        gallery = soup.find_all("img")

    for img in gallery:
        src = img.get("src", "") or img.get("data-src", "") or img.get("data-lazy", "")
        if not src:
            continue

        # Filter out icons, logos, placeholder images
        src_lower = src.lower()
        if any(skip in src_lower for skip in [
            "logo", "icon", "placeholder", "spinner", "loading",
            "pixel", "spacer", "blank", "widget", "badge",
            "1x1", "favicon",
        ]):
            continue

        # Normalize URL
        if src.startswith("//"):
            src = "https:" + src

        if src not in seen:
            seen.add(src)
            photos.append(src)

    return photos


def _parse_price(text: Optional[str]) -> Optional[float]:
    """Parse a price string like '$45,990' into a float."""
    if not text:
        return None
    cleaned = re.sub(r"[^\d.]", "", text)
    try:
        price = float(cleaned)
        return price if price > 0 else None
    except (ValueError, TypeError):
        return None


def _parse_number(text: Optional[str]) -> Optional[int]:
    """Parse a number string like '12,345 miles' into an int."""
    if not text:
        return None
    cleaned = re.sub(r"[^\d]", "", text)
    try:
        return int(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None
