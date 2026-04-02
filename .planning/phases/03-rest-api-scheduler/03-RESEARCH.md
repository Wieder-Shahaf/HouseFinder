# Phase 3: REST API + Scheduler - Research

**Researched:** 2026-04-02
**Domain:** FastAPI query parameters / APScheduler 3.x AsyncIOScheduler / async SQLAlchemy session management outside dependency injection
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Fire the first Yad2 scrape immediately on startup (not after the first 2-hour interval). Use APScheduler `next_run_time=datetime.now(timezone.utc)` on the first job registration.
- **D-02:** Track run results in an in-memory dict — a module-level `dict[str, ScraperResult]` updated after each scheduler run. `GET /health` reads from this dict. Data is lost on process restart (shows "never run" until next run completes). No new DB table or migration needed.
- **D-03:** `GET /listings` with no params returns all active listings (`is_active=True`). No default exclusion of `is_seen=True`.
- **D-04:** Low-confidence listings (`llm_confidence < threshold`) are excluded by default from all `GET /listings` responses. They remain in the DB but are invisible to the frontend unless a future admin endpoint explicitly requests them.
- **D-05:** Implement neighborhood filtering via address text matching — filter on `address` column containing כרמל / מרכז העיר / נווה שאנן. Phase 5 replaces this with coordinate-based matching.

### Claude's Discretion

- Query param naming conventions (e.g., `price_max`, `rooms_min`, `is_seen`, `neighborhood`)
- Pagination design (if any — not in success criteria, but may be useful)
- Whether to add a `neighborhood` column to the Listing model or derive from `address` at query time
- Exact APScheduler job config (interval trigger, coalesce setting, misfire grace time)
- In-memory health dict structure and thread-safety approach

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCHED-01 | All scrapers run automatically on a configurable interval (default: every 2 hours) | APScheduler `IntervalTrigger(hours=2)` with `scrape_interval_hours` added to `Settings`; D-01 covers immediate first-run via `next_run_time` |
| SCHED-02 | Overlapping runs are prevented (job lock — a new run does not start if previous is still running) | APScheduler `max_instances=1` on the job is the canonical mechanism; verified in APScheduler 3.x docs |
| SCHED-03 | Scheduler is embedded in the backend process (APScheduler — no separate service needed) | `AsyncIOScheduler` started/stopped inside FastAPI `lifespan` context manager; already stubbed in `main.py` |
</phase_requirements>

---

## Summary

Phase 3 wires together three independent concerns: (1) a fully filtered `GET /listings` REST endpoint, (2) two mutation endpoints for seen/favorited state, and (3) an embedded APScheduler that runs the Yad2 scraper on a 2-hour interval with no overlap. All three concerns are well-understood with the existing stack — this is primarily assembly work, not discovery.

The APScheduler integration has one non-obvious wrinkle: the scheduler job runs outside FastAPI's dependency injection system. It cannot use `Depends(get_db)`. It must open a session directly from `async_session_factory` and manage its own transaction lifecycle. The `async_session_factory` is already exported from `backend/app/database.py` — the job function just needs to call `async with async_session_factory() as session:` directly.

The REST API filtering is straightforward FastAPI query parameter work. The `address`-based neighborhood filter (D-05) requires a SQLAlchemy `or_()` + `ilike()` construct rather than an equality match since neighborhood names appear within a free-text address string.

**Primary recommendation:** Use `AsyncIOScheduler` with `max_instances=1`, `coalesce=True`, and `next_run_time=datetime.now(timezone.utc)` in the `lifespan` startup. The health dict should be module-level in a new `backend/app/scheduler.py` module that also owns the scheduler instance — this keeps `main.py` lean.

---

## Standard Stack

### Core (already in requirements.txt — no new installs)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| APScheduler | 3.11.2 (installed) | Periodic scheduler | Already in requirements.txt; embedded in-process |
| FastAPI | 0.128.8 (installed) | REST API framework | Already in use |
| SQLAlchemy | 2.0.48 (installed) | Async ORM / query layer | Already in use |
| pydantic | 2.12.5 (installed) | Query param validation | FastAPI-native; `Query()` uses Pydantic under the hood |

No new packages are needed for Phase 3. All required libraries are already installed and pinned in `requirements.txt`.

**Installation:**
```bash
# No new dependencies — all required libraries already present in requirements.txt
```

---

## Architecture Patterns

### Recommended File Structure for Phase 3

```
backend/app/
├── scheduler.py          # NEW: AsyncIOScheduler instance + health dict + job function
├── routers/
│   └── listings.py       # REPLACE stub: full GET/PUT implementation
├── main.py               # MODIFY: wire scheduler into lifespan, expand /health endpoint
└── config.py             # MODIFY: add scrape_interval_hours setting
```

No new directories needed. `schemas/listing.py` and `models/listing.py` are unchanged.

---

### Pattern 1: AsyncIOScheduler in FastAPI Lifespan

**What:** The scheduler is instantiated at module level in `scheduler.py`, and started/stopped inside the `lifespan` async context manager in `main.py`.

**When to use:** Any time you need periodic in-process background work with FastAPI.

**Why `AsyncIOScheduler` over `BackgroundScheduler`:** `BackgroundScheduler` uses a separate OS thread; `AsyncIOScheduler` runs on the same event loop as FastAPI/uvicorn. Since the job function is `async def` and uses `aiosqlite`, it must run on the asyncio event loop — `AsyncIOScheduler` is the correct choice.

```python
# backend/app/scheduler.py
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler(timezone="UTC")

async def run_scrape_job() -> None:
    """Job function — creates its own DB session, not via FastAPI DI."""
    from app.database import async_session_factory
    from app.scrapers.yad2 import run_yad2_scraper
    async with async_session_factory() as session:
        result = await run_yad2_scraper(session)
    # Update in-memory health dict after run
    _health["yad2"] = result
```

```python
# backend/app/main.py — lifespan modification
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from app.scheduler import scheduler, run_scrape_job
from app.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        run_scrape_job,
        trigger="interval",
        hours=settings.scrape_interval_hours,
        id="yad2_scrape",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
        next_run_time=datetime.now(timezone.utc),  # D-01: fire immediately on startup
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)
```

**Source:** APScheduler 3.x official docs — https://apscheduler.readthedocs.io/en/3.x/userguide.html

---

### Pattern 2: Job Lock via max_instances=1

**What:** `max_instances=1` (the APScheduler default) prevents a new job instance from starting if one is already running.

**SCHED-02 implementation:** Set `max_instances=1` on `add_job()`. When the interval fires and the previous run hasn't finished, APScheduler logs a warning and skips that execution — no duplicate run starts.

**Note on coalesce vs max_instances:**
- `coalesce=True`: If multiple trigger times were missed (e.g., process was paused), fire only once instead of all at once.
- `max_instances=1`: If trigger fires while previous run is still executing, do not start a new run.
Both should be set. They guard against different scenarios.

```python
scheduler.add_job(
    run_scrape_job,
    trigger="interval",
    hours=2,
    id="yad2_scrape",
    max_instances=1,   # SCHED-02: no duplicate concurrent runs
    coalesce=True,     # Missed fires collapse to one
    misfire_grace_time=300,  # Allow up to 5 min late start before considering missed
    next_run_time=datetime.now(timezone.utc),  # D-01: fire immediately
)
```

---

### Pattern 3: Scheduler Job Creates Its Own DB Session

**What:** APScheduler jobs run outside FastAPI's request lifecycle. FastAPI's `Depends(get_db)` generator is not available to the job function. The job must create its own session using the exported `async_session_factory`.

**Why this matters:** Using `get_db()` directly inside a job (calling it as a plain function instead of via `Depends`) would not properly manage the session context — it is an async generator and must be driven by a context manager or `async for`.

**Correct pattern:**
```python
# backend/app/scheduler.py
from app.database import async_session_factory  # exported async_sessionmaker

async def run_scrape_job() -> None:
    async with async_session_factory() as session:
        result = await run_yad2_scraper(session)
    # session is committed/closed when async with block exits
    _health["yad2"] = result
```

**Source:** SQLAlchemy async docs — https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

---

### Pattern 4: In-Memory Health Dict (D-02)

**What:** A module-level dict in `scheduler.py` stores the last `ScraperResult` per source key. `GET /health` reads this dict. No database access needed for health endpoint.

**Thread safety note:** `AsyncIOScheduler` runs job callbacks on the asyncio event loop (same thread as FastAPI). Python dict reads/writes in a single-threaded asyncio context are safe without locks. No `asyncio.Lock` is needed.

```python
# backend/app/scheduler.py
from typing import Optional
from app.scrapers.base import ScraperResult

# Module-level health state — reset on process restart (D-02)
_health: dict[str, Optional[ScraperResult]] = {
    "yad2": None,
}

def get_health_state() -> dict[str, Optional[ScraperResult]]:
    return _health
```

```python
# Health response in main.py (or a dedicated health router)
from app.scheduler import get_health_state

@app.get("/api/health")
async def health():
    state = get_health_state()
    scrapers = {}
    for source, result in state.items():
        if result is None:
            scrapers[source] = {"last_run": None, "listings_inserted": None, "success": None}
        else:
            scrapers[source] = {
                "last_run": result.last_run_at.isoformat() if hasattr(result, "last_run_at") else None,
                "listings_found": result.listings_found,
                "listings_inserted": result.listings_inserted,
                "listings_rejected": result.listings_rejected,
                "listings_flagged": result.listings_flagged,
                "success": result.success,
                "errors": result.errors,
            }
    return {"status": "ok", "scrapers": scrapers}
```

**Note:** `ScraperResult` in `base.py` does not currently have a `last_run_at` timestamp field. The job function should record `datetime.now(timezone.utc)` when the run completes and attach it to the result, or store it separately in the health dict. This is a Claude's-discretion decision.

---

### Pattern 5: FastAPI Query Parameters for Filtering

**What:** FastAPI accepts typed query parameters using `Query()` from `fastapi`. SQLAlchemy filters are applied conditionally.

```python
# backend/app/routers/listings.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import List, Optional
from app.database import get_db
from app.models.listing import Listing
from app.schemas.listing import ListingResponse
from app.config import settings

router = APIRouter(prefix="/api/listings", tags=["listings"])

@router.get("/", response_model=List[ListingResponse])
async def get_listings(
    price_min: Optional[int] = Query(None, ge=0),
    price_max: Optional[int] = Query(None, ge=0),
    rooms_min: Optional[float] = Query(None, ge=0),
    rooms_max: Optional[float] = Query(None, ge=0),
    neighborhood: Optional[str] = Query(None),  # כרמל | מרכז העיר | נווה שאנן
    is_seen: Optional[bool] = Query(None),
    is_favorited: Optional[bool] = Query(None),
    since_hours: Optional[int] = Query(None, ge=1),  # recency filter
    db: AsyncSession = Depends(get_db),
):
    filters = [
        Listing.is_active == True,
        Listing.llm_confidence >= settings.llm_confidence_threshold,  # D-04
    ]
    if price_min is not None:
        filters.append(Listing.price >= price_min)
    if price_max is not None:
        filters.append(Listing.price <= price_max)
    if rooms_min is not None:
        filters.append(Listing.rooms >= rooms_min)
    if rooms_max is not None:
        filters.append(Listing.rooms <= rooms_max)
    if is_seen is not None:
        filters.append(Listing.is_seen == is_seen)
    if is_favorited is not None:
        filters.append(Listing.is_favorited == is_favorited)
    if since_hours is not None:
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        filters.append(Listing.created_at >= cutoff)
    if neighborhood is not None:
        filters.append(Listing.address.ilike(f"%{neighborhood}%"))  # D-05

    stmt = select(Listing).where(and_(*filters)).order_by(Listing.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()
```

**Note on D-04 and NULL llm_confidence:** The filter `Listing.llm_confidence >= threshold` will exclude rows where `llm_confidence IS NULL` in SQLite (NULL comparison returns NULL, not True). This is the desired behavior — listings without LLM verification are also excluded. If a listing came from a source that doesn't run LLM verification, it would be excluded. Verify this is acceptable for the current Yad2-only phase (all listings go through LLM pipeline).

---

### Pattern 6: Mutation Endpoints for Seen / Favorited

```python
@router.put("/{listing_id}/seen", response_model=ListingResponse)
async def mark_seen(listing_id: int, db: AsyncSession = Depends(get_db)):
    listing = await db.get(Listing, listing_id)
    if listing is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Listing not found")
    listing.is_seen = True
    await db.commit()
    await db.refresh(listing)
    return listing

@router.put("/{listing_id}/favorited", response_model=ListingResponse)
async def mark_favorited(listing_id: int, db: AsyncSession = Depends(get_db)):
    listing = await db.get(Listing, listing_id)
    if listing is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Listing not found")
    listing.is_favorited = True
    await db.commit()
    await db.refresh(listing)
    return listing
```

**Note:** Success criteria say "update the listing state" — they do not say toggle. Treating them as idempotent set-to-true is the simplest correct implementation. If unset semantics are needed (mark-unseen, unfavorite), that is left for Phase 4 to request.

---

### Anti-Patterns to Avoid

- **Using BackgroundScheduler instead of AsyncIOScheduler:** `BackgroundScheduler` creates an OS thread. When the job runs `await run_yad2_scraper(session)`, it would need `asyncio.run()` inside a thread — creating a new event loop that conflicts with aiosqlite's existing connection. Always use `AsyncIOScheduler` when jobs are `async def`.
- **Calling get_db() directly inside the scheduler job:** `get_db()` is an async generator function for FastAPI's `Depends()` machinery. Calling it as `session = get_db()` returns a generator object, not a session. Use `async_session_factory()` directly.
- **Module-level scheduler.start() call:** Starting the scheduler at import time (outside `lifespan`) causes the scheduler to run during test collection, firing real scraper jobs in tests. Always start inside `lifespan`.
- **Importing scheduler in conftest without stopping it:** In tests that import `app` (which imports `scheduler`), the scheduler instance exists but should not be started. Tests that trigger `lifespan` must explicitly stop the scheduler or mock it.
- **`and_()` with an empty list:** If all filters are optional and none are passed, `and_(*[])` returns `True` which is fine in SQLAlchemy 2.x. But explicitly including `is_active=True` and the confidence filter means the list is never empty — this is safe.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Job overlap prevention | Custom `is_running` flag in a global variable | `max_instances=1` on APScheduler job | APScheduler handles concurrent-trigger-while-running correctly; a global flag has race conditions in async context |
| Interval scheduling with retry | Custom `asyncio.sleep()` loop in a background task | `AsyncIOScheduler` with `IntervalTrigger` | APScheduler handles missed fires, coalescing, and clean shutdown; sleep loops lose all of this |
| DB session in scheduler job | New engine/sessionmaker inside job function | `async_session_factory` imported from `database.py` | Reuse the existing configured engine; creating a new engine per run leaks connections |
| Query param validation | Manual type checks in endpoint body | FastAPI `Query(ge=0)` annotations | FastAPI generates 422 responses automatically with field-level validation errors |

---

## Common Pitfalls

### Pitfall 1: AsyncIOScheduler job fires before lifespan completes

**What goes wrong:** If the scheduler's `next_run_time=datetime.now(timezone.utc)` fires before the FastAPI app is fully initialized (e.g., before routers are registered), the job may attempt DB operations before tables are confirmed to exist via Alembic.

**Why it happens:** APScheduler fires the first run immediately after `scheduler.start()`, which is called at the top of the `lifespan` async context. In practice, Alembic runs at deploy time (not at startup), so tables already exist. But if someone runs the backend without running migrations first, the job will fail.

**How to avoid:** Document that `alembic upgrade head` must run before starting the server. The scheduler job should also catch and log exceptions rather than letting them propagate (APScheduler catches exceptions in jobs but logs them; ensure logging is configured).

---

### Pitfall 2: llm_confidence NULL excludes pre-LLM listings

**What goes wrong:** The filter `llm_confidence >= 0.7` silently excludes all listings where `llm_confidence IS NULL`. In SQLite, `NULL >= 0.7` evaluates to NULL (falsy), so those rows are filtered out.

**Why it happens:** SQLite's three-valued NULL logic. This is actually the desired behavior per D-04, but it should be documented so future phases (Madlan, Facebook) know their scrapers must run LLM verification or their listings will never appear in the API.

**How to avoid:** This is a design decision, not a bug. Document it in the API contract. Add a comment in the query.

---

### Pitfall 3: scheduler.shutdown() blocks if wait=True and job is running

**What goes wrong:** If the Yad2 scraper is mid-run when the server receives SIGTERM, `scheduler.shutdown(wait=True)` will block the process until the job completes. With Playwright/httpx calls this could take 30-60 seconds, causing Docker to force-kill after the grace period.

**How to avoid:** Use `scheduler.shutdown(wait=False)` in the lifespan teardown. The job may be interrupted mid-scrape, but since the DB uses commit-per-insert (or transaction-per-batch), partial runs just result in fewer inserted listings — no corruption.

---

### Pitfall 4: Address ilike filter misses partial Hebrew matches

**What goes wrong:** `Listing.address.ilike("%כרמל%")` filters correctly for exact neighborhood name presence. But if Yad2 returns address strings like "כרמל, חיפה" or "שכונת כרמל" it works fine. The risk is that a future neighborhood like "קרית" might contain a substring match — unlikely with the current three names but worth documenting.

**How to avoid:** The three neighborhood names (כרמל, מרכז העיר, נווה שאנן) are distinct enough that substring matching is safe. Phase 5 will replace this with coordinate-based matching anyway (D-05 is explicitly provisional).

---

### Pitfall 5: Test isolation — scheduler started by lifespan

**What goes wrong:** Tests using `AsyncClient(transport=ASGITransport(app=app))` trigger FastAPI's `lifespan`, which starts the `AsyncIOScheduler` and fires the first scraper job immediately (due to `next_run_time=now`). This causes the test to attempt a real HTTP call to Yad2 and a real Anthropic API call.

**How to avoid:** In the `conftest.py` client fixture, either (a) mock `scheduler.start()` so it's a no-op during tests, or (b) add a `TESTING=true` env var check in `lifespan` that skips scheduler startup. Option (b) is cleaner for long-term test isolation. Alternatively, move the `client` fixture to use `app_override` where the scheduler is patched.

The existing conftest `client` fixture does NOT trigger lifespan because it uses `AsyncClient(transport=ASGITransport(app=app))` without `with app.lifespan_context()` — but verify this in practice: FastAPI's ASGI transport does run lifespan by default in recent versions.

---

## Code Examples

### Complete scheduler.py module

```python
# Source: pattern from APScheduler 3.x docs + project conventions
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.scrapers.base import ScraperResult

scheduler = AsyncIOScheduler(timezone="UTC")

# Module-level health state — lost on process restart (D-02)
_health: dict[str, Optional[dict]] = {
    "yad2": None,
}


def get_health_state() -> dict[str, Optional[dict]]:
    return _health


async def run_yad2_scrape_job() -> None:
    """APScheduler job: create own DB session, run scraper, update health dict."""
    from app.database import async_session_factory
    from app.scrapers.yad2 import run_yad2_scraper

    started_at = datetime.now(timezone.utc)
    try:
        async with async_session_factory() as session:
            result: ScraperResult = await run_yad2_scraper(session)
    except Exception as exc:
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
```

### lifespan wiring in main.py

```python
# Source: APScheduler 3.x docs + FastAPI lifespan pattern
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from app.scheduler import scheduler, run_yad2_scrape_job
from app.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        run_yad2_scrape_job,
        trigger="interval",
        hours=settings.scrape_interval_hours,
        id="yad2_scrape",
        max_instances=1,      # SCHED-02: no duplicate concurrent runs
        coalesce=True,        # Missed fires collapse to one
        misfire_grace_time=300,
        next_run_time=datetime.now(timezone.utc),  # D-01: fire immediately on startup
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)
```

### Settings addition (config.py)

```python
# Add to Settings class — controls SCHED-01
scrape_interval_hours: int = 2
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `BackgroundScheduler` + `asyncio.run()` in thread | `AsyncIOScheduler` with native `async def` jobs | APScheduler 3.x onward | Eliminates thread/event-loop conflicts with aiosqlite |
| `@app.on_event("startup")` / `@app.on_event("shutdown")` decorators | `lifespan` asynccontextmanager | FastAPI 0.95+ | `on_event` is deprecated; `lifespan` is the current pattern |
| `scheduler.scheduled_job()` decorator | `scheduler.add_job()` in lifespan | No change — both still valid in 3.x | `add_job()` is preferred when startup-time config (interval, next_run_time) must be read from settings |

---

## Open Questions

1. **Should the client fixture skip lifespan in tests?**
   - What we know: `ASGITransport` in httpx does trigger ASGI lifespan events as of httpx 0.23+
   - What's unclear: Whether `AsyncClient` in the existing conftest triggers lifespan or not — needs a quick test run
   - Recommendation: Add a Wave 0 test task to verify. If lifespan fires in tests, mock `scheduler.start()` in the client fixture.

2. **`since_hours` vs `since_days` — recency filter granularity**
   - What we know: MAP-04 calls for "new only" toggle (last 24h / 48h) in the frontend
   - What's unclear: Whether to expose `since_hours` (flexible) or a fixed `recency` enum (`24h` / `48h`) in Phase 3
   - Recommendation: `since_hours: Optional[int]` covers both Phase 3 and Phase 4 needs without over-constraining the API surface.

3. **Pagination**
   - What we know: Not in Phase 3 success criteria; at single-user scale with hundreds of listings, full result sets are manageable
   - Recommendation: Skip pagination for now. Add `limit` and `offset` params in a later phase if needed.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| APScheduler | SCHED-01, SCHED-02, SCHED-03 | Yes | 3.11.2 | — |
| FastAPI | REST API | Yes | 0.128.8 | — |
| SQLAlchemy (async) | DB queries | Yes | 2.0.48 | — |
| aiosqlite | Async SQLite driver | Yes | 0.22.1 | — |
| pytest + pytest-asyncio | Testing | Yes | pytest>=8.0, pytest-asyncio>=0.23 | — |

No missing dependencies. All required libraries already installed and pinned.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `backend/pytest.ini` (`asyncio_mode = auto`) |
| Quick run command | `cd backend && pytest tests/test_api.py tests/test_scheduler.py -x -q` |
| Full suite command | `cd backend && pytest -x -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCHED-01 | Scraper runs on configurable interval | unit (mock scheduler) | `pytest tests/test_scheduler.py::test_job_registered_with_correct_interval -x` | Wave 0 |
| SCHED-02 | Second run does not start while first is running | unit (APScheduler max_instances) | `pytest tests/test_scheduler.py::test_job_max_instances_is_one -x` | Wave 0 |
| SCHED-03 | Scheduler starts/stops inside FastAPI lifespan | integration | `pytest tests/test_scheduler.py::test_scheduler_lifecycle -x` | Wave 0 |
| (API) | GET /listings with no params returns active+high-confidence listings | unit | `pytest tests/test_api.py::test_get_listings_default -x` | Wave 0 |
| (API) | GET /listings filters by price_max | unit | `pytest tests/test_api.py::test_get_listings_price_filter -x` | Wave 0 |
| (API) | GET /listings filters by neighborhood (address ilike) | unit | `pytest tests/test_api.py::test_get_listings_neighborhood_filter -x` | Wave 0 |
| (API) | GET /listings excludes low-confidence by default (D-04) | unit | `pytest tests/test_api.py::test_get_listings_excludes_low_confidence -x` | Wave 0 |
| (API) | PUT /listings/{id}/seen updates is_seen and returns 200 | unit | `pytest tests/test_api.py::test_mark_seen -x` | Wave 0 |
| (API) | PUT /listings/{id}/favorited updates is_favorited and returns 200 | unit | `pytest tests/test_api.py::test_mark_favorited -x` | Wave 0 |
| (API) | PUT /listings/{id}/seen returns 404 for unknown id | unit | `pytest tests/test_api.py::test_mark_seen_not_found -x` | Wave 0 |
| (API) | GET /health returns last_run timestamps and listing counts | unit | `pytest tests/test_api.py::test_health_with_scraper_state -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `cd backend && pytest tests/test_api.py tests/test_scheduler.py -x -q`
- **Per wave merge:** `cd backend && pytest -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_scheduler.py` — covers SCHED-01, SCHED-02, SCHED-03 (scheduler unit tests with mocked job function)
- [ ] `backend/tests/test_api.py` — expand from current 1-test stub to full listings filter + mutation + health tests
- [ ] Conftest update — client fixture may need scheduler mock to prevent real job execution during tests

---

## Sources

### Primary (HIGH confidence)
- APScheduler 3.11.2 official docs — https://apscheduler.readthedocs.io/en/3.x/ — `AsyncIOScheduler`, `max_instances`, `coalesce`, `next_run_time`, `add_job()`
- SQLAlchemy async docs — https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html — `async_sessionmaker`, session lifecycle outside DI
- FastAPI Query params docs — https://fastapi.tiangolo.com/tutorial/query-params/ — `Query()` annotation pattern
- Codebase direct read — `backend/app/main.py`, `backend/app/database.py`, `backend/app/models/listing.py`, `backend/app/schemas/listing.py`, `backend/app/scrapers/base.py`, `backend/app/config.py`, `backend/requirements.txt`

### Secondary (MEDIUM confidence)
- APScheduler GitHub discussion #999 — async jobs and event loop behavior confirmed
- nashruddinamin.com FastAPI+APScheduler pattern — verified against official docs

### Tertiary (LOW confidence)
- None — all critical claims verified via official docs or direct codebase inspection

---

## Project Constraints (from CLAUDE.md)

| Directive | Applies to Phase 3 |
|-----------|-------------------|
| Python 3.12 runtime | Backend code must be Python 3.12-compatible (note: local machine runs 3.9, Docker uses 3.12) |
| FastAPI 0.111+ | Already at 0.128.8 — compliant |
| APScheduler 3.10+ | Already at 3.11.2 — compliant |
| SQLAlchemy 2.0+ with async | Already in use — session pattern confirmed |
| pydantic 2.7+ | Already at 2.12.5 — compliant |
| Single-user scale — no concurrency optimization needed | REST endpoints don't need connection pooling tuning |
| No GSD workflow bypass | Phase work must go through `/gsd:execute-phase` |
| from __future__ import annotations for Python 3.9 union type syntax | Add to scheduler.py and modified routers/listings.py |

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and in active use in the codebase
- Architecture: HIGH — APScheduler 3.x patterns verified against official docs; SQLAlchemy async session pattern verified
- Pitfalls: HIGH — all pitfalls derived from direct code analysis and verified APScheduler/FastAPI behavior

**Research date:** 2026-04-02
**Valid until:** 2026-07-02 (90 days — APScheduler 3.x and FastAPI are stable; unlikely to change)
