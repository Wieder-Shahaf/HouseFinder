"""Facebook Groups scraper for apartment rental listings.

Scrapes user-defined Facebook groups for rental posts. Uses a saved Playwright
session (facebook_session.json) for authenticated access. Checks session health
before scraping and sends a Web Push alert if the session has expired.

Groups are loaded from /data/facebook_groups.json (format: list of dicts with
url and name keys, e.g. [{"url": "...", "name": "שכירות חיפה"}]).

Extracted posts are verified via the LLM pipeline and inserted into the DB
with deduplication on (source, source_id).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import re
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.llm.verifier import batch_verify_listings, merge_llm_fields
from app.models.listing import Listing
from app.notifier import send_session_expiry_alert
from app.scrapers.base import ScraperResult
from app.scrapers.proxy import get_proxy_launch_args

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GROUPS_FILE = Path("/data/facebook_groups.json")
SOURCE = "facebook_groups"

# Adapted from verifier.py VERIFY_PROMPT — same structure but Facebook-aware
FACEBOOK_VERIFY_PROMPT = """You are analyzing a Hebrew post from a Facebook apartment rental group. The post may be informal/free-form text.

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
# Helper functions
# ---------------------------------------------------------------------------


def _load_groups() -> list[dict]:
    """Load the Facebook group list from GROUPS_FILE.

    Returns a list of dicts with at minimum 'url' and 'name' keys.
    Returns empty list if the file is missing or contains an empty array.
    Does not raise — callers should handle the empty-list case gracefully.
    """
    try:
        content = GROUPS_FILE.read_text(encoding="utf-8")
        groups = json.loads(content)
        if not isinstance(groups, list):
            logger.warning("_load_groups: expected list in %s, got %s", GROUPS_FILE, type(groups))
            return []
        if not groups:
            logger.info("_load_groups: %s contains an empty list", GROUPS_FILE)
        return groups
    except FileNotFoundError:
        logger.warning("_load_groups: %s not found — returning empty list", GROUPS_FILE)
        return []
    except Exception as exc:
        logger.warning("_load_groups: failed to parse %s — %s", GROUPS_FILE, exc)
        return []


async def _load_fb_context(p: Any, session_path: str) -> tuple[Any, Any]:
    """Create a Playwright browser + context with a saved Facebook session.

    Args:
        p:            async_playwright() instance.
        session_path: Path to the saved session JSON (facebook_session.json).

    Returns:
        (browser, context) tuple. Caller must close both when done.
    """
    browser = await p.chromium.launch(headless=True, **get_proxy_launch_args())
    context = await browser.new_context(
        storage_state=session_path,
        locale="he-IL",
        viewport={"width": 1280, "height": 800},
        extra_http_headers={"Accept-Language": "he-IL,he;q=0.9"},
    )
    await Stealth().apply_stealth_async(context)
    return browser, context


async def check_session_health(context: Any) -> bool:
    """Check whether the stored Facebook session is still authenticated.

    Opens a new page, navigates to facebook.com, and checks for login/checkpoint
    redirect. Also verifies the LeftRail navigation element is present.

    Returns:
        True  — session is healthy and authenticated.
        False — session has expired or any error occurred.
    """
    page = None
    try:
        page = await context.new_page()
        await page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        current_url = page.url
        if "login" in current_url or "checkpoint" in current_url:
            logger.info("check_session_health: redirected to %s — session expired", current_url)
            return False

        # Secondary check: LeftRail navigation must be present
        left_rail_count = await page.locator('[data-pagelet="LeftRail"]').count()
        if left_rail_count > 0:
            logger.info("check_session_health: session healthy — LeftRail found")
            return True

        logger.info("check_session_health: LeftRail not found — session may be expired")
        return False
    except Exception as exc:
        logger.error("check_session_health: error checking session — %s", exc)
        return False
    finally:
        if page is not None:
            await page.close()


def extract_post_source_id(post_url: str, fallback_text: str = "") -> str:
    """Extract a stable source_id from a Facebook post URL.

    Tries to extract the numeric post ID from permalink or posts URL patterns.
    Falls back to a sha256 hash of the fallback_text if no ID is found.

    Args:
        post_url:      Facebook post URL (may be empty).
        fallback_text: Post text to hash when URL has no extractable ID.

    Returns:
        Numeric ID string (from URL) or 32-char hex digest (from fallback hash).
    """
    if post_url:
        match = re.search(r"/(?:permalink|posts)/(\d+)", post_url)
        if match:
            return match.group(1)
    return hashlib.sha256(fallback_text.encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Main scraper function
# ---------------------------------------------------------------------------


async def run_facebook_groups_scraper(db: AsyncSession) -> ScraperResult:
    """Scrape Facebook group pages for apartment rental listings.

    Flow:
    1. Load group list from /data/facebook_groups.json.
    2. Verify session file exists.
    3. Check Facebook session health — alert + skip if expired.
    4. Iterate each group, extract posts with 5-15s inter-group delay.
    5. Run LLM verification on all collected posts.
    6. Insert verified rentals into DB with deduplication.

    Returns ScraperResult. Never raises — all errors are caught and logged.
    """
    result = ScraperResult(source=SOURCE)
    browser = None
    context = None

    try:
        # 1. Load groups
        groups = _load_groups()
        if not groups:
            logger.info("run_facebook_groups_scraper: no groups configured — skipping")
            return result

        # 2. Check session file
        if not Path(settings.facebook_session_path).exists():
            msg = "session file not found: %s" % settings.facebook_session_path
            logger.warning("run_facebook_groups_scraper: %s", msg)
            result.errors.append(msg)
            return result

        # 3. Launch browser + context; check session health
        async with async_playwright() as p:
            browser, context = await _load_fb_context(p, settings.facebook_session_path)

            if not await check_session_health(context):
                logger.warning("run_facebook_groups_scraper: session expired — alerting user")
                await send_session_expiry_alert()
                result.errors.append(
                    "session_expired: Facebook session requires re-authentication"
                )
                await context.close()
                await browser.close()
                return result

            # 4. Scrape each group
            all_posts: list[dict[str, Any]] = []

            for idx, group in enumerate(groups):
                group_url: str = group.get("url", "")
                group_name: str = group.get("name", "קבוצה לא ידועה")

                if not group_url:
                    logger.warning("run_facebook_groups_scraper: group entry has no url — skipping")
                    continue

                # Inter-group delay (pitfall 5: rate limiting)
                if idx > 0:
                    delay = random.uniform(5, 15)
                    logger.debug(
                        "run_facebook_groups_scraper: waiting %.1fs before group %s",
                        delay, group_name,
                    )
                    await asyncio.sleep(delay)

                try:
                    page = await context.new_page()
                    try:
                        await page.goto(
                            group_url,
                            wait_until="domcontentloaded",
                            timeout=30000,
                        )

                        # Scroll to load more posts (3-5 scrolls with 2s pauses)
                        scroll_count = random.randint(3, 5)
                        for _ in range(scroll_count):
                            await page.evaluate("window.scrollBy(0, window.innerHeight)")
                            await asyncio.sleep(2)

                        # Extract articles
                        articles = await page.locator('[role="article"]').all()
                        group_posts = 0

                        for article in articles:
                            try:
                                post_text = await article.inner_text()
                                if not post_text.strip():
                                    continue

                                # Extract post URL
                                post_url = ""
                                for href_pattern in [
                                    'a[href*="/permalink/"]',
                                    'a[href*="/posts/"]',
                                ]:
                                    link_el = article.locator(href_pattern).first
                                    href = await link_el.get_attribute("href")
                                    if href:
                                        if href.startswith("/"):
                                            post_url = "https://www.facebook.com" + href
                                        else:
                                            post_url = href
                                        break

                                # Extract poster name (first h2/h3/strong)
                                poster_name = ""
                                for name_selector in ["h2", "h3", "strong"]:
                                    name_el = article.locator(name_selector).first
                                    name_text = await name_el.inner_text()
                                    if name_text.strip():
                                        poster_name = name_text.strip()
                                        break

                                # Extract post date (abbr with timestamp or span with id)
                                post_date_text = ""
                                date_el = article.locator("abbr").first
                                date_text = await date_el.inner_text()
                                if date_text:
                                    post_date_text = date_text.strip()

                                source_id = extract_post_source_id(post_url, post_text[:200])

                                all_posts.append({
                                    "source_id": source_id,
                                    "group_name": group_name,
                                    "group_url": group_url,
                                    "post_text": post_text,
                                    "post_url": post_url,
                                    "poster_name": poster_name,
                                    "post_date_text": post_date_text,
                                })
                                group_posts += 1
                            except Exception as article_exc:
                                logger.debug(
                                    "run_facebook_groups_scraper: error extracting article — %s",
                                    article_exc,
                                )
                                continue

                        result.listings_found += group_posts
                        logger.info(
                            "run_facebook_groups_scraper: extracted %d posts from group '%s'",
                            group_posts, group_name,
                        )

                    except Exception as page_exc:
                        logger.warning(
                            "run_facebook_groups_scraper: error scraping group '%s' — %s (continuing)",
                            group_name, page_exc,
                        )
                    finally:
                        await page.close()

                except Exception as group_exc:
                    logger.warning(
                        "run_facebook_groups_scraper: failed to open page for group '%s' — %s",
                        group_name, group_exc,
                    )
                    continue

            await context.close()
            await browser.close()
            browser = None
            context = None

            # 5. LLM verification
            if not all_posts:
                logger.info("run_facebook_groups_scraper: no posts collected — done")
                return result

            # Prefix each post with group context for LLM
            texts_for_llm = [
                f"[פוסט מקבוצת פייסבוק: {p['group_name']}]\n{p['post_text']}"
                for p in all_posts
            ]

            llm_results = await batch_verify_listings(texts_for_llm)

            # 6. Insert verified listings
            for post, llm_result in zip(all_posts, llm_results):
                if not llm_result.get("is_rental", False):
                    result.listings_rejected += 1
                    continue

                confidence = llm_result.get("confidence", 0.0)
                if confidence < settings.llm_confidence_threshold:
                    result.listings_flagged += 1
                    # Still insert flagged listings (low confidence) — they're visible in UI
                    # but flagged for review

                scraper_data: dict[str, Any] = {
                    "price": None,
                    "rooms": None,
                    "size_sqm": None,
                    "address": None,
                    "contact_info": post.get("poster_name") or None,
                }
                merged = merge_llm_fields(scraper_data, llm_result)

                stmt = (
                    sqlite_insert(Listing)
                    .values(
                        source=SOURCE,
                        source_id=post["source_id"],
                        title=post["post_text"][:200] if post["post_text"] else None,
                        price=merged.get("price"),
                        rooms=merged.get("rooms"),
                        size_sqm=merged.get("size_sqm"),
                        address=merged.get("address"),
                        contact_info=merged.get("contact_info"),
                        url=post["post_url"] or None,
                        source_badge="פייסבוק",
                        raw_data=json.dumps({
                            "post_text": post["post_text"],
                            "poster_name": post["poster_name"],
                            "post_date_text": post["post_date_text"],
                            "group_name": post["group_name"],
                            "group_url": post["group_url"],
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
                "run_facebook_groups_scraper: done — found=%d inserted=%d skipped=%d "
                "rejected=%d flagged=%d",
                result.listings_found,
                result.listings_inserted,
                result.listings_skipped,
                result.listings_rejected,
                result.listings_flagged,
            )

    except Exception as exc:
        logger.error("run_facebook_groups_scraper: unhandled exception — %s", exc, exc_info=True)
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
