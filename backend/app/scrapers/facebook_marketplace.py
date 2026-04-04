"""Facebook Marketplace scraper for apartment rental listings in Haifa.

Scrapes the Facebook Marketplace Haifa property rentals page for listings.
Reuses the shared Playwright session infrastructure from facebook_groups.py —
same saved session, same health check, same stealth configuration.

Marketplace listings are semi-structured (title, price, location visible in
cards) unlike free-form group posts. Cards are anchored by
``a[href*="/marketplace/item/"]`` links with structured text blocks.

Extracted listings are verified via the LLM pipeline and inserted into the DB
with deduplication on (source, source_id).
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.llm.verifier import batch_verify_listings, merge_llm_fields
from app.models.listing import Listing
from app.notifier import send_session_expiry_alert
from app.scrapers.base import ScraperResult
from app.scrapers.facebook_groups import _load_fb_context, check_session_health

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCE = "facebook_marketplace"
MARKETPLACE_URL = "https://www.facebook.com/marketplace/haifa/propertyrentals/"

# Adapted from verifier.py VERIFY_PROMPT — Marketplace-aware variant.
# Marketplace cards have structured title + price fields plus an optional
# free-form Hebrew description, so the prompt reflects both modes.
MARKETPLACE_VERIFY_PROMPT = """You are analyzing a Facebook Marketplace rental listing. The listing has structured fields (title, price) but may also include free-form Hebrew description.

Determine if this is a genuine RENTAL listing. Reject if it is:
- A "looking for apartment" post (מחפש/ה דירה)
- A sale listing (למכירה / מכירה)
- Spam, advertising, or unrelated content
- A roommate search (שותף/ה)

If it IS a rental listing, extract these fields:
- price: Monthly rent in ILS (integer, no currency symbol)
- rooms: Number of rooms (float, e.g., 2.5, 3, 3.5)
- size_sqm: Apartment size in square meters (integer)
- address: Full address in Hebrew (street, neighborhood, city)
- contact_info: Contact name and/or phone number

Set confidence (0.0-1.0) based on how clearly the text identifies as a rental \
and how many fields you could extract. High confidence (>0.8) means clear rental \
with most fields extractable. Low confidence (<0.5) means ambiguous text or very \
few fields found.

Listing text:
{text}"""


# ---------------------------------------------------------------------------
# Main scraper function
# ---------------------------------------------------------------------------


async def run_facebook_marketplace_scraper(db: AsyncSession) -> ScraperResult:
    """Scrape Facebook Marketplace (Haifa property rentals) for listings.

    Flow:
    1. Verify session file exists.
    2. Check Facebook session health — alert + skip if expired.
    3. Navigate to the Marketplace Haifa rentals URL.
    4. Scroll 3-5 times to load more cards.
    5. Extract listing cards via ``a[href*="/marketplace/item/"]`` anchors.
    6. Run LLM verification on collected listings.
    7. Insert verified rentals into DB with deduplication.

    Returns ScraperResult. Never raises — all errors are caught and logged.
    """
    result = ScraperResult(source=SOURCE)
    browser = None
    context = None

    try:
        # 1. Check session file existence
        if not Path(settings.facebook_session_path).exists():
            msg = "session file not found: %s" % settings.facebook_session_path
            logger.warning("run_facebook_marketplace_scraper: %s", msg)
            result.errors.append(msg)
            return result

        # 2. Launch browser + context; check session health
        async with async_playwright() as p:
            browser, context = await _load_fb_context(p, settings.facebook_session_path)

            if not await check_session_health(context):
                logger.warning("run_facebook_marketplace_scraper: session expired — alerting user")
                await send_session_expiry_alert()
                result.errors.append(
                    "session_expired: Facebook session requires re-authentication"
                )
                await context.close()
                await browser.close()
                return result

            # 3. Navigate to Marketplace
            page = await context.new_page()
            try:
                await page.goto(
                    MARKETPLACE_URL,
                    wait_until="domcontentloaded",
                    timeout=30000,
                )

                # 4. Scroll to load more listing cards (3-5 scrolls with 2s pauses)
                scroll_count = random.randint(3, 5)
                for _ in range(scroll_count):
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await asyncio.sleep(2)

                # 5. Extract listing cards
                raw_listings: list[dict[str, Any]] = []

                # Primary: anchor links that point to /marketplace/item/ paths
                item_links = await page.locator('a[href*="/marketplace/item/"]').all()

                for link_el in item_links:
                    try:
                        href = await link_el.get_attribute("href")
                        if not href:
                            continue

                        # Normalise to absolute URL
                        if href.startswith("/"):
                            listing_url = "https://www.facebook.com" + href
                        else:
                            listing_url = href

                        # source_id: numeric item ID from URL
                        id_match = re.search(r"/item/(\d+)", href)
                        if not id_match:
                            continue
                        source_id = id_match.group(1)

                        # Extract card text for title / price / location
                        card_text = await link_el.inner_text()
                        lines = [ln.strip() for ln in card_text.splitlines() if ln.strip()]

                        title = lines[0] if lines else ""
                        price: int | None = None
                        location = ""
                        description = ""

                        # Walk remaining lines looking for price and location
                        for line in lines[1:]:
                            # Price line: contains ₪ or a plain number like 3,500
                            if price is None:
                                price_match = re.search(r"[\d,]+", line.replace(",", ""))
                                if "₪" in line or re.match(r"^\d[\d,]+$", line.strip()):
                                    digits = re.sub(r"[^\d]", "", line)
                                    if digits:
                                        try:
                                            price = int(digits)
                                        except ValueError:
                                            pass
                                    continue
                            # First non-price line after title is typically location
                            if not location:
                                location = line
                            else:
                                description += " " + line

                        raw_listings.append({
                            "source_id": source_id,
                            "listing_url": listing_url,
                            "title": title,
                            "price": price,
                            "location": location.strip(),
                            "description": description.strip(),
                            "post_date": datetime.now(timezone.utc).isoformat(),
                        })

                    except Exception as card_exc:
                        logger.debug(
                            "run_facebook_marketplace_scraper: error extracting card — %s",
                            card_exc,
                        )
                        continue

                # Fallback: if no item links found, try reading main text and parsing
                if not raw_listings:
                    logger.info(
                        "run_facebook_marketplace_scraper: no /marketplace/item/ links found — "
                        "attempting fallback text extraction"
                    )
                    try:
                        main_text = await page.inner_text("main")
                        if main_text.strip():
                            raw_listings.append({
                                "source_id": "fallback_%s" % re.sub(r"\W", "", main_text[:30]),
                                "listing_url": MARKETPLACE_URL,
                                "title": main_text[:200],
                                "price": None,
                                "location": "חיפה",
                                "description": main_text[:500],
                                "post_date": datetime.now(timezone.utc).isoformat(),
                            })
                    except Exception as fb_exc:
                        logger.debug(
                            "run_facebook_marketplace_scraper: fallback extraction failed — %s",
                            fb_exc,
                        )

            except Exception as page_exc:
                logger.warning(
                    "run_facebook_marketplace_scraper: error navigating Marketplace — %s",
                    page_exc,
                )
            finally:
                await page.close()

            await context.close()
            await browser.close()
            browser = None
            context = None

            result.listings_found = len(raw_listings)
            logger.info(
                "run_facebook_marketplace_scraper: extracted %d listing cards",
                result.listings_found,
            )

            if not raw_listings:
                return result

            # 6. LLM verification
            texts_for_llm = [
                f"[רישום מפייסבוק מרקטפלייס]\nכותרת: {item['title']}\n"
                f"מחיר: {item['price']}\nמיקום: {item['location']}\n{item['description']}"
                for item in raw_listings
            ]

            llm_results = await batch_verify_listings(texts_for_llm)

            # 7. Insert verified listings
            for item, llm_result in zip(raw_listings, llm_results):
                if not llm_result.get("is_rental", False):
                    result.listings_rejected += 1
                    continue

                confidence = llm_result.get("confidence", 0.0)
                if confidence < settings.llm_confidence_threshold:
                    result.listings_flagged += 1
                    # Still insert flagged listings — kept for user review

                scraper_data: dict[str, Any] = {
                    "price": item.get("price"),
                    "rooms": None,
                    "size_sqm": None,
                    "address": item.get("location") or None,
                    "contact_info": None,
                }
                merged = merge_llm_fields(scraper_data, llm_result)

                stmt = (
                    sqlite_insert(Listing)
                    .values(
                        source=SOURCE,
                        source_id=item["source_id"],
                        title=item["title"][:200] if item["title"] else None,
                        price=merged.get("price"),
                        rooms=merged.get("rooms"),
                        size_sqm=merged.get("size_sqm"),
                        address=merged.get("address"),
                        contact_info=merged.get("contact_info"),
                        url=item["listing_url"] or None,
                        source_badge="מרקטפלייס",
                        raw_data=json.dumps({
                            "title": item["title"],
                            "price": item["price"],
                            "location": item["location"],
                            "description": item["description"],
                            "post_date": item["post_date"],
                        }, ensure_ascii=False),
                        llm_confidence=merged.get("llm_confidence"),
                        is_active=True,
                    )
                    .on_conflict_do_nothing(index_elements=["source", "source_id"])
                )

                insert_result = await db.execute(stmt)
                if insert_result.rowcount > 0:
                    result.listings_inserted += 1
                else:
                    result.listings_skipped += 1

            await db.commit()

            logger.info(
                "run_facebook_marketplace_scraper: done — found=%d inserted=%d skipped=%d "
                "rejected=%d flagged=%d",
                result.listings_found,
                result.listings_inserted,
                result.listings_skipped,
                result.listings_rejected,
                result.listings_flagged,
            )

    except Exception as exc:
        logger.error(
            "run_facebook_marketplace_scraper: unhandled exception — %s", exc, exc_info=True
        )
        result.success = False
        result.errors.append(str(exc))
        # Ensure browser is cleaned up on unexpected error
        try:
            if context is not None:
                await context.close()
        except Exception:
            pass
        try:
            if browser is not None:
                await browser.close()
        except Exception:
            pass

    return result
