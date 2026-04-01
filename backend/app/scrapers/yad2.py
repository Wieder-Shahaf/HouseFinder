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
from app.models.listing import Listing
from app.scrapers.base import ScraperResult

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


async def _parse_html_listings(html: str) -> list[dict]:
    """Extract listing items from rendered Yad2 page HTML.

    Uses BeautifulSoup to find listing card elements. Selectors may need
    updating as Yad2 DOM evolves — verify against live DOM before use.
    # TODO: verify selectors against live DOM
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("[yad2] BeautifulSoup4 not installed — cannot parse HTML fallback")
        return []

    soup = BeautifulSoup(html, "html.parser")
    listings: list[dict] = []

    # Try common Yad2 feed item selectors
    # TODO: verify selectors against live DOM
    for card in soup.select("[data-testid='feed-item'], .feeditem, .feed-item, [class*='feedItem']"):
        item: dict[str, Any] = {}

        # ID from data attribute or link href
        link = card.select_one("a[href*='/item/']")
        if link and link.get("href"):
            match = re.search(r"/item/([^/?]+)", link["href"])
            if match:
                item["id"] = match.group(1)
                item["link_token"] = match.group(1)

        # Title
        for sel in ["[data-testid='title']", ".title", "h2", "h3"]:
            el = card.select_one(sel)
            if el and el.get_text(strip=True):
                item["title_1"] = el.get_text(strip=True)
                break

        # Price
        for sel in ["[data-testid='price']", ".price", "[class*='price']"]:
            el = card.select_one(sel)
            if el and el.get_text(strip=True):
                item["price"] = el.get_text(strip=True)
                break

        # Address / neighborhood
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
    from playwright.async_api import async_playwright
    from playwright_stealth import stealth_async  # 2.x API — must await

    logger.info("[yad2] httpx blocked — falling back to Playwright")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="he-IL",
            extra_http_headers={"Accept-Language": "he-IL,he;q=0.9"},
        )
        page = await context.new_page()
        await stealth_async(page)
        await page.goto(url, wait_until="networkidle", timeout=30000)
        content = await page.content()
        await browser.close()

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
        "raw_data": json.dumps(item, ensure_ascii=False),
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
    """Fetch Yad2 listings, filter, parse, and upsert to DB.

    - Tries httpx API path first.
    - Falls back to Playwright+stealth on 403/429/connection errors.
    - Applies neighborhood filter (is_in_target_neighborhood) on all paths.
    - Price filter: excludes listings above settings.yad2_price_max.
    - DB upsert: on_conflict_do_nothing for silent deduplication.
    - Catches all exceptions; returns ScraperResult.success=False on error.

    Returns ScraperResult with counts and any error messages.
    """
    result = ScraperResult(source="yad2")

    try:
        feed_items: list[dict] = []

        try:
            api_data = await fetch_yad2_api()
            feed_items = api_data.get("feed", {}).get("feed_items", [])
            logger.info(f"[yad2] Fetched {len(feed_items)} listings via httpx API")
        except (httpx.HTTPStatusError, httpx.RequestError, ValueError) as e:
            logger.warning(f"[yad2] httpx failed ({e}) — falling back to Playwright")
            url = (
                f"https://www.yad2.co.il/realestate/rent"
                f"?city={settings.yad2_city_code}&price=0-{settings.yad2_price_max}"
            )
            feed_items = await fetch_yad2_browser(url)

        # Neighborhood filter (YAD2-01): discard listings outside target areas
        before_filter = len(feed_items)
        feed_items = [item for item in feed_items if is_in_target_neighborhood(item)]
        discarded = before_filter - len(feed_items)
        if discarded:
            logger.info(f"[yad2] Filtered {discarded} listings outside target neighborhoods")

        # Parse fields + price filter
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
            inserted, skipped = await insert_listings(db, parsed)
            result.listings_inserted = inserted
            result.listings_skipped = skipped

        logger.info(
            f"[yad2] Run complete: {result.listings_inserted} inserted, "
            f"{result.listings_skipped} skipped (duplicates)"
        )

    except Exception as e:
        result.success = False
        result.errors.append(str(e))
        logger.error(f"[yad2] Scraper error: {e}", exc_info=True)

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
