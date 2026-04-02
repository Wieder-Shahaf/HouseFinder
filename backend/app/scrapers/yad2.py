"""Yad2 scraper: httpx-first API path with Playwright+stealth fallback.

Fetches Haifa rental listings from Yad2 filtered to target neighborhoods
(כרמל, מרכז העיר, נווה שאנן) and price <= settings.yad2_price_max.

Usage:
    from app.scrapers.yad2 import run_yad2_scraper
    result = await run_yad2_scraper(db)
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
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

YAD2_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "he-IL,he;q=0.9",
    "Referer": "https://www.yad2.co.il/realestate/rent",
}


# ---------------------------------------------------------------------------
# API fetch (httpx path)
# ---------------------------------------------------------------------------


async def fetch_yad2_api() -> dict:
    """Fetch Yad2 rental listings via the internal XHR API.

    Returns the raw JSON response dict.
    Raises httpx.HTTPStatusError on non-2xx.
    Raises ValueError if the response body is not valid JSON.
    """
    params = {
        "city": settings.yad2_city_code,
        "price": f"0-{settings.yad2_price_max}",
        "propertyGroup": "apartments",
        # Pass the confirmed Carmel neighborhood ID for API-level filtering.
        # מרכז העיר and נווה שאנן codes are unknown — handled by post-scrape filter.
        "neighborhood": str(settings.yad2_neighborhood_id_carmel),
    }

    async with httpx.AsyncClient(headers=YAD2_HEADERS, follow_redirects=True, timeout=30) as client:
        # Step 1: Obtain guest_token cookie via a preflight request to the main page.
        # Yad2 API requires this JWT cookie to be present in subsequent requests.
        try:
            await client.get("https://www.yad2.co.il/realestate/rent", timeout=15)
        except Exception:
            # Best-effort cookie acquisition — continue without it
            pass

        response = await client.get(settings.yad2_api_base_url, params=params)
        response.raise_for_status()

        try:
            return response.json()
        except Exception as exc:
            raise ValueError(f"Yad2 API returned non-JSON response: {response.text[:200]}") from exc


# ---------------------------------------------------------------------------
# Playwright fallback
# ---------------------------------------------------------------------------


def _flatten_nextdata_item(item: dict) -> dict:
    """Flatten a Yad2 __NEXT_DATA__ feed item into the shape that parse_listing expects.

    The real Yad2 page embeds all listing data in a Next.js __NEXT_DATA__ JSON blob.
    Each item in props.pageProps.feed.{private,agency,...} has nested objects.
    This function flattens them into the flat dict that parse_listing already reads.

    Confirmed field mapping (from live DOM inspection 2026-04-02):
      token                              → token / id
      price                              → price (integer)
      additionalDetails.roomsCount       → rooms
      additionalDetails.squareMeter      → size_sqm
      address.city.text                  → city
      address.neighborhood.text          → neighborhood
      address.street.text                → street
      address.coords.lat/lon             → lat / lon
      metaData.description               → title_1
    """
    addr = item.get("address") or {}
    details = item.get("additionalDetails") or {}
    meta = item.get("metaData") or {}
    coords = addr.get("coords") or {}

    token = item.get("token") or str(item.get("orderId") or "")

    return {
        "id": token,
        "token": token,
        "link_token": token,
        "price": item.get("price"),
        "rooms": details.get("roomsCount"),
        "size_sqm": details.get("squareMeter"),
        "city": (addr.get("city") or {}).get("text") or "",
        "neighborhood": (addr.get("neighborhood") or {}).get("text") or "",
        "street": (addr.get("street") or {}).get("text") or "",
        "lat": coords.get("lat"),
        "lon": coords.get("lon"),
        "title_1": meta.get("description") or "",
        "date": None,  # not present in feed item; available via item detail endpoint
        "contact_name": None,
        # Preserve original for raw_data serialisation
        "_raw_nextdata": item,
    }


async def _parse_html_listings(html: str) -> list[dict]:
    """Extract listing items from rendered Yad2 page HTML.

    Primary path: extract from Next.js __NEXT_DATA__ JSON blob embedded in the page.
    The feed items are at props.pageProps.feed.{private,agency,platinum,...}.

    Falls back to CSS-selector HTML parsing if __NEXT_DATA__ is absent.
    """
    # --- Primary: __NEXT_DATA__ JSON extraction ---
    nextdata_match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if nextdata_match:
        try:
            data = json.loads(nextdata_match.group(1))
            feed = data["props"]["pageProps"]["feed"]
            # Collect items from all feed categories that contain listing lists
            # Skipping 'yad1' (different shape), 'pagination', 'lookalike'
            listing_categories = ["private", "agency", "platinum", "kingOfTheHar", "trio", "booster", "leadingBroker"]
            raw_items: list[dict] = []
            for cat in listing_categories:
                items = feed.get(cat)
                if isinstance(items, list):
                    raw_items.extend(items)
            logger.info(f"[yad2] Extracted {len(raw_items)} items from __NEXT_DATA__ feed")
            return [_flatten_nextdata_item(item) for item in raw_items if item.get("token")]
        except Exception as e:
            logger.warning(f"[yad2] Failed to parse __NEXT_DATA__: {e} — falling back to CSS selectors")

    # --- Fallback: CSS selector HTML parsing (kept for resilience) ---
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("[yad2] BeautifulSoup4 not installed — cannot parse HTML fallback")
        return []

    soup = BeautifulSoup(html, "html.parser")
    listings: list[dict] = []

    cards = soup.select("[data-testid='feed-item'], .feeditem, .feed-item, [class*='feedItem']")
    logger.debug(f"[yad2] _parse_html_listings CSS fallback: found {len(cards)} card elements")
    for card in cards:
        item: dict[str, Any] = {}

        link = card.select_one("a[href*='/item/']")
        if link and link.get("href"):
            match = re.search(r"/item/([^/?]+)", link["href"])
            if match:
                item["id"] = match.group(1)
                item["link_token"] = match.group(1)

        for sel in ["[data-testid='title']", ".title", "h2", "h3"]:
            el = card.select_one(sel)
            if el and el.get_text(strip=True):
                item["title_1"] = el.get_text(strip=True)
                break

        for sel in ["[data-testid='price']", ".price", "[class*='price']"]:
            el = card.select_one(sel)
            if el and el.get_text(strip=True):
                item["price"] = el.get_text(strip=True)
                break

        for sel in ["[data-testid='address']", ".address", "[class*='address']"]:
            el = card.select_one(sel)
            if el and el.get_text(strip=True):
                item["street"] = el.get_text(strip=True)
                break

        if item.get("id"):
            listings.append(item)

    return listings


async def fetch_yad2_browser(url: str) -> list[dict]:
    """Fallback: use Playwright+stealth to render the Yad2 page and extract listings."""
    import os
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth  # 2.x API: Stealth().apply_stealth_async(page)

    # Persist browser profile so guest_token cookies survive between runs.
    # This dramatically reduces the chance of bot-detection on repeat invocations.
    user_data_dir = os.path.expanduser("~/.yad2-browser-profile")
    os.makedirs(user_data_dir, exist_ok=True)
    # Remove stale lock file left by previous crash/container restart
    singleton_lock = os.path.join(user_data_dir, "SingletonLock")
    if os.path.exists(singleton_lock):
        os.remove(singleton_lock)

    if is_proxy_enabled():
        logger.info("[yad2] Bright Data Web Unlocker proxy enabled for Playwright")
    logger.info("[yad2] httpx blocked — falling back to Playwright (headless=False, persistent profile)")
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=True,
            locale="he-IL",
            viewport={"width": 1280, "height": 800},
            extra_http_headers={"Accept-Language": "he-IL,he;q=0.9"},
            **get_proxy_launch_args(),
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        await page.goto(url, wait_until="load", timeout=60000)
        # Wait for JS-rendered content after initial load event
        await page.wait_for_timeout(5000)
        content = await page.content()
        await context.close()

    # Diagnostic: save HTML to temp file so we can inspect the real DOM structure
    debug_path = "/tmp/yad2_debug.html"
    try:
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"[yad2] DEBUG: saved page HTML ({len(content)} bytes) to {debug_path}")
    except Exception as e:
        logger.warning(f"[yad2] DEBUG: could not write debug HTML: {e}")

    # Detect captcha/bot-block page. With headless=False the user can solve the captcha
    # manually in the visible browser window — wait up to 90s for the real page to load.
    if "ShieldSquare" in content or "hcaptcha" in content or "Are you for real" in content:
        logger.warning(
            "[yad2] Bot-detection CAPTCHA detected. "
            "A browser window is open — solve the captcha manually, then the scraper will continue. "
            "Waiting up to 90 seconds..."
        )
        # Re-open browser to wait for captcha resolution
        async with async_playwright() as p2:
            context2 = await p2.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=True,
                locale="he-IL",
                viewport={"width": 1280, "height": 800},
                extra_http_headers={"Accept-Language": "he-IL,he;q=0.9"},
                **get_proxy_launch_args(),
            )
            page2 = await context2.new_page()
            await page2.goto(url, wait_until="load", timeout=60000)
            # Wait for the real page to appear (no captcha keywords in URL or page title)
            try:
                await page2.wait_for_function(
                    "() => !document.title.includes('אבטחת אתר') && !document.title.includes('Captcha') && document.title.length > 0",
                    timeout=90000,
                )
                await page2.wait_for_timeout(3000)
                content = await page2.content()
            except Exception:
                logger.warning("[yad2] Captcha not solved within 90s — giving up for this run")
                await context2.close()
                return []
            await context2.close()

        # Save updated HTML for diagnostics
        try:
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass

        # If still captcha after waiting, give up
        if "ShieldSquare" in content or "hcaptcha" in content:
            logger.warning("[yad2] Still on captcha page after wait — no listing data available")
            return []

    return await _parse_html_listings(content)


# ---------------------------------------------------------------------------
# Neighborhood filter
# ---------------------------------------------------------------------------


def is_in_target_neighborhood(item: dict) -> bool:
    """Check if a listing is in one of the target Haifa neighborhoods.

    Combines neighborhood, street, and city fields for substring matching
    against settings.yad2_neighborhoods. Applied as a post-scrape safety net
    on all listings regardless of API-level filtering.
    """
    neighborhood = item.get("neighborhood", "") or ""
    address = item.get("street", "") or ""
    city = item.get("city", "") or ""
    location_text = f"{neighborhood} {address} {city}"
    return any(n in location_text for n in settings.yad2_neighborhoods)


# ---------------------------------------------------------------------------
# Field parser
# ---------------------------------------------------------------------------


def _parse_int_price(raw: Any) -> int | None:
    """Parse price from Yad2 raw value — handles '3,500 ₪', 3500, etc."""
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
    """Extract rooms count from row_4 list or numeric value."""
    raw = item.get("rooms")
    if raw is not None:
        try:
            return float(raw)
        except (ValueError, TypeError):
            pass

    row_4 = item.get("row_4")
    if isinstance(row_4, list) and row_4:
        try:
            return float(row_4[0].get("value", 0))
        except (ValueError, TypeError, AttributeError):
            pass
    return None


def _parse_int_sqm(item: dict) -> int | None:
    """Extract size in m² from row_3 list or numeric value."""
    raw = item.get("size_sqm")
    if raw is not None:
        try:
            return int(raw)
        except (ValueError, TypeError):
            pass

    row_3 = item.get("row_3")
    if isinstance(row_3, list) and row_3:
        text = str(row_3[0].get("value", ""))
        digits = re.sub(r"[^\d]", "", text)
        if digits:
            try:
                return int(digits)
            except ValueError:
                pass
    return None


def _parse_post_date(raw: Any) -> datetime | None:
    """Parse ISO-8601 or common date strings to datetime. Returns None if unparseable."""
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:len(fmt.replace("%", "XX"))], fmt)
        except ValueError:
            pass
    # Try dateutil if available
    try:
        from dateutil import parser as dateutil_parser
        return dateutil_parser.parse(text)
    except Exception:
        pass
    return None


def parse_listing(item: dict) -> dict | None:
    """Extract and normalise fields from a single Yad2 feed item.

    Returns a dict ready for insertion into the Listing table, or None
    if the item is malformed (missing source_id).
    """
    source_id = str(item.get("id") or item.get("token") or "").strip()
    if not source_id:
        return None

    title = (item.get("title_1") or item.get("title_2") or "").strip()
    price = _parse_int_price(item.get("price"))
    rooms = _parse_float_rooms(item)
    size_sqm = _parse_int_sqm(item)

    neighborhood = (item.get("neighborhood") or "").strip()
    street = (item.get("street") or "").strip()
    city = (item.get("city") or "").strip()
    address_parts = [p for p in [street, neighborhood, city] if p]
    address = ", ".join(address_parts) if address_parts else None

    contact_info = (item.get("contact_name") or "").strip() or None
    post_date = _parse_post_date(item.get("date"))
    link_token = item.get("link_token") or item.get("id") or source_id
    url = f"https://www.yad2.co.il/item/{link_token}"

    # Coordinates — present when extracted from __NEXT_DATA__ (lon mapped to lng for DB column)
    lat = item.get("lat")
    lng = item.get("lon") or item.get("lng")
    try:
        lat = float(lat) if lat is not None else None
        lng = float(lng) if lng is not None else None
    except (ValueError, TypeError):
        lat = lng = None

    # For raw_data serialisation, strip internal-only key added by _flatten_nextdata_item
    raw_item = {k: v for k, v in item.items() if k != "_raw_nextdata"}

    return {
        "source": "yad2",
        "source_id": source_id,
        "title": title or None,
        "price": price,
        "rooms": rooms,
        "size_sqm": size_sqm,
        "address": address,
        "contact_info": contact_info,
        "post_date": post_date,
        "url": url,
        "source_badge": "יד2",
        "raw_data": json.dumps(raw_item, ensure_ascii=False),
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


async def run_yad2_scraper(db: AsyncSession) -> ScraperResult:
    """Fetch Yad2 listings, verify with LLM, merge fields, and upsert to DB.

    Pipeline:
      1. Fetch listings via httpx API (falls back to Playwright on errors).
      2. Neighborhood filter — discard listings outside target areas.
      3. Parse and price-filter all feed items.
      4. LLM batch verification — reject non-rentals, flag low-confidence.
      5. Merge LLM-extracted fields with scraper fields (scraper wins on non-null).
      6. DB upsert — on_conflict_do_nothing for deduplication.

    Returns ScraperResult with counts and any error messages.
    """
    result = ScraperResult(source="yad2")

    try:
        feed_items: list[dict] = []

        # Step 1: Fetch listings (httpx or Playwright fallback)
        try:
            api_data = await fetch_yad2_api()
            feed_items = api_data.get("feed", {}).get("feed_items", [])
            logger.info(f"[yad2] Fetched {len(feed_items)} listings via httpx API")
        except (httpx.HTTPStatusError, httpx.RequestError, ValueError) as e:
            logger.warning(f"[yad2] httpx failed ({e}) — falling back to Playwright")
            # Use the frontend URL format matching the user's actual browser URL.
            # area=5 = Haifa coastal-north region; params match the yad2 frontend.
            # The internal gw.yad2.co.il API path is not yet confirmed via DevTools;
            # until it is, the Playwright path is the primary data source.
            url = (
                "https://www.yad2.co.il/realestate/rent/coastal-north"
                f"?maxPrice={settings.yad2_price_max}"
                "&minRooms=2.5&maxRooms=3"
                "&imageOnly=1&priceOnly=1"
                "&property=1%2C3%2C5%2C6%2C39%2C32%2C55"
                "&area=5"
            )
            if is_proxy_enabled():
                url = url.replace("https://", "http://", 1)
                logger.info("[yad2] Proxy active — using http:// scheme for Web Unlocker")
            feed_items = await fetch_yad2_browser(url)

        # Neighborhood filter (YAD2-01): discard listings outside target areas
        before_filter = len(feed_items)
        feed_items = [item for item in feed_items if is_in_target_neighborhood(item)]
        discarded = before_filter - len(feed_items)
        if discarded:
            logger.info(f"[yad2] Filtered {discarded} listings outside target neighborhoods")

        # Step 2: Parse fields + price filter
        parsed: list[dict] = []
        for item in feed_items:
            listing = parse_listing(item)
            if listing is None:
                continue
            # Price cap (belt-and-suspenders after API param)
            if listing["price"] is not None and listing["price"] > settings.yad2_price_max:
                continue
            parsed.append(listing)

        result.listings_found = len(parsed)

        if parsed:
            # Step 3: LLM batch verification (D-03: after full scrape batch, not per-listing)
            # raw_data is always set by parse_listing (JSON of original feed item)
            raw_texts = [p.get("raw_data") or str(p) for p in parsed]
            logger.info(f"[llm] Verifying {len(raw_texts)} listings with {settings.llm_model}")
            llm_results = await batch_verify_listings(raw_texts)

            # Step 4: Process LLM results — reject, flag, merge
            verified_listings: list[dict] = []
            for scraper_data, llm_data in zip(parsed, llm_results):
                if not llm_data.get("is_rental", False):
                    rejection_reason = llm_data.get("rejection_reason", "")
                    if rejection_reason and str(rejection_reason).startswith("LLM error:"):
                        # LLM call failed (auth error, network error, rate limit, etc.)
                        # Do NOT reject the listing — flag it for manual review instead.
                        result.listings_flagged += 1
                        logger.warning(
                            f"[llm] Listing flagged (LLM unavailable): {rejection_reason}"
                        )
                        # Insert with zero confidence so the UI can surface it for review
                        merged = dict(scraper_data)
                        merged["llm_confidence"] = 0.0
                        verified_listings.append(merged)
                        continue
                    # LLM-01: Reject non-rental posts (LLM made a real decision)
                    result.listings_rejected += 1
                    logger.debug(f"[llm] Rejected: {rejection_reason or 'unknown'}")
                    continue

                # LLM-04: Merge LLM fields with scraper fields (scraper non-null wins)
                merged = merge_llm_fields(scraper_data, llm_data)

                confidence = llm_data.get("confidence", 0.0)
                merged["llm_confidence"] = confidence

                if confidence < settings.llm_confidence_threshold:
                    # LLM-03: Flag low confidence — still insert (D-02: not deleted)
                    result.listings_flagged += 1
                    logger.debug(
                        f"[llm] Flagged (confidence {confidence:.2f} < {settings.llm_confidence_threshold})"
                    )

                verified_listings.append(merged)

            accepted = len(verified_listings)
            logger.info(
                f"[llm] {accepted} accepted, {result.listings_rejected} rejected, "
                f"{result.listings_flagged} flagged (confidence < {settings.llm_confidence_threshold})"
            )

            # Step 5: Insert verified listings to DB
            inserted, skipped = await insert_listings(db, verified_listings)
            result.listings_inserted = inserted
            result.listings_skipped = skipped
        else:
            logger.info("[yad2] No listings found to verify")

        logger.info(
            f"[yad2] Run complete: {result.listings_inserted} inserted, "
            f"{result.listings_skipped} skipped (duplicates), "
            f"{result.listings_rejected} rejected, {result.listings_flagged} flagged"
        )

    except Exception as e:
        result.success = False
        result.errors.append(str(e))
        logger.error(f"[yad2] ERROR: {e} — scraper exiting cleanly")

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
            result = await run_yad2_scraper(db)
            print(
                f"[yad2] Run complete: {result.listings_inserted} inserted, "
                f"{result.listings_skipped} skipped, {result.listings_rejected} rejected"
            )
            sys.exit(0 if result.success else 1)

    asyncio.run(main())
