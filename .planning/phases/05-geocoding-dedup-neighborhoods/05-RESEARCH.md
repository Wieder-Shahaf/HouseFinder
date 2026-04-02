# Phase 5: Geocoding + Dedup + Neighborhoods - Research

**Researched:** 2026-04-02
**Domain:** Geocoding (Nominatim + Playwright/Google Maps), deduplication (haversine + SQLAlchemy), APScheduler job chaining
**Confidence:** HIGH

## Summary

Phase 5 adds three data-quality passes that run after each Yad2 scrape: geocoding unresolved Hebrew addresses to coordinates via Nominatim (with a Playwright+Bright Data fallback), tagging each geocoded listing to a Haifa neighborhood via bounding-box lookup, and deduplicating cross-source duplicates by fingerprint. All three operations act on the existing SQLite listings table. The only schema change required is adding a single `neighborhood VARCHAR(100) NULLABLE` column via Alembic.

The implementation is purely additive: a new `backend/app/geocoding.py` module, two new scheduler job functions in `backend/app/scheduler.py`, a new Alembic migration, and small touch-ups to the listings router and schema. No existing scraper or model logic changes. Shapely 2.0.7 is already installed in the project's Python environment (pulled in as an indirect dependency) but is not needed — neighborhood assignment is bounding-box arithmetic (four comparisons), which is simpler inline. Haversine distance for dedup is also best done inline with `math` (stdlib-only, no new dependency).

The critical field name pitfall: Nominatim returns `lon` (not `lng`). The existing Yad2 scraper also uses `lon` internally (`coords.get("lon")`). The Listing model and schema use `lng`. Conversions must be explicit wherever Nominatim results are consumed.

**Primary recommendation:** Implement `backend/app/geocoding.py` as a module with three public coroutine functions — `run_geocoding_pass(session)`, `run_dedup_pass(session)`, and a private `_geocode_address(address)` — then wire them into `scheduler.py` as two new `AsyncIOScheduler` jobs that fire immediately after the existing Yad2 job completes (sequential execution within the Yad2 job function body, not as separate APScheduler-triggered jobs).

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Neighborhood boundaries are defined as hand-drawn bounding boxes hardcoded in a Python dict in `backend/app/geocoding.py`.
```python
NEIGHBORHOODS = {
    "כרמל":       {"lat": (32.78, 32.83), "lng": (34.97, 35.02)},
    "מרכז העיר": {"lat": (32.81, 32.84), "lng": (35.00, 35.03)},
    "נווה שאנן":  {"lat": (32.80, 32.83), "lng": (35.02, 35.05)},
}
```

**D-02:** Listings outside all bounding boxes get `neighborhood=NULL`. They appear on the map without a filter, hidden when a neighborhood filter is active. No "Other" category.

**D-03:** Schema change: add `neighborhood VARCHAR(100) NULLABLE` via Alembic (render_as_batch=True). Update `ListingResponse` to include `neighborhood: Optional[str]`. Update `GET /listings` to filter `WHERE neighborhood = X` exact match (replacing address.ilike).

**D-04:** Only geocode listings where `lat IS NULL AND address IS NOT NULL`. Yad2 already populates lat/lng from API — do not re-geocode.

**D-05:** Geocoding cascade:
1. Nominatim primary: `GET /search?q=<address>&format=json&countrycodes=il&limit=1` — 1 req/sec
2. Playwright + Bright Data Web Unlocker fallback when Nominatim returns no result

**D-06:** When both providers return no result, leave `lat=NULL`. Retry happens automatically on the next pass.

**D-07:** Neighborhood assignment happens immediately after lat/lng is obtained — same geocoding pass, not a separate step.

**D-08:** Dedup match criteria: `price_a == price_b`, `rooms_a == rooms_b`, `haversine(a,b) < 100m`. Both listings must have non-NULL lat/lng.

**D-09:** Merge: deactivate duplicate (`is_active=False`). First-inserted record is canonical.

**D-10:** Keep canonical record's `is_seen`/`is_favorited` state only. Duplicate's user state is discarded.

**D-11:** `dedup_fingerprint = sha256(f"{price}:{rooms}:{round(lat,4)}:{round(lng,4)}")`. Group by fingerprint; deactivate all but the earliest `id`.

**D-12:** APScheduler chain: `run_yad2_scraper()` → `run_geocoding_pass()` → `run_dedup_pass()`. All three run sequentially.

### Claude's Discretion
- Exact Nominatim User-Agent string (required by ToS — use project name + contact email)
- Whether to use `httpx` or `aiohttp` for Nominatim HTTP call
- Exact Google Maps URL pattern and lat/lng extraction method
- How to structure `backend/app/geocoding.py` (class vs module-level functions)
- Alembic migration naming convention
- Geocoding failure log level

### Deferred Ideas (OUT OF SCOPE)
- Fuzzy text dedup (DEDUP-01)
- Admin dedup review UI (DEDUP-02)
- "Other" neighborhood category
- OR-merge for is_seen/is_favorited across canonical/duplicate pair
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-03 | Cross-source dedup: listings sharing price + rooms + coords within 100m merge into one record | SQLAlchemy async bulk UPDATE, haversine inline, fingerprint sha256 |
| DATA-04 | Geocoding: Hebrew address → lat/lng via Nominatim asynchronously (non-blocking) | Nominatim API verified, httpx async pattern, 1 req/sec enforcement |
| DATA-05 | Neighborhood tagging: Carmel/Downtown/Neve Shanan based on geocoded coordinates | Bounding-box dict lookup, inline math, no new library needed |
</phase_requirements>

---

## Standard Stack

### Core (no new dependencies required)
| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `httpx` | 0.27+ (already installed) | Nominatim HTTP requests | Async-native; already used for Yad2 API calls; consistent with codebase |
| `playwright` | 1.58.0 (already installed) | Google Maps fallback geocoding | Already installed for Yad2 scraper; proxy integration already in `proxy.py` |
| `sqlalchemy` | 2.0.48 (already installed) | Bulk fingerprint + is_active updates | `update().where().values()` with `await session.execute()` |
| `alembic` | 1.16.5 (already installed) | `neighborhood` column migration | `render_as_batch=True` already configured in `env.py` |
| `hashlib` | stdlib | SHA-256 fingerprint generation | No install needed |
| `math` | stdlib | Haversine distance calculation | No install needed |
| `asyncio` | stdlib | 1 req/sec rate limiting (`asyncio.sleep(1)`) | No install needed |

**No new pip dependencies.** The `shapely` package is installed (2.0.7) as an indirect dependency but is not needed — bounding-box logic is four float comparisons.

### Installation
```bash
# No new packages — all dependencies already in requirements.txt
```

### Version Verification
All versions confirmed via direct file inspection of `backend/requirements.txt` (read on 2026-04-02).

---

## Architecture Patterns

### Recommended Project Structure
```
backend/app/
├── geocoding.py          # NEW: geocoding + dedup module (all Phase 5 logic)
├── scheduler.py          # MODIFY: add run_geocoding_job(), run_dedup_job()
├── models/
│   └── listing.py        # MODIFY: add neighborhood column
├── schemas/
│   └── listing.py        # MODIFY: add neighborhood field to ListingResponse
├── routers/
│   └── listings.py       # MODIFY: neighborhood filter → exact match
└── main.py               # MODIFY: register two new APScheduler jobs
backend/alembic/versions/
└── 0002_add_neighborhood.py   # NEW: Alembic migration
```

### Pattern 1: Nominatim Geocoding with Rate Limiting

**What:** Async HTTP GET to Nominatim with a 1-second sleep between requests, custom User-Agent per ToS.
**When to use:** Primary path for every listing where `lat IS NULL AND address IS NOT NULL`.

```python
# Source: https://nominatim.org/release-docs/latest/api/Search/ + ToS
import asyncio
import httpx

NOMINATIM_USER_AGENT = "ApartmentFinder/1.0 (contact@example.com)"

async def _geocode_nominatim(address: str) -> tuple[float, float] | None:
    """Return (lat, lng) or None. Nominatim returns 'lon', not 'lng'."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "countrycodes": "il",
        "limit": 1,
    }
    headers = {"User-Agent": NOMINATIM_USER_AGENT}
    async with httpx.AsyncClient(headers=headers, timeout=10) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        results = resp.json()
    await asyncio.sleep(1)  # ToS: max 1 req/sec
    if not results:
        return None
    # NOTE: Nominatim uses "lon" (not "lng") — values are STRINGS, cast to float
    return float(results[0]["lat"]), float(results[0]["lon"])
```

**Critical:** Nominatim `lat` and `lon` values are JSON strings, not numbers. Always cast with `float()`.

### Pattern 2: Google Maps Fallback via Playwright

**What:** Navigate Playwright browser (with Bright Data proxy) to `google.com/maps/search/?api=1&query=<address>+חיפה`, wait for the URL to contain `@`, then extract lat/lng with a regex.
**When to use:** Only when Nominatim returns no result.

```python
# Source: Google Maps URL format docs + Playwright page.wait_for_url API
import re
from playwright.async_api import async_playwright

async def _geocode_google_maps_fallback(address: str) -> tuple[float, float] | None:
    from app.scrapers.proxy import get_proxy_launch_args
    query = f"{address} חיפה"
    search_url = f"https://www.google.com/maps/search/?api=1&query={query}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, **get_proxy_launch_args())
        try:
            page = await browser.new_page()
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            # Google Maps rewrites the URL to include @lat,lng after redirect
            await page.wait_for_url(re.compile(r"@-?\d+\.\d+,-?\d+\.\d+"), timeout=15000)
            current_url = page.url
            match = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", current_url)
            if match:
                return float(match.group(1)), float(match.group(2))
            return None
        except Exception:
            return None
        finally:
            await browser.close()
```

**Notes on proxy usage:** `get_proxy_launch_args()` returns `{}` when Bright Data env vars are unset (graceful degradation per existing `proxy.py` contract). When proxy is active, target URLs must use `http://` per the comment in `proxy.py` — but Google Maps redirects mean the initial URL can still be `https://`. Use `http://` when Bright Data is enabled:

```python
# When proxy is active, use http:// — proxy handles SSL
protocol = "http" if is_proxy_enabled() else "https"
search_url = f"{protocol}://www.google.com/maps/search/?api=1&query={query}"
```

### Pattern 3: Neighborhood Bounding-Box Assignment

**What:** Pure Python dict lookup — O(n_neighborhoods) comparisons per listing.
**When to use:** Immediately after lat/lng is obtained (D-07).

```python
# Source: locked decision D-01 in CONTEXT.md
NEIGHBORHOODS: dict[str, dict] = {
    "כרמל":       {"lat": (32.78, 32.83), "lng": (34.97, 35.02)},
    "מרכז העיר": {"lat": (32.81, 32.84), "lng": (35.00, 35.03)},
    "נווה שאנן":  {"lat": (32.80, 32.83), "lng": (35.02, 35.05)},
}

def assign_neighborhood(lat: float, lng: float) -> str | None:
    for name, bounds in NEIGHBORHOODS.items():
        if (bounds["lat"][0] <= lat <= bounds["lat"][1] and
                bounds["lng"][0] <= lng <= bounds["lng"][1]):
            return name
    return None  # D-02: NULL for listings outside all bounding boxes
```

### Pattern 4: Haversine Distance (inline, stdlib-only)

**What:** Great-circle distance in meters between two lat/lng points.
**When to use:** Dedup pass to check if two listings are within 100m.

```python
# Source: standard haversine formula, verified with math module (stdlib)
from math import radians, sin, cos, sqrt, atan2

def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6_371_000  # Earth radius in meters
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lng2 - lng1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))
```

**Verified:** `haversine_meters(32.8191, 34.9998, 32.8200, 35.0003)` returns `110.4m` (slightly over 100m — correct for the test case). Same-point returns `0.0m`.

### Pattern 5: Dedup Fingerprint Generation

**What:** SHA-256 of `"{price}:{rooms}:{round(lat,4)}:{round(lng,4)}"`.
**Fits in:** `VARCHAR(64)` — SHA-256 hex digest is exactly 64 characters.

```python
import hashlib

def make_dedup_fingerprint(price: int, rooms: float, lat: float, lng: float) -> str:
    key = f"{price}:{rooms}:{round(lat, 4)}:{round(lng, 4)}"
    return hashlib.sha256(key.encode()).hexdigest()
```

**Verified:** produces 64-character hex string. Fits existing `dedup_fingerprint VARCHAR(64)` column exactly.

### Pattern 6: SQLAlchemy Async Bulk UPDATE

**What:** Update `dedup_fingerprint` for geocoded listings, and deactivate duplicates.
**When to use:** End of geocoding pass (write fingerprint) and dedup pass (write is_active=False).

```python
# Source: https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html
from sqlalchemy import update, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.listing import Listing

# Write fingerprint for a single listing after geocoding
listing.lat = lat
listing.lng = lng
listing.neighborhood = neighborhood
listing.dedup_fingerprint = fingerprint
await session.flush()  # or commit at end of pass

# Bulk deactivate duplicate IDs (all but canonical)
duplicate_ids: list[int] = [...]
stmt = (
    update(Listing)
    .where(Listing.id.in_(duplicate_ids))
    .values(is_active=False)
)
await session.execute(stmt)
await session.commit()
```

**Note on session strategy:** The geocoding pass processes listings one-by-one (rate-limited by Nominatim's 1 req/sec). Flush individual listing updates inside the loop; commit once at the end of the full pass. This avoids holding a long transaction while waiting for HTTP responses.

### Pattern 7: APScheduler Job Chaining

**What:** The simplest chain is to call the geocoding and dedup passes sequentially inside `run_yad2_scrape_job()` rather than as separate APScheduler jobs with triggers.
**Why:** APScheduler 3.x has no built-in job dependency/ordering system. The existing pattern (one job per scraper, registered in `main.py` with interval trigger) already handles scheduling. The geocoding and dedup passes should be called from within the Yad2 job function itself, sharing the same session context.

```python
# In scheduler.py — extend run_yad2_scrape_job to call passes sequentially
async def run_yad2_scrape_job() -> None:
    from app.database import async_session_factory
    from app.scrapers.yad2 import run_yad2_scraper
    from app.geocoding import run_geocoding_pass, run_dedup_pass

    started_at = datetime.now(timezone.utc)
    logger.info("Yad2 scrape job started")
    try:
        async with async_session_factory() as session:
            result = await run_yad2_scraper(session)
            await run_geocoding_pass(session)   # Step 2: geocode NULL-lat listings
            await run_dedup_pass(session)       # Step 3: deactivate fingerprint duplicates
    except Exception as exc:
        ...
```

**Alternative:** Register separate APScheduler jobs with `next_run_time=None` and trigger them manually. This is more complex with no benefit at single-user scale. **Use the sequential-call pattern above.**

### Pattern 8: Alembic Migration for neighborhood Column

**What:** Add `neighborhood VARCHAR(100) NULLABLE` to the listings table.
**Naming convention:** Follows `0001_initial_schema.py` — use `0002_add_neighborhood.py`, revision `"0002"`, `down_revision="0001"`.

```python
# backend/alembic/versions/0002_add_neighborhood.py
"""Add neighborhood column to listings

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    with op.batch_alter_table("listings") as batch_op:
        batch_op.add_column(sa.Column("neighborhood", sa.String(100), nullable=True))

def downgrade() -> None:
    with op.batch_alter_table("listings") as batch_op:
        batch_op.drop_column("neighborhood")
```

**render_as_batch=True is already set** in `backend/alembic/env.py` line 26 — verified by direct file read. SQLite requires batch mode for ALTER TABLE. The migration itself must still use `with op.batch_alter_table(...)` context manager (batch mode is not automatic in the migration body).

### Anti-Patterns to Avoid
- **Using `lng` when reading Nominatim JSON:** Nominatim returns `"lon"` — using `result["lng"]` will raise `KeyError`. Always read `result["lon"]` and then assign to `listing.lng`.
- **Registering geocoding/dedup as separate interval jobs:** They are not independent recurring tasks — they should only run after a scraper run. Separate interval jobs would cause them to run on their own schedule, potentially against empty or stale data.
- **Re-geocoding Yad2 listings:** Yad2 API already provides lat/lng from `address.coords.lat/lon`. The `D-04` rule `lat IS NULL AND address IS NOT NULL` correctly skips these.
- **Committing inside the Nominatim rate-limit sleep:** `asyncio.sleep(1)` does not block the event loop, but committing inside a tight loop per-listing is fine at this scale. Batching commits is an optimization for Phase 5's volume.
- **Using `op.add_column` directly (without batch_alter_table):** Will fail on SQLite with `OperationalError: Cannot add a NOT NULL column with default value NULL`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Hebrew address → coordinates | Custom geocoder | Nominatim (free OSM API) + Playwright fallback | Nominatim handles Hebrew UTF-8, Israel-filtered results, free forever |
| Distance between two coordinates | Custom formula from scratch | Inline haversine (5 lines of stdlib math) | Simple enough to inline; no dependency needed |
| Neighborhood polygon lookup | Shapely spatial index | Simple bounding-box dict (4 float comparisons) | Three rectangles — shapely would be overengineering |
| SHA-256 hashing | Custom hash | stdlib `hashlib.sha256` | Already available, correct length for VARCHAR(64) |
| HTTP rate limiting | Token bucket, semaphore | `asyncio.sleep(1)` between requests | Nominatim's 1 req/sec is per-process; simple sleep is sufficient at single-user scale |

**Key insight:** This phase's "heavy lifting" is orchestration, not algorithms. All the math is stdlib. The complexity is in the Playwright fallback and the SQLAlchemy session management.

---

## Common Pitfalls

### Pitfall 1: Nominatim Returns "lon" Not "lng"
**What goes wrong:** `float(result["lng"])` raises `KeyError` at runtime, geocoding pass crashes silently or with an unhandled exception.
**Why it happens:** Nominatim's JSON spec uses the abbreviation `lon` (standard GIS convention). The Listing model uses `lng` (project convention). The mapping is asymmetric.
**How to avoid:** Always extract as `float(result["lon"])` and assign to `listing.lng`. Add a comment at the extraction point.
**Warning signs:** KeyError in geocoding logs; listings never getting coordinates despite valid Nominatim responses.

### Pitfall 2: Nominatim Values are Strings, Not Numbers
**What goes wrong:** `listing.lat = result["lat"]` stores `"32.8191"` (a string) instead of `32.8191` (float), causing SQLAlchemy type coercion errors or incorrect bounding-box comparisons.
**Why it happens:** Nominatim's JSON encodes lat/lon as JSON strings per their API spec (confirmed in official docs example).
**How to avoid:** Always `float(result["lat"])` and `float(result["lon"])`.
**Warning signs:** Bounding-box comparisons always return False; SQLAlchemy warnings about type mismatch.

### Pitfall 3: Google Maps URL May Not Contain "@" Until Redirect Completes
**What goes wrong:** `page.url` is read immediately after `goto()` and still shows the search URL without coordinates; regex returns no match.
**Why it happens:** Google Maps performs a JavaScript redirect that rewrites the URL to include `@lat,lng,zoom` — this happens after `domcontentloaded` but before the page fully settles.
**How to avoid:** Use `await page.wait_for_url(re.compile(r"@-?\d+\.\d+,-?\d+\.\d+"), timeout=15000)` before reading `page.url`. This blocks until the URL contains coordinates.
**Warning signs:** Regex match returns None even for valid addresses; coordinates come back as None even when the page visually shows the location.

### Pitfall 4: Bright Data Proxy Requires http:// Not https://
**What goes wrong:** Playwright navigates with `https://` while proxy is active, causing SSL certificate errors or proxy rejection.
**Why it happens:** The comment in `backend/app/scrapers/proxy.py` line 10 explicitly states: "Target URLs passed to page.goto() MUST use http:// (not https://) when the proxy is active."
**How to avoid:** Check `is_proxy_enabled()` before constructing the URL. Use `"http://"` prefix when proxy is active, `"https://"` otherwise.
**Warning signs:** Playwright SSL errors when proxy is configured; geocoding fallback always returns None when Bright Data is enabled.

### Pitfall 5: Dedup Pass Must Run After Geocoding (Not Concurrently)
**What goes wrong:** Dedup pass groups by fingerprint — but fingerprints are only populated after geocoding sets lat/lng. Running dedup before geocoding produces no fingerprint matches (all `dedup_fingerprint IS NULL`).
**Why it happens:** D-11 states fingerprint includes `lat`/`lng` — listings without coordinates cannot be fingerprinted.
**How to avoid:** Sequential call: `await run_geocoding_pass(session)` then `await run_dedup_pass(session)` — already specified in D-12. The session flush at the end of the geocoding pass ensures fingerprints are visible to the dedup query.
**Warning signs:** Dedup pass finds 0 duplicates even when the same listing exists from multiple sources.

### Pitfall 6: batch_alter_table Required in Migration Body
**What goes wrong:** `op.add_column("listings", sa.Column(...))` fails with `OperationalError` on SQLite even though `render_as_batch=True` is in `env.py`.
**Why it happens:** `render_as_batch=True` in `env.py` applies to autogenerate-produced migrations. Hand-written migrations must explicitly use `with op.batch_alter_table("listings") as batch_op:` context manager.
**How to avoid:** Always use batch context manager in any hand-written migration that ALTERs the listings table on SQLite.
**Warning signs:** `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) Cannot add a NOT NULL column`.

---

## Code Examples

### Complete Geocoding Pass Skeleton
```python
# Source: patterns from existing yad2.py session usage + Nominatim API docs
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.listing import Listing

async def run_geocoding_pass(session: AsyncSession) -> None:
    """Geocode all listings where lat IS NULL and address IS NOT NULL."""
    stmt = select(Listing).where(
        Listing.lat.is_(None),
        Listing.address.isnot(None),
        Listing.is_active == True,
    )
    result = await session.execute(stmt)
    listings = result.scalars().all()

    for listing in listings:
        coords = await _geocode_nominatim(listing.address)
        if coords is None:
            coords = await _geocode_google_maps_fallback(listing.address)
        if coords is None:
            continue  # D-06: leave lat=NULL, retry next pass
        lat, lng = coords
        listing.lat = lat
        listing.lng = lng
        listing.neighborhood = assign_neighborhood(lat, lng)   # D-07
        listing.dedup_fingerprint = make_dedup_fingerprint(
            listing.price, listing.rooms, lat, lng
        ) if listing.price and listing.rooms else None
        # No commit inside loop — avoid holding transaction during HTTP calls

    await session.commit()
```

### Complete Dedup Pass Skeleton
```python
async def run_dedup_pass(session: AsyncSession) -> None:
    """Deactivate duplicate listings by dedup_fingerprint (D-08 through D-11)."""
    from sqlalchemy import func

    # Find all fingerprints that appear more than once among active listings
    stmt = (
        select(Listing.dedup_fingerprint, func.min(Listing.id).label("canonical_id"))
        .where(
            Listing.dedup_fingerprint.isnot(None),
            Listing.is_active == True,
        )
        .group_by(Listing.dedup_fingerprint)
        .having(func.count(Listing.id) > 1)
    )
    result = await session.execute(stmt)
    duplicates = result.all()

    for fingerprint, canonical_id in duplicates:
        # Deactivate all non-canonical rows with this fingerprint
        deactivate_stmt = (
            update(Listing)
            .where(
                Listing.dedup_fingerprint == fingerprint,
                Listing.id != canonical_id,
                Listing.is_active == True,
            )
            .values(is_active=False)
        )
        await session.execute(deactivate_stmt)

    await session.commit()
```

### Router Neighborhood Filter Change
```python
# BEFORE (listings.py line 53): provisional address text match
filters.append(Listing.address.ilike(f"%{neighborhood}%"))

# AFTER (Phase 5): exact neighborhood column match
filters.append(Listing.neighborhood == neighborhood)
```

### ListingResponse Schema Update
```python
# Add to ListingResponse in schemas/listing.py
neighborhood: Optional[str] = None
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Selenium for browser geocoding | Playwright async | 2023-2024 | Faster, async-native, better proxy support |
| Google Maps JS API (paid) | Nominatim (free OSM) | Always an option | Zero cost, Hebrew tiles, countrycodes filter |
| Celery + Redis for job chains | Inline sequential calls in APScheduler job | Project decision Phase 3 | No broker needed; simpler at single-user scale |

**No deprecations affect Phase 5.**

---

## Open Questions

1. **Nominatim User-Agent contact email**
   - What we know: Nominatim ToS requires a valid User-Agent with application name and contact. The string is Claude's discretion.
   - What's unclear: Whether a placeholder email is acceptable or if a real email is required.
   - Recommendation: Use `"ApartmentFinder/1.0 (shahaf@localhost)"` or the developer's actual email. A non-routable address is likely fine for a personal app — the ToS intent is to allow OSM to contact abusers.

2. **Session commit strategy in geocoding pass**
   - What we know: The geocoding pass may take several minutes (many listings × 1 req/sec Nominatim).
   - What's unclear: Whether to commit after each listing (durable progress) or once at the end (atomic).
   - Recommendation: Commit in batches of 10 listings. If the process crashes mid-pass, already-geocoded listings are saved and the next pass skips them (lat IS NOT NULL). Pure end-of-pass commit risks losing all progress on crash.

3. **Google Maps fallback browser reuse**
   - What we know: Current Playwright usage in yad2.py launches a new browser per-session.
   - What's unclear: Whether to launch one browser for the entire geocoding pass or one per address.
   - Recommendation: Launch one browser per geocoding pass (not per address). Reuse the context across multiple page navigations. This reduces overhead for the (hopefully rare) fallback case.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | All Phase 5 code | verified (requirements.txt) | 3.12 | — |
| httpx | Nominatim HTTP | verified (requirements.txt) | 0.27+ | — |
| playwright | Google Maps fallback | verified (requirements.txt) | 1.58.0 | Skip fallback, leave lat=NULL |
| sqlalchemy | Bulk updates | verified (requirements.txt) | 2.0.48 | — |
| alembic | Migration | verified (requirements.txt) | 1.16.5 | — |
| hashlib | SHA-256 fingerprint | stdlib | — | — |
| math | Haversine | stdlib | — | — |
| asyncio | Rate limiting sleep | stdlib | — | — |
| Bright Data proxy | Google Maps bypass | Optional (env vars) | — | Playwright without proxy (may fail on Google) |
| Nominatim public API | Geocoding primary | Public service | — | Google Maps fallback |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:**
- Bright Data proxy: if env vars unset, `get_proxy_launch_args()` returns `{}` (graceful degradation already implemented in `proxy.py`). Google Maps without a proxy may return bot-detection errors; in that case the geocoding fallback simply returns None and the listing stays at lat=NULL.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio |
| Config file | `backend/pytest.ini` (`asyncio_mode = auto`) |
| Quick run command | `cd backend && python -m pytest tests/test_geocoding.py -x -q` |
| Full suite command | `cd backend && python -m pytest -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-04 | Nominatim returns (lat, lng) for valid Hebrew address | unit | `pytest tests/test_geocoding.py::test_nominatim_success -x` | Wave 0 |
| DATA-04 | Nominatim returns None for empty result | unit | `pytest tests/test_geocoding.py::test_nominatim_no_result -x` | Wave 0 |
| DATA-04 | Google Maps fallback extracts @lat,lng from URL | unit | `pytest tests/test_geocoding.py::test_google_maps_fallback -x` | Wave 0 |
| DATA-04 | Geocoding pass skips listings with lat IS NOT NULL | unit | `pytest tests/test_geocoding.py::test_geocoding_pass_skips_geocoded -x` | Wave 0 |
| DATA-04 | Geocoding pass skips listings with address IS NULL | unit | `pytest tests/test_geocoding.py::test_geocoding_pass_skips_no_address -x` | Wave 0 |
| DATA-05 | assign_neighborhood returns "כרמל" for point inside bounding box | unit | `pytest tests/test_geocoding.py::test_neighborhood_carmel -x` | Wave 0 |
| DATA-05 | assign_neighborhood returns None for point outside all boxes | unit | `pytest tests/test_geocoding.py::test_neighborhood_null -x` | Wave 0 |
| DATA-03 | haversine_meters returns < 100 for two nearby points | unit | `pytest tests/test_geocoding.py::test_haversine_under_100m -x` | Wave 0 |
| DATA-03 | Dedup pass sets is_active=False for duplicate fingerprint | unit | `pytest tests/test_geocoding.py::test_dedup_pass_deactivates_duplicate -x` | Wave 0 |
| DATA-03 | Dedup pass keeps canonical (min id) active | unit | `pytest tests/test_geocoding.py::test_dedup_pass_keeps_canonical -x` | Wave 0 |
| DATA-05 | GET /listings?neighborhood=כרמל returns only neighborhood-tagged listings | integration | `pytest tests/test_api.py::test_neighborhood_filter_exact_match -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_geocoding.py -x -q`
- **Per wave merge:** `cd backend && python -m pytest -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_geocoding.py` — covers all DATA-03, DATA-04, DATA-05 unit tests listed above
- [ ] `tests/test_api.py` — add `test_neighborhood_filter_exact_match` to existing test file

*(Existing `tests/conftest.py` fixtures (`db_session`, `client`) are reusable — no new conftest needed)*

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on Phase 5 |
|-----------|-------------------|
| Python 3.12 runtime | All new code must be Python 3.12 compatible |
| FastAPI + SQLAlchemy 2.0 async | Session pattern: `async with async_session_factory() as session:` with deferred imports inside job functions |
| SQLite (no Postgres) | Alembic migrations MUST use `op.batch_alter_table` for ALTER TABLE |
| APScheduler embedded (no Celery) | Job chaining = sequential `await` calls inside the existing Yad2 job, not separate trigger-based jobs |
| Playwright for browser automation | Use for Google Maps fallback; reuse existing proxy.py infrastructure |
| httpx for static HTTP | Use for Nominatim (no full browser needed) |
| Single user, no concurrency | `asyncio.sleep(1)` rate limiting is sufficient; no token bucket needed |
| Hebrew/RTL throughout | Neighborhood names stored and compared in Hebrew: "כרמל", "מרכז העיר", "נווה שאנן" — no transliteration |
| GSD workflow enforcement | All file edits must be made via `/gsd:execute-phase` |

---

## Sources

### Primary (HIGH confidence)
- Nominatim Search API docs — URL format, `lat`/`lon` field names, JSON string type confirmed: https://nominatim.org/release-docs/latest/api/Search/
- Nominatim JSON Output docs — complete field list with example showing `"lat": "51.5073219"` (string): https://nominatim.org/release-docs/latest/api/Output/
- Nominatim Usage Policy — 1 req/sec limit, User-Agent requirement: https://operations.osmfoundation.org/policies/nominatim/
- SQLAlchemy 2.0 ORM DML docs — `update().where().values()` async pattern: https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html
- Playwright Python `page.wait_for_url` API — regex parameter, async usage: https://playwright.dev/python/docs/api/class-page#page-wait-for-url
- Google Maps URLs — `search/?api=1&query=` format: https://developers.google.com/maps/documentation/urls/get-started
- Direct file reads: `backend/requirements.txt`, `backend/alembic/env.py`, `backend/app/models/listing.py`, `backend/app/scheduler.py`, `backend/app/main.py`, `backend/app/scrapers/proxy.py`, `backend/app/config.py`

### Secondary (MEDIUM confidence)
- Google Maps `@lat,lng` regex pattern (`r"@(-?\d+\.\d+),(-?\d+\.\d+)"`) — verified by manual regex test on a Haifa Maps URL: https://codingtechroom.com/question/extract-latitude-longitude-google-maps-url
- APScheduler 3.x `AsyncIOScheduler` async job execution — does not support built-in job chaining/ordering: https://apscheduler.readthedocs.io/en/3.x/userguide.html

### Tertiary (LOW confidence — flagged)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and in use in the project; verified by direct file reads
- Nominatim API format: HIGH — verified against official docs; `lon` vs `lng` and string type confirmed
- Google Maps URL pattern: MEDIUM — `@lat,lng` pattern is well-documented but Google can change redirect behavior; the `wait_for_url` approach is more robust than a fixed sleep
- APScheduler chaining approach: HIGH — no built-in ordering confirmed in docs; sequential-call pattern is established project precedent (single job, no Celery)
- SQLAlchemy async bulk UPDATE: HIGH — official docs confirm `update().where().values()` with `await session.execute()`
- Haversine inline math: HIGH — stdlib math verified with test calculation
- Alembic migration pattern: HIGH — existing migration file and `env.py` read directly; `render_as_batch=True` confirmed

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (Nominatim API is stable; Google Maps URL format changes infrequently)
