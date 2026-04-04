"""Madlan scraper: direct GraphQL httpx approach with Playwright fallback.

Fetches Haifa rental listings from Madlan filtered to target neighborhoods
(כרמל, מרכז העיר, נווה שאנן) and price <= settings.yad2_price_max.

Usage:
    from app.scrapers.madlan import run_madlan_scraper
    result = await run_madlan_scraper(db)

=============================================================================
API Discovery Findings (2026-04-04) — Updated
=============================================================================

Method: Direct GraphQL introspection + live API probing via httpx
Target: https://www.madlan.co.il/api3 (GraphQL endpoint — confirmed live)

1. GRAPHQL ENDPOINT (confirmed):
   POST https://www.madlan.co.il/api3
   Query: searchBulletinWithUserPreferences
   No auth token required for public listing search.

2. GEOGRAPHIC FILTERING (discovery result):
   - userPreferences.location PredicateInput: ALL field names rejected by the API.
     Tried: docId, city, cityDocId, location, geo, locationDocId, and 50+ variants.
     Error: "Field X is not supported / not allowed in location section"
     Exception: 'id' is globally valid but also not allowed in location section.
   - tileRanges with Web Mercator tile coordinates (any zoom 7-19): returns 0 or all-Israel.
     Madlan's tileRanges system is NOT standard slippy map tiles.
   - WORKING APPROACH: Use deal_type predicate only, then POST-FILTER by cityDocId in Python.
     Haifa cityDocId: "חיפה-ישראל" (from autocomplete query)

3. VALID PREDICATE FIELDS (confirmed in "attributes" section):
   - deal_type: IN ["unitRent", "buildingRent"] — filters for rentals
   - price: RANGE (numeric array)
   - beds: RANGE (numeric array) — "rooms" in Israeli convention (float)
   - baths: RANGE (numeric array)
   - floor: RANGE (numeric array)
   - property_type: IN [...] (PropertyType enum)
   - building_type: IN [...] (string)
   - seller_type: IN [...] (SellerType enum)
   - general_condition: IN [...] (GeneralCondition enum)

4. FIELD MAPPING (confirmed from live API response):
   id               → source_id (short alphanumeric slug, e.g. "7cPBU3UBrDO")
   price            → price (integer NIS/month)
   beds             → rooms (float, Israeli "rooms" count, e.g. 3.5)
   area             → size_sqm (float/integer, square meters)
   address          → address string (e.g. "האסיף 19, חיפה")
   structuredAddress.streetName + streetNumber → street
   addressDetails.city        → city name
   addressDetails.cityDocId   → city filter key ("חיפה-ישראל" for Haifa)
   addressDetails.neighbourhood → neighborhood name
   addressDetails.neighbourhoodDocId → neighborhood filter key
   locationPoint.lat / .lng   → lat/lng (float)
   firstTimeSeen              → post_date (ISO8601)
   lastUpdated                → fallback for post_date
   description                → title/description
   dealType                   → deal type enum (unitRent, unitBuy, etc.)
   url                        → empty string in API response (construct from id)
   Listing URL pattern: https://www.madlan.co.il/listings/{id}

5. PAGINATION:
   limit/offset pagination. limit=50 recommended.
   Sort by DATE DESC to get newest listings first.
   Stop pagination when firstTimeSeen < scrape_interval_hours ago.
   Approximately 4-8 Haifa rentals per page of 50 all-Israel rentals.

6. BOT PROTECTION:
   Madlan uses PerimeterX + Cloudflare WAF on page rendering (403 from datacenter).
   The /api3 GraphQL endpoint does NOT require browser rendering or cookies —
   direct httpx POST works from datacenter IPs (confirmed in testing).
   Bright Data proxy is still useful if /api3 starts blocking datacenter IPs.
=============================================================================
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.config import settings
from app.llm.verifier import batch_verify_listings, merge_llm_fields
from app.models.listing import Listing
from app.scrapers.base import ScraperResult
from app.scrapers.proxy import get_proxy_launch_args, is_proxy_enabled

logger = logging.getLogger(__name__)

# Madlan GraphQL endpoint (confirmed via introspection, 2026-04-04)
MADLAN_GRAPHQL_URL = "https://www.madlan.co.il/api3"

# Haifa city docId (from autocomplete query)
HAIFA_CITY_DOC_ID = "חיפה-ישראל"

# GraphQL query for rental bulletins
SEARCH_BULLETINS_QUERY = """
query SearchBulletins($limit: Int!, $offset: Int!) {
  searchBulletinWithUserPreferences(searchQuery: {
    limit: $limit
    offset: $offset
    sortType: DATE
    sortOrder: DESC
    userPreferences: {
      attributes: {
        operator: IN
        field: "deal_type"
        intent: MUST
        value: ["unitRent", "buildingRent"]
      }
    }
  }) {
    total
    bulletins {
      id
      price
      beds
      area
      floor
      dealType
      address
      description
      firstTimeSeen
      lastUpdated
      addressDetails {
        city
        cityDocId
        neighbourhood
        neighbourhoodDocId
      }
      structuredAddress {
        city
        streetName
        streetNumber
      }
      locationPoint {
        lat
        lng
      }
    }
  }
}
"""


# ---------------------------------------------------------------------------
# Direct GraphQL fetch (primary strategy)
# ---------------------------------------------------------------------------


async def fetch_madlan_graphql(
    max_pages: int = 10,
    page_size: int = 50,
    cutoff_hours: int | None = None,
) -> list[dict]:
    """Fetch Madlan rental listings directly via the /api3 GraphQL endpoint.

    Strategy:
      1. POST searchBulletinWithUserPreferences with deal_type=unitRent filter.
      2. Paginate sorted by DATE DESC until firstTimeSeen < cutoff_hours ago.
      3. Filter results to Haifa (addressDetails.cityDocId == HAIFA_CITY_DOC_ID).

    No browser or cookies required — /api3 accepts direct httpx requests.
    Falls back gracefully if the endpoint returns non-200 or errors.

    Args:
        max_pages: Maximum pages to fetch (safety cap).
        page_size: Results per page (50 is optimal).
        cutoff_hours: Stop pagination when listings are older than this many hours.
                      Defaults to settings.scrape_interval_hours * 2 for safety margin.

    Returns:
        List of raw bulletin dicts for Haifa rentals only.
    """
    if cutoff_hours is None:
        cutoff_hours = settings.scrape_interval_hours * 2

    cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=cutoff_hours)
    logger.info(
        f"[madlan] GraphQL fetch: cutoff={cutoff_dt.isoformat()}, "
        f"max_pages={max_pages}, page_size={page_size}"
    )

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ),
        "Origin": "https://www.madlan.co.il",
        "Referer": "https://www.madlan.co.il/rent/haifa",
        "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
    }

    haifa_listings: list[dict] = []

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for page in range(max_pages):
            offset = page * page_size
            payload = {
                "query": SEARCH_BULLETINS_QUERY,
                "variables": {"limit": page_size, "offset": offset},
            }

            try:
                resp = await client.post(MADLAN_GRAPHQL_URL, json=payload, headers=headers)
            except Exception as exc:
                logger.warning(f"[madlan] GraphQL request failed (page {page + 1}): {exc}")
                break

            if resp.status_code != 200:
                logger.warning(
                    f"[madlan] GraphQL returned HTTP {resp.status_code} (page {page + 1})"
                )
                break

            try:
                data = resp.json()
            except Exception as exc:
                logger.warning(f"[madlan] GraphQL JSON parse failed (page {page + 1}): {exc}")
                break

            if "errors" in data:
                logger.warning(
                    f"[madlan] GraphQL errors (page {page + 1}): "
                    f"{data['errors'][0].get('message', '')[:120]}"
                )
                break

            result = (data.get("data") or {}).get("searchBulletinWithUserPreferences") or {}
            bulletins = result.get("bulletins") or []
            total = result.get("total", 0)

            if not bulletins:
                logger.info(f"[madlan] GraphQL: no bulletins on page {page + 1}, stopping")
                break

            logger.info(
                f"[madlan] GraphQL page {page + 1}: {len(bulletins)} bulletins "
                f"(total across Israel: {total})"
            )

            # Filter to Haifa and apply cutoff
            # NOTE: cutoff is checked on ALL bulletins (not just Haifa) to drive
            # pagination termination — bulletins are sorted DATE DESC so once we
            # see one older than cutoff_dt the rest will be older too.
            reached_cutoff = False
            page_oldest: datetime | None = None
            for bulletin in bulletins:
                # Track oldest timestamp on this page for cutoff decision
                first_seen_raw = bulletin.get("firstTimeSeen") or bulletin.get("lastUpdated")
                if first_seen_raw:
                    try:
                        first_seen = datetime.fromisoformat(
                            first_seen_raw.replace("Z", "+00:00")
                        )
                        if page_oldest is None or first_seen < page_oldest:
                            page_oldest = first_seen
                    except Exception:
                        pass

                # City filter: Haifa only
                addr_details = bulletin.get("addressDetails") or {}
                if addr_details.get("cityDocId") != HAIFA_CITY_DOC_ID:
                    continue

                haifa_listings.append(bulletin)

            # Stop paginating if the oldest listing on this page is beyond cutoff
            if page_oldest is not None and page_oldest < cutoff_dt:
                reached_cutoff = True

            if reached_cutoff:
                logger.info(
                    f"[madlan] GraphQL: reached cutoff ({cutoff_hours}h) at page {page + 1}"
                )
                break

            # If we got fewer results than page_size, we've reached the end
            if len(bulletins) < page_size:
                logger.info(f"[madlan] GraphQL: final page reached at page {page + 1}")
                break

    logger.info(
        f"[madlan] GraphQL fetch complete: {len(haifa_listings)} Haifa rental listings"
    )
    return haifa_listings


# ---------------------------------------------------------------------------
# Playwright browser fetch (fallback)
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

    Supports both the GraphQL API format (addressDetails.neighbourhood) and
    the legacy browser-scraped format (nested address.neighborhood.text).

    Uses substring matching against settings.yad2_neighborhoods.
    Same neighborhoods list as Yad2 (כרמל, מרכז העיר, נווה שאנן).
    """
    # GraphQL API format (primary — confirmed from live /api3 responses)
    addr_details = item.get("addressDetails") or {}
    if isinstance(addr_details, dict):
        neighbourhood = addr_details.get("neighbourhood", "") or ""
        neighbourhood_doc_id = addr_details.get("neighbourhoodDocId", "") or ""
    else:
        neighbourhood = ""
        neighbourhood_doc_id = ""

    # Legacy browser-scraped format (nested address object)
    address = item.get("address") or {}
    if isinstance(address, dict):
        legacy_neighborhood = (address.get("neighborhood") or {}).get("text", "") or ""
        legacy_street = (address.get("street") or {}).get("text", "") or ""
    else:
        legacy_neighborhood = ""
        legacy_street = ""

    # Flat fields (fallback)
    flat_neighborhood = item.get("neighborhood", "") or ""
    flat_street = item.get("street", "") or ""

    # Also check description/title for neighborhood mentions
    description = item.get("description", "") or item.get("title", "") or ""

    location_text = (
        f"{neighbourhood} {neighbourhood_doc_id} {legacy_neighborhood} "
        f"{legacy_street} {flat_neighborhood} {flat_street} {description}"
    )
    return any(n in location_text for n in settings.yad2_neighborhoods)


# ---------------------------------------------------------------------------
# Field parsers
# ---------------------------------------------------------------------------


def _parse_int_price(raw: Any) -> int | None:
    """Parse price from Madlan raw value — handles integers, '3,500 ₪', etc."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
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

    GraphQL API uses 'beds' (float, Israeli "rooms" convention, e.g. 3.5).
    Legacy browser format uses 'rooms' key.
    """
    # GraphQL API field (confirmed from /api3 live responses)
    raw = item.get("beds")
    if raw is not None:
        try:
            return float(raw)
        except (ValueError, TypeError):
            pass
    # Legacy browser-scraped field
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

    Supports two formats:
    1. GraphQL /api3 format (primary — confirmed from live API, 2026-04-04):
       id                          → source_id
       price                       → price (integer NIS/month)
       beds                        → rooms (float, Israeli "rooms" count)
       area                        → size_sqm (float)
       address                     → address string (e.g. "האסיף 19, חיפה")
       structuredAddress.streetName + streetNumber → street components
       addressDetails.city         → city name
       addressDetails.neighbourhood → neighborhood name
       locationPoint.lat / .lng    → lat/lng coordinates
       firstTimeSeen / lastUpdated → post_date (ISO8601)
       description                 → title

    2. Legacy browser-scraped format (fallback):
       id / bulletinId / listingId → source_id
       rooms / squareMeter etc.    → as before

    Listing URL: https://www.madlan.co.il/listings/{id} (confirmed from sitemap)

    Returns a dict ready for insertion into the Listing table, or None
    if the item is malformed (missing source_id).
    """
    # source_id: stable per-listing ID (short alphanumeric slug from GraphQL or legacy)
    source_id = str(
        item.get("id") or item.get("bulletinId") or item.get("listingId") or ""
    ).strip()
    if not source_id:
        return None

    # Title: description field (GraphQL) or title/headline (legacy)
    title = (
        item.get("description") or item.get("title") or item.get("headline") or ""
    ).strip()

    # Price
    price = _parse_int_price(item.get("price"))

    # Rooms: 'beds' in GraphQL API, 'rooms' in legacy format
    rooms = _parse_float_rooms(item)

    # Size: 'area' in GraphQL API, 'squareMeter' in legacy format
    size_sqm = _parse_int_sqm(item)

    # Address: GraphQL provides structured address in multiple fields
    # Primary: addressDetails (GraphQL)
    addr_details = item.get("addressDetails") or {}
    structured = item.get("structuredAddress") or {}

    if isinstance(addr_details, dict) and addr_details.get("city"):
        # GraphQL /api3 format
        city = addr_details.get("city", "") or ""
        neighborhood = addr_details.get("neighbourhood", "") or ""
        street_name = structured.get("streetName", "") or "" if isinstance(structured, dict) else ""
        street_num = structured.get("streetNumber", "") or "" if isinstance(structured, dict) else ""
        street = f"{street_name} {street_num}".strip() if street_num else street_name
        # Use the flat address string if available (most complete)
        flat_address = item.get("address", "") or ""
        address = flat_address or ", ".join(p for p in [street, neighborhood, city] if p) or None
    else:
        # Legacy browser-scraped format (nested address object)
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
            # address_obj is a string in browser DOM fallback
            flat_address = str(address_obj) if address_obj else ""

        # Flat-field fallback
        neighborhood = neighborhood or item.get("neighborhood", "") or ""
        street = street or item.get("street", "") or ""
        city = city or item.get("city", "") or ""
        if "house_num" in dir():
            street_full = f"{street} {house_num}".strip() if house_num else street
        else:
            street_full = street
        address_parts = [p for p in [street_full, neighborhood, city] if p]
        address = ", ".join(address_parts) if address_parts else None

    # Contact info: not available in GraphQL /api3 public API (protected field)
    contact_info = (item.get("contactName") or item.get("contact_name") or "").strip() or None

    # Post date: 'firstTimeSeen' (GraphQL) or 'publishedAt'/'updatedAt' (legacy)
    post_date = _parse_post_date(
        item.get("firstTimeSeen")
        or item.get("publishedAt")
        or item.get("lastUpdated")
        or item.get("updatedAt")
        or item.get("date")
    )

    # Coordinates: 'locationPoint.lat/lng' (GraphQL) or 'coordinates.lat/lng' (legacy)
    location_point = item.get("locationPoint") or {}
    if isinstance(location_point, dict) and location_point.get("lat") is not None:
        # GraphQL /api3 format
        lat = location_point.get("lat")
        lng = location_point.get("lng")
    else:
        # Legacy browser format
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
      1. Fetch listings via direct GraphQL httpx (Strategy A — primary).
         Query: searchBulletinWithUserPreferences with deal_type=unitRent.
         Filter by cityDocId='חיפה-ישראל' in Python (location predicate field names
         are not publicly documented — see debug session madlan-api-predicate-fields).
      2. Fallback to Playwright browser if GraphQL returns 0 results.
      3. Neighborhood filter — discard listings outside target areas.
      4. Parse and price-filter all feed items.
      5. LLM batch verification — reject non-rentals, flag low-confidence.
      6. Merge LLM-extracted fields with scraper fields (scraper wins on non-null).
      7. DB upsert — on_conflict_do_nothing for deduplication.

    Returns ScraperResult with counts and any error messages.
    """
    result = ScraperResult(source="madlan")

    try:
        # Step 1A: Fetch listings via direct GraphQL (primary strategy)
        # Confirmed working: POST /api3 with deal_type predicate, filter Haifa in Python.
        logger.info("[madlan] Attempting direct GraphQL fetch from /api3")
        feed_items = await fetch_madlan_graphql(
            max_pages=settings.madlan_graphql_max_pages,
            page_size=50,
            cutoff_hours=settings.scrape_interval_hours * 2,
        )
        logger.info(f"[madlan] GraphQL: {len(feed_items)} Haifa rental items fetched")

        # Step 1B: Playwright fallback if GraphQL returned nothing
        if not feed_items:
            logger.warning(
                "[madlan] GraphQL returned 0 items — falling back to Playwright browser"
            )
            url = settings.madlan_base_url
            if is_proxy_enabled():
                logger.info("[madlan] Proxy active — using https:// with ignore_https_errors")
            feed_items = await fetch_madlan_browser(url)
            logger.info(f"[madlan] Playwright fallback: {len(feed_items)} raw items fetched")

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
