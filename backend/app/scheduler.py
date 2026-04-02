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
}


def get_health_state() -> dict[str, Optional[dict]]:
    """Return current health state dict. Read by GET /health endpoint."""
    return _health


async def run_yad2_scrape_job() -> None:
    """APScheduler job: create own DB session, run Yad2 scraper, update health dict.

    Uses async_session_factory directly — NOT FastAPI's Depends(get_db).
    """
    from app.database import async_session_factory
    from app.scrapers.yad2 import run_yad2_scraper

    started_at = datetime.now(timezone.utc)
    logger.info("Yad2 scrape job started")
    try:
        async with async_session_factory() as session:
            result: ScraperResult = await run_yad2_scraper(session)
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
