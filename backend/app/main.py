from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI

from app.config import settings
from app.database import engine, Base
from app.models import listing  # noqa: F401 — registers model with Base
from app.routers.listings import router
from app.scheduler import scheduler, run_yad2_scrape_job, get_health_state


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist (checkfirst=True prevents race on multi-worker startup)
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, checkfirst=True))

    # SCHED-03: embedded scheduler starts with FastAPI process
    scheduler.add_job(
        run_yad2_scrape_job,
        trigger="interval",
        hours=settings.scrape_interval_hours,  # SCHED-01: configurable interval
        id="yad2_scrape",
        max_instances=1,       # SCHED-02: no duplicate concurrent runs
        coalesce=True,         # Missed fires collapse to one
        misfire_grace_time=300,
        next_run_time=datetime.now(timezone.utc),  # D-01: fire immediately on startup
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="ApartmentFinder API", lifespan=lifespan)


@app.get("/api/health")
async def health():
    """Enhanced health endpoint with per-source scraper run data."""
    state = get_health_state()
    scrapers = {}
    for source, result in state.items():
        if result is None:
            scrapers[source] = {
                "last_run": None,
                "listings_found": None,
                "listings_inserted": None,
                "success": None,
                "errors": None,
            }
        else:
            scrapers[source] = result
    return {"status": "ok", "scrapers": scrapers}


app.include_router(router)
