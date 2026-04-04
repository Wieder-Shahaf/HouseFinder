"""Madlan scraper: Playwright+stealth browser automation (Playwright-first, per D-01).

Fetches Haifa rental listings from Madlan filtered to target neighborhoods
(כרמל, מרכז העיר, נווה שאנן) and price <= settings.yad2_price_max.

Usage:
    from app.scrapers.madlan import run_madlan_scraper
    result = await run_madlan_scraper(db)

=============================================================================
DevTools Discovery Findings (2026-04-03)
=============================================================================

Method: Playwright headless browser + network interception + httpx probing
Target: https://www.madlan.co.il/rent/haifa

1. BOT PROTECTION:
   Madlan uses PerimeterX + Cloudflare WAF.
   - All requests from datacenter/CI IPs receive 403 + captcha challenge page.
   - The captcha page contains: <script src="/o4wPDYYd/captcha/PXo4wPDYYd/captcha.js">
   - Detection keywords to check: "px-captcha", "PXo4wPDYYd", "perimeterx", "captcha"
   - WORKAROUND: Must run from residential IP OR use Bright Data Web Unlocker proxy.
   - playwright-stealth + proxy + persistent profile is the correct approach.

2. LISTING URL PATTERN (confirmed from sitemap):
   Individual listing: https://www.madlan.co.il/listings/{id}
   where {id} is a short alphanumeric slug, e.g. "EaW4wX1L38K", "lOrHhKgErxG"
   Sitemap URL: https://www.madlan.co.il/sitemap/listings__index.xml

3. API ENDPOINT:
   robots.txt discloses: /api2/ and /getBulletines
   The /api2/ endpoint path appears to be /api2/bulletines (historical usage pattern)
   This endpoint requires a session cookie ("a1" token) obtained via browser navigation.
   Attempting /api2/bulletines directly returns "sorry a1" (missing session auth).

4. DATA EXTRACTION STRATEGY:
   Primary:   XHR interception via page.on("response") to capture api2 JSON responses.
              After browser navigation, api2 calls carry session cookies automatically.
              Look for responses from api2/* or containing "bulletines" / "listings".
   Secondary: __NEXT_DATA__ extraction from page HTML.
              Madlan is a Next.js/React SPA - listing data may be embedded in
              props.pageProps after server-side rendering.
   Tertiary:  DOM parsing via BeautifulSoup as last resort.

5. FIELD MAPPING (inferred from Madlan's known data structure and sitemap):
   The Madlan listing object typically contains:
     id / bulletinId   → source_id (short alphanumeric slug, stable per sitemap)
     price             → price (integer, NIS/month)
     rooms             → rooms (float, e.g. 3.0 or 3.5)
     squareMeter       → size_sqm (integer, square meters)
     address.city.text     → city
     address.neighborhood.text → neighborhood
     address.street.text   → street
     address.houseNum      → house number
     coordinates.lat / lon → lat / lng
     contactName       → contact_info
     publishedAt / updatedAt → post_date
     description / title   → title
   URL: https://www.madlan.co.il/listings/{id}

6. PAGINATION:
   Madlan uses infinite scroll (similar to Yad2).
   Scroll-to-load pattern: scroll down, wait for new items, repeat until stable.
   URL parameter `page` may also exist for pagination.

7. HAIFA FILTER URL:
   https://www.madlan.co.il/rent/haifa
   Additional price param: ?maxPrice=4500 (to be verified at runtime)
=============================================================================
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.config import settings
from app.llm.verifier import batch_verify_listings, merge_llm_fields
from app.models.listing import Listing
from app.scrapers.base import ScraperResult
from app.scrapers.proxy import get_proxy_launch_args, is_proxy_enabled

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Playwright browser fetch
# ---------------------------------------------------------------------------


async def fetch_madlan_browser(url: str) -> list[dict]:
    """Use Playwright+stealth to render the Madlan rental page and extract listings.

    Strategy 1 (primary): Intercept XHR/fetch responses during page load.
      Madlan's api2 endpoint returns structured JSON when the browser navigates
      with valid session cookies. We capture these responses via page.on("response").

    Strategy 2 (secondary): Extract from __NEXT_DATA__ embedded JSON.
      Madlan is a Next.js SPA - listing data may be server-rendered into the page.

    Strategy 3 (tertiary): DOM parsing with BeautifulSoup if neither above works.
    """
    import asyncio
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth  # 2.x API: Stealth().apply_stealth_async(page)

    # Persist browser profile to maintain session cookies between runs.
    # SEPARATE from Yad2's ~/.yad2-browser-profile to prevent session contamination.
    user_data_dir = os.path.expanduser("~/.madlan-browser-profile")
    os.makedirs(user_data_dir, exist_ok=True)
    # Remove stale lock file left by previous crash/container restart
    singleton_lock = os.path.join(user_data_dir, "SingletonLock")
    if os.path.exists(singleton_lock):
        os.remove(singleton_lock)

    if is_proxy_enabled():
        logger.info("[madlan] Bright Data Web Unlocker proxy enabled for Playwright")
    logger.info("[madlan] Starting Playwright (headless=True, persistent profile)")

    captured_api_listings: list[dict] = []
    api_response_received = asyncio.Event()

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=True,
            locale="he-IL",
            viewport={"width": 1280, "height": 800},
            extra_http_headers={"Accept-Language": "he-IL,he;q=0.9"},
            ignore_https_errors=True,  # Bright Data Web Unlocker does MITM SSL interception
            **get_proxy_launch_args(),
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        # Strategy 1: Intercept XHR/fetch API responses
        async def handle_response(response):
            resp_url = response.url
            content_type = response.headers.get("content-type", "")
            is_json = "json" in content_type
            # Log all JSON responses so we can discover the real API endpoint
            if is_json and response.status == 200:
                logger.info(f"[madlan] JSON response: {resp_url[:120]}")
            # Capture api2 bulletines/listings responses (JSON only)
            is_api = any(
                x in resp_url
                for x in ["api2", "bulletines", "getBulletines", "listings", "rent", "for-rent", "search", "properties"]
            )
            if is_api and is_json and response.status == 200:
                try:
                    body = await response.body()
                    if body:
                        data = json.loads(body)
                        listings = _extract_listings_from_api(data, resp_url)
                        if listings:
                            logger.info(
                                f"[madlan] XHR captured {len(listings)} listings from {resp_url}"
                            )
                            captured_api_listings.extend(listings)
                            api_response_received.set()
                        else:
                            logger.info(f"[madlan] API URL matched but 0 listings extracted from {resp_url[:80]}")
                except Exception as e:
                    logger.debug(f"[madlan] Error parsing response from {resp_url}: {e}")

        page.on("response", handle_response)

        logger.warning(f"[madlan] Navigating to: {url}")
        try:
            resp = await page.goto(url, wait_until="load", timeout=60000)
            logger.warning(f"[madlan] goto returned status={resp.status if resp else 'None'}, url={page.url}")
        except Exception as nav_err:
            logger.error(f"[madlan] goto failed: {nav_err}")
            return []

        # Wait for initial JS hydration
        INITIAL_WAIT_MS = 6000
        await page.wait_for_timeout(INITIAL_WAIT_MS)

        # Scroll-to-load constants — mirrors Yad2 pattern
        MAX_SCROLLS = 8
        SCROLL_PAUSE_MS = 2000

        prev_height = await page.evaluate("document.body.scrollHeight")
        for i in range(1, MAX_SCROLLS + 1):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(SCROLL_PAUSE_MS)
            new_height = await page.evaluate("document.body.scrollHeight")
            logger.info(f"[madlan] Scroll {i}: page height {prev_height} -> {new_height}")
            if new_height == prev_height:
                logger.info(
                    f"[madlan] Scroll loop: no new content after {i} iterations — stopping"
                )
                break
            prev_height = new_height

        # Scroll back to top
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(1000)

        content = await page.content()
        await context.close()

    # Diagnostic: save HTML to temp file for inspection
    debug_path = "/tmp/madlan_debug.html"
    try:
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"[madlan] DEBUG: saved page HTML ({len(content)} bytes) to {debug_path}")
    except Exception as e:
        logger.warning(f"[madlan] DEBUG: could not write debug HTML: {e}")

    # Bot detection check — only bail on actual CAPTCHA challenge pages.
    # PXo4wPDYYd / perimeterx scripts appear on every Madlan page for real users too
    # (monitoring, not blocking). A real block page is short (<50KB) AND has challenge UI.
    hard_block_keywords = ["px-captcha", "challenge-form", "cf-challenge", "access denied"]
    is_short_page = len(content) < 50_000
    is_hard_block = any(kw.lower() in content.lower() for kw in hard_block_keywords)
    if is_short_page and is_hard_block:
        logger.warning(
            "[madlan] Bot-detection CAPTCHA page detected (short page + challenge UI). "
            "Inspect /tmp/madlan_debug.html for details."
        )
        return []
    if is_short_page and len(content) < 10_000:
        logger.warning(
            "[madlan] Page suspiciously short (%d bytes) — possible block. "
            "Inspect /tmp/madlan_debug.html for details.",
            len(content),
        )
        return []

    # If XHR interception captured listings, use them (Strategy 1)
    if captured_api_listings:
        logger.info(
            f"[madlan] Strategy 1 (XHR): captured {len(captured_api_listings)} listings total"
        )
        return captured_api_listings

    # Strategy 2: Extract from __NEXT_DATA__ embedded JSON
    next_data_listings = _extract_from_nextdata(content)
    if next_data_listings:
        logger.info(
            f"[madlan] Strategy 2 (__NEXT_DATA__): extracted {len(next_data_listings)} listings"
        )
        return next_data_listings

    # Strategy 3: DOM parsing fallback
    dom_listings = _extract_from_dom(content)
    if dom_listings:
        logger.info(
            f"[madlan] Strategy 3 (DOM): extracted {len(dom_listings)} listings"
        )
        return dom_listings

    logger.warning("[madlan] All extraction strategies returned 0 listings")
    return []


# ---------------------------------------------------------------------------
# Data extraction helpers
# ---------------------------------------------------------------------------


def _extract_listings_from_api(data: Any, url: str) -> list[dict]:
    """Extract listing items from a captured Madlan API response.

    Madlan api2/bulletines returns JSON with a listings array.
    The exact key path varies — we search recursively for arrays of listing objects.
    """
    if not isinstance(data, (dict, list)):
        return []

    listings: list[dict] = []

    def _find_listings(obj: Any, depth: int = 0) -> None:
        if depth > 6:
            return
        if isinstance(obj, list) and len(obj) > 0:
            sample = obj[0]
            if isinstance(sample, dict):
                sample_keys = set(sample.keys())
                # Listing indicators: id + price, or bulletinId, or known Madlan fields
                if (
                    ("id" in sample_keys or "bulletinId" in sample_keys)
                    and ("price" in sample_keys or "rooms" in sample_keys)
                ):
                    listings.extend(obj)
                    return
        if isinstance(obj, dict):
            for v in obj.values():
                _find_listings(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj[:3]:  # Only recurse into first 3 elements
                _find_listings(item, depth + 1)

    _find_listings(data)
    return listings


def _extract_from_nextdata(html: str) -> list[dict]:
    """Extract listing items from __NEXT_DATA__ embedded JSON (Strategy 2).

    Madlan is a Next.js SPA — if the page server-renders, listings are in
    props.pageProps. We look for arrays containing objects with listing fields.
    """
    nextdata_match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not nextdata_match:
        return []

    try:
        data = json.loads(nextdata_match.group(1))
        page_props = data.get("props", {}).get("pageProps", {})
        logger.debug(f"[madlan] __NEXT_DATA__ pageProps keys: {list(page_props.keys())}")
        return _extract_listings_from_api(page_props, "__NEXT_DATA__")
    except Exception as e:
        logger.warning(f"[madlan] Failed to parse __NEXT_DATA__: {e}")
        return []


def _extract_from_dom(html: str) -> list[dict]:
    """Extract listing items from DOM via BeautifulSoup (Strategy 3, fallback).

    CSS selector approach — targets common Madlan listing card patterns.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("[madlan] BeautifulSoup4 not installed — cannot parse HTML fallback")
        return []

    soup = BeautifulSoup(html, "html.parser")
    listings: list[dict] = []

    # Madlan listing cards — try common selector patterns
    cards = soup.select(
        "[data-testid='listing-card'], [class*='ListingCard'], [class*='listing-card'], "
        "[class*='bulletinCard'], [class*='bulletin-card']"
    )
    logger.debug(f"[madlan] DOM fallback: found {len(cards)} card elements")

    for card in cards:
        item: dict[str, Any] = {}

        # Extract listing ID from link href
        link = card.select_one("a[href*='/listings/']")
        if link and link.get("href"):
            match = re.search(r"/listings/([^/?]+)", link["href"])
            if match:
                item["id"] = match.group(1)

        # Extract title
        for sel in ["[data-testid='listing-title']", "h2", "h3", "[class*='title']"]:
            el = card.select_one(sel)
            if el and el.get_text(strip=True):
                item["description"] = el.get_text(strip=True)
                break

        # Extract price
        for sel in ["[data-testid='price']", "[class*='price']", "[class*='Price']"]:
            el = card.select_one(sel)
            if el and el.get_text(strip=True):
                item["price"] = el.get_text(strip=True)
                break

        # Extract address
        for sel in ["[data-testid='address']", "[class*='address']", "[class*='Address']"]:
            el = card.select_one(sel)
            if el and el.get_text(strip=True):
                item["street"] = el.get_text(strip=True)
                break

        if item.get("id"):
            listings.append(item)

    return listings


# ---------------------------------------------------------------------------
# Neighborhood filter
# ---------------------------------------------------------------------------


def is_in_target_neighborhood(item: dict) -> bool:
    """Check if a listing is in one of the target Haifa neighborhoods.

    Uses substring matching against settings.yad2_neighborhoods.
    Checks neighborhood, street, city, and description fields.
    Same neighborhoods list as Yad2 (כרמל, מרכז העיר, נווה שאנן).
    """
    # Madlan field names for address (nested structure)
    address = item.get("address") or {}
    if isinstance(address, dict):
        neighborhood = (address.get("neighborhood") or {}).get("text", "") or ""
        street = (address.get("street") or {}).get("text", "") or ""
        city = (address.get("city") or {}).get("text", "") or ""
    else:
        neighborhood = ""
        street = ""
        city = ""

    # Also check flat fields (if already flattened)
    neighborhood = neighborhood or item.get("neighborhood", "") or ""
    street = street or item.get("street", "") or ""
    city = city or item.get("city", "") or ""

    # Also check description/title for neighborhood mentions
    description = item.get("description", "") or item.get("title", "") or ""

    location_text = f"{neighborhood} {street} {city} {description}"
    return any(n in location_text for n in settings.yad2_neighborhoods)


# ---------------------------------------------------------------------------
# Field parsers
# ---------------------------------------------------------------------------


def _parse_int_price(raw: Any) -> int | None:
    """Parse price from Madlan raw value — handles '3,500 ₪', 3500, '3500/month', etc."""
    if raw is None:
        return None
    text = str(raw)
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _parse_float_rooms(item: dict) -> float | None:
    """Extract rooms count from Madlan item.

    Madlan uses 'rooms' key directly (float: 3.0, 3.5, etc.).
    """
    raw = item.get("rooms")
    if raw is not None:
        try:
            return float(raw)
        except (ValueError, TypeError):
            pass
    return None


def _parse_int_sqm(item: dict) -> int | None:
    """Extract size in m² from Madlan item.

    Madlan uses 'squareMeter' key (integer).
    """
    for key in ("squareMeter", "square_meter", "size", "area", "size_sqm"):
        raw = item.get(key)
        if raw is not None:
            try:
                return int(raw)
            except (ValueError, TypeError):
                pass
    return None


def _parse_post_date(raw: Any) -> datetime | None:
    """Parse ISO-8601 or common date strings to datetime. Returns None if unparseable."""
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[: len(fmt.replace("%", "XX"))], fmt)
        except ValueError:
            pass
    # Try dateutil if available
    try:
        from dateutil import parser as dateutil_parser
        return dateutil_parser.parse(text)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Field parser
# ---------------------------------------------------------------------------


def parse_listing(item: dict) -> dict | None:
    """Extract and normalise fields from a single Madlan listing item.

    Field mapping (from DevTools discovery + known Madlan data structure):
      id / bulletinId       → source_id (short alphanumeric slug, stable)
      price                 → price (integer NIS/month)
      rooms                 → rooms (float)
      squareMeter           → size_sqm (integer)
      address.city.text     → city component
      address.neighborhood.text → neighborhood component
      address.street.text   → street component
      address.houseNum      → house number
      coordinates.lat/lng   → lat/lng (geocoded later by run_geocoding_pass)
      contactName           → contact_info
      publishedAt / updatedAt → post_date
      description / title   → title
      id                    → URL: https://www.madlan.co.il/listings/{id}

    Returns a dict ready for insertion into the Listing table, or None
    if the item is malformed (missing source_id).
    """
    # source_id: stable per-listing ID (short alphanumeric slug)
    source_id = str(
        item.get("id") or item.get("bulletinId") or item.get("listingId") or ""
    ).strip()
    if not source_id:
        return None

    # Title: use description or title field
    title = (
        item.get("description") or item.get("title") or item.get("headline") or ""
    ).strip()

    # Price
    price = _parse_int_price(item.get("price"))

    # Rooms
    rooms = _parse_float_rooms(item)

    # Size
    size_sqm = _parse_int_sqm(item)

    # Address (handle nested address object from Madlan, with flat-field fallback)
    address_obj = item.get("address") or {}
    if isinstance(address_obj, dict):
        neighborhood = (address_obj.get("neighborhood") or {}).get("text", "") or ""
        street = (address_obj.get("street") or {}).get("text", "") or ""
        city = (address_obj.get("city") or {}).get("text", "") or ""
        house_num = str(address_obj.get("houseNum") or "").strip()
    else:
        neighborhood = ""
        street = ""
        city = ""
        house_num = ""

    # Flat-field fallback: if nested address yielded empty values, try direct item keys
    neighborhood = neighborhood or item.get("neighborhood", "") or ""
    street = street or item.get("street", "") or ""
    city = city or item.get("city", "") or ""

    street_full = f"{street} {house_num}".strip() if house_num else street
    address_parts = [p for p in [street_full, neighborhood, city] if p]
    address = ", ".join(address_parts) if address_parts else None

    # Contact info
    contact_info = (item.get("contactName") or item.get("contact_name") or "").strip() or None

    # Post date
    post_date = _parse_post_date(
        item.get("publishedAt") or item.get("updatedAt") or item.get("date")
    )

    # Coordinates (geocoded later if missing)
    coords = item.get("coordinates") or item.get("coords") or {}
    if isinstance(coords, dict):
        lat = coords.get("lat") or coords.get("latitude")
        lng = coords.get("lng") or coords.get("lon") or coords.get("longitude")
    else:
        lat = item.get("lat")
        lng = item.get("lng") or item.get("lon")
    try:
        lat = float(lat) if lat is not None else None
        lng = float(lng) if lng is not None else None
    except (ValueError, TypeError):
        lat = lng = None

    # Listing URL — confirmed from sitemap: /listings/{id}
    url = f"https://www.madlan.co.il/listings/{source_id}"

    return {
        "source": "madlan",
        "source_id": source_id,
        "title": title or None,
        "price": price,
        "rooms": rooms,
        "size_sqm": size_sqm,
        "address": address,
        "contact_info": contact_info,
        "post_date": post_date,
        "url": url,
        "source_badge": "מדלן",
        "raw_data": json.dumps(item, ensure_ascii=False),
        "lat": lat,
        "lng": lng,
    }


# ---------------------------------------------------------------------------
# DB insert
# ---------------------------------------------------------------------------


async def insert_listings(db: AsyncSession, listings: list[dict]) -> tuple[int, int]:
    """Insert listings with on_conflict_do_nothing deduplication.

    Returns (inserted_count, skipped_count).
    """
    inserted = 0
    skipped = 0
    for listing in listings:
        stmt = sqlite_insert(Listing).values(**listing)
        stmt = stmt.on_conflict_do_nothing(index_elements=["source", "source_id"])
        result = await db.execute(stmt)
        if result.rowcount == 1:
            inserted += 1
        else:
            skipped += 1
    await db.commit()
    return inserted, skipped


# ---------------------------------------------------------------------------
# Main scraper entry point
# ---------------------------------------------------------------------------


async def run_madlan_scraper(db: AsyncSession) -> ScraperResult:
    """Fetch Madlan listings, verify with LLM, merge fields, and upsert to DB.

    Pipeline:
      1. Fetch listings via Playwright+stealth (Playwright-first, per D-01).
         Three extraction strategies: XHR interception → __NEXT_DATA__ → DOM.
      2. Neighborhood filter — discard listings outside target areas.
      3. Parse and price-filter all feed items.
      4. LLM batch verification — reject non-rentals, flag low-confidence.
      5. Merge LLM-extracted fields with scraper fields (scraper wins on non-null).
      6. DB upsert — on_conflict_do_nothing for deduplication.

    Returns ScraperResult with counts and any error messages.
    """
    result = ScraperResult(source="madlan")

    try:
        # Build URL: Madlan Haifa rental page with price filter
        # Keep https:// — Bright Data Web Unlocker handles SSL via MITM interception.
        # ignore_https_errors=True is set on the browser context to accept the proxy cert.
        url = settings.madlan_base_url
        if is_proxy_enabled():
            logger.info("[madlan] Proxy active — using https:// with ignore_https_errors")

        # Step 1: Fetch listings via Playwright
        feed_items = await fetch_madlan_browser(url)
        logger.info(f"[madlan] Fetched {len(feed_items)} raw items from Playwright")

        # Neighborhood filter (MADL-01): discard listings outside target areas
        before_filter = len(feed_items)
        feed_items = [item for item in feed_items if is_in_target_neighborhood(item)]
        discarded = before_filter - len(feed_items)
        if discarded:
            logger.info(f"[madlan] Filtered {discarded} listings outside target neighborhoods")

        # Step 2: Parse fields + price filter
        parsed: list[dict] = []
        for item in feed_items:
            listing = parse_listing(item)
            if listing is None:
                continue
            # Price cap: discard listings above budget
            if listing["price"] is not None and listing["price"] > settings.yad2_price_max:
                continue
            parsed.append(listing)

        result.listings_found = len(parsed)

        if parsed:
            # Step 3: LLM batch verification (batch, not per-listing)
            raw_texts = [p.get("raw_data") or str(p) for p in parsed]
            logger.info(f"[llm] Verifying {len(raw_texts)} madlan listings with {settings.llm_model}")
            llm_results = await batch_verify_listings(raw_texts)

            # Step 4: Process LLM results — reject, flag, merge
            verified_listings: list[dict] = []
            for scraper_data, llm_data in zip(parsed, llm_results):
                if not llm_data.get("is_rental", False):
                    rejection_reason = llm_data.get("rejection_reason", "")
                    if rejection_reason and str(rejection_reason).startswith("LLM error:"):
                        # LLM call failed — flag for manual review, do not reject
                        result.listings_flagged += 1
                        logger.warning(
                            f"[llm] Madlan listing flagged (LLM unavailable): {rejection_reason}"
                        )
                        merged = dict(scraper_data)
                        merged["llm_confidence"] = 0.0
                        verified_listings.append(merged)
                        continue
                    # Real LLM decision: reject non-rental posts
                    result.listings_rejected += 1
                    logger.debug(f"[llm] Rejected: {rejection_reason or 'unknown'}")
                    continue

                # Merge LLM fields with scraper fields (scraper non-null wins)
                merged = merge_llm_fields(scraper_data, llm_data)

                confidence = llm_data.get("confidence", 0.0)
                merged["llm_confidence"] = confidence

                if confidence < settings.llm_confidence_threshold:
                    result.listings_flagged += 1
                    logger.debug(
                        f"[llm] Flagged (confidence {confidence:.2f} < {settings.llm_confidence_threshold})"
                    )

                verified_listings.append(merged)

            accepted = len(verified_listings)
            logger.info(
                f"[llm] madlan: {accepted} accepted, {result.listings_rejected} rejected, "
                f"{result.listings_flagged} flagged"
            )

            # Step 5: Insert verified listings to DB
            inserted, skipped = await insert_listings(db, verified_listings)
            result.listings_inserted = inserted
            result.listings_skipped = skipped
        else:
            logger.info("[madlan] No listings found to verify")

        logger.info(
            f"[madlan] Run complete: {result.listings_inserted} inserted, "
            f"{result.listings_skipped} skipped (duplicates), "
            f"{result.listings_rejected} rejected, {result.listings_flagged} flagged"
        )

    except Exception as e:
        result.success = False
        result.errors.append(str(e))
        logger.error(f"[madlan] ERROR: {e} — scraper exiting cleanly")

    return result


# ---------------------------------------------------------------------------
# Manual invocation
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio
    import sys
    from app.database import async_session_factory

    async def main():
        async with async_session_factory() as db:
            result = await run_madlan_scraper(db)
            print(
                f"[madlan] Run complete: {result.listings_inserted} inserted, "
                f"{result.listings_skipped} skipped, {result.listings_rejected} rejected"
            )
            sys.exit(0 if result.success else 1)

    asyncio.run(main())
