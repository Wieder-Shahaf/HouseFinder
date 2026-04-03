from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.scrapers.base import ScraperResult

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

# Module-level health state — lost on process restart (per D-02)
_health: dict[str, Optional[dict]] = {
    "yad2": None,
    "madlan": None,
}


def get_health_state() -> dict[str, Optional[dict]]:
    """Return current health state dict. Read by GET /health endpoint."""
    return _health


async def run_yad2_scrape_job() -> None:
    """APScheduler job: run Yad2 scraper → geocoding pass → dedup pass → notify (D-12)."""
    from app.database import async_session_factory
    from app.geocoding import run_dedup_pass, run_geocoding_pass
    from app.notifier import run_notification_job  # deferred import
    from app.scrapers.yad2 import run_yad2_scraper

    started_at = datetime.now(timezone.utc)
    logger.info("Yad2 scrape job started")
    try:
        async with async_session_factory() as session:
            result: ScraperResult = await run_yad2_scraper(session)
            # Chain: geocode NULL-lat listings, then dedup by fingerprint (D-12)
            await run_geocoding_pass(session)
            await run_dedup_pass(session)
            await run_notification_job(session, started_at)
    except Exception as exc:
        logger.exception("Yad2 scrape job failed: %s", exc)
        result = ScraperResult(source="yad2", success=False, errors=[str(exc)])

    _health["yad2"] = {
        "last_run": started_at.isoformat(),
        "listings_found": result.listings_found,
        "listings_inserted": result.listings_inserted,
        "listings_rejected": result.listings_rejected,
        "listings_flagged": result.listings_flagged,
        "success": result.success,
        "errors": result.errors,
    }
    logger.info(
        "Yad2 scrape job completed: found=%d inserted=%d success=%s",
        result.listings_found,
        result.listings_inserted,
        result.success,
    )


async def run_madlan_scrape_job() -> None:
    """APScheduler job: run Madlan scraper → geocoding pass → dedup pass → notify."""
    from app.database import async_session_factory
    from app.geocoding import run_dedup_pass, run_geocoding_pass
    from app.notifier import run_notification_job  # deferred import
    from app.scrapers.madlan import run_madlan_scraper  # deferred import (Phase 3 pattern)

    started_at = datetime.now(timezone.utc)
    logger.info("Madlan scrape job started")
    try:
        async with async_session_factory() as session:
            result: ScraperResult = await run_madlan_scraper(session)
            await run_geocoding_pass(session)
            await run_dedup_pass(session)
            await run_notification_job(session, started_at)
    except Exception as exc:
        logger.exception("Madlan scrape job failed: %s", exc)
        result = ScraperResult(source="madlan", success=False, errors=[str(exc)])

    _health["madlan"] = {
        "last_run": started_at.isoformat(),
        "listings_found": result.listings_found,
        "listings_inserted": result.listings_inserted,
        "listings_rejected": result.listings_rejected,
        "listings_flagged": result.listings_flagged,
        "success": result.success,
        "errors": result.errors,
    }
    logger.info(
        "Madlan scrape job completed: found=%d inserted=%d success=%s",
        result.listings_found,
        result.listings_inserted,
        result.success,
    )
