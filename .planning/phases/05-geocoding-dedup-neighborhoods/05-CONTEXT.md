# Phase 5: Geocoding + Dedup + Neighborhoods - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver three coordinated data-quality capabilities:
1. **Geocoding** — listings with a Hebrew address and NULL lat/lng get coordinates via Nominatim (primary) → Playwright + Bright Data Web Unlocker scraping Google Maps/Search (fallback)
2. **Neighborhood tagging** — every geocoded listing is assigned to כרמל / מרכז העיר / נווה שאנן (or NULL) based on bounding-box lookup; a new `neighborhood` column stores this in the DB
3. **Cross-source dedup** — after each scraper + geocode pass, listings sharing price + rooms + coordinates within 100m are deduplicated by deactivating the duplicate (is_active=False)

All three run as a chained APScheduler sequence: scrape → geocode → dedup.

</domain>

<decisions>
## Implementation Decisions

### Neighborhood Boundaries
- **D-01:** Neighborhood boundaries are defined as **hand-drawn bounding boxes** hardcoded in a Python dict in `backend/app/geocoding.py`. No OSM dependency, no config complexity.
  ```python
  NEIGHBORHOODS = {
      "כרמל":       {"lat": (32.78, 32.83), "lng": (34.97, 35.02)},
      "מרכז העיר": {"lat": (32.81, 32.84), "lng": (35.00, 35.03)},
      "נווה שאנן":  {"lat": (32.80, 32.83), "lng": (35.02, 35.05)},
  }
  ```
- **D-02:** Listings that fall outside all 3 bounding boxes are **left with neighborhood=NULL**. They appear on the map when no neighborhood filter is active, and are hidden when a specific neighborhood is filtered. No "Other" category, no deactivation.
- **D-03:** Schema change required — add `neighborhood VARCHAR(100) NULLABLE` column to the listings table via Alembic migration (render_as_batch=True for SQLite). Update `ListingResponse` schema to include `neighborhood: Optional[str]`. Update `GET /listings` router to filter `WHERE neighborhood = X` (exact match) when the neighborhood param is provided.

### Geocoding Strategy
- **D-04:** Only geocode listings where **lat IS NULL AND address IS NOT NULL**. Yad2 already populates lat/lng — do not re-geocode those. Facebook posts (Phase 8) and any missed listings will need geocoding.
- **D-05:** Geocoding provider cascade:
  1. **Nominatim** (primary) — `GET /search?q=<address>&format=json&countrycodes=il&limit=1`. Free, no key. Rate-limited to 1 req/sec — add 1s sleep between requests.
  2. **Playwright + Bright Data Web Unlocker** (fallback) — when Nominatim returns no result, launch a Playwright browser session via the existing Bright Data Web Unlocker proxy, navigate to `google.com/maps?q=<address>+חיפה` (or Google Search), and extract lat/lng from the URL or page JSON-LD. Uses the same Playwright + proxy infrastructure already set up in quick task 260402-uad.
- **D-06:** When both Nominatim and Google Maps fallback return no result, leave lat=NULL. The listing will be retried on the next geocoding pass automatically (pass only processes NULL lat records, so it will naturally retry).
- **D-07:** Neighborhood assignment happens immediately after lat/lng is obtained for a listing — no separate pass needed. Same geocoding pass: get coords → assign neighborhood bounding box → write both to DB.

### Cross-Source Deduplication
- **D-08:** Duplicate matching criteria (exact, no tolerance):
  - `price_a == price_b` (exact integer match)
  - `rooms_a == rooms_b` (exact float match)
  - `haversine(a, b) < 100m` (using geocoded coordinates)
  - Both listings must have non-NULL lat/lng (dedup only runs after geocoding pass)
- **D-09:** Merge behavior — **deactivate the duplicate** (set `is_active=False`). The first-inserted record is the canonical listing and remains `is_active=True`. No new schema columns needed (uses existing `is_active` column). The canonical listing appears on the map; the duplicate is filtered out by the existing `WHERE is_active=True` query.
- **D-10:** `is_seen` / `is_favorited` state: **keep the canonical record's state only**. The duplicate's user interactions are ignored. The canonical is the displayed record and holds all user state.
- **D-11:** The existing `dedup_fingerprint` column stores a hash of the matching criteria for a listing. Format: `sha256(f"{price}:{rooms}:{round(lat,4)}:{round(lng,4)}")`. During the dedup pass, listings are grouped by fingerprint and all but the first-inserted are deactivated.

### Scheduler Integration
- **D-12:** APScheduler chain after each scraper run:
  1. `run_yad2_scraper()` — existing job
  2. `run_geocoding_pass()` — new: geocodes NULL-lat listings, assigns neighborhoods
  3. `run_dedup_pass()` — new: deactivates duplicate listings by fingerprint
  All three run synchronously in the APScheduler thread pool. Geocoding pass may take minutes (Playwright fallback); this is acceptable since the scheduler is not on the critical path for user requests.

### Claude's Discretion
- Exact Nominatim User-Agent string (required by Nominatim ToS — use project name + contact email)
- Whether to use `httpx` or `aiohttp` for the Nominatim HTTP call
- Exact Google Maps URL pattern to navigate and method to extract lat/lng (URL params vs JSON-LD vs page source parsing)
- How to structure `backend/app/geocoding.py` (class vs module-level functions)
- Alembic migration naming convention (follows existing Phase 1 pattern)
- Whether to log geocoding failures and at what level (INFO vs WARNING)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 5 Requirements
- `.planning/REQUIREMENTS.md` — DATA-03, DATA-04, DATA-05 (cross-source dedup, geocoding, neighborhood tagging)

### Existing Schema & Code
- `backend/app/models/listing.py` — Listing model: existing `lat`, `lng`, `dedup_fingerprint`, `is_active` columns; `dedup_fingerprint` is VARCHAR(64) nullable, currently unpopulated
- `backend/app/routers/listings.py` — `GET /listings` endpoint: current neighborhood filter uses `address.ilike` — Phase 5 changes this to `WHERE neighborhood = X` exact match
- `backend/app/scheduler.py` — APScheduler setup; Phase 5 adds geocoding and dedup jobs to the chain

### Bright Data Web Unlocker Proxy (Geocoding Fallback)
- `.planning/quick/260402-uad-integrate-bright-data-web-unlocker-proxy/` — Proxy setup implemented in quick task 260402-uad; contains integration pattern for Playwright + Web Unlocker

### Roadmap
- `.planning/ROADMAP.md` — Phase 5 success criteria (3 checkpoints: geocoding runs async, neighborhood filter works by coords, Yad2+Madlan duplicate appears as single pin)

### Stack
- `CLAUDE.md` — Python 3.12 / FastAPI / SQLite / APScheduler / Playwright / Alembic render_as_batch=True

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/models/listing.py` — `dedup_fingerprint VARCHAR(64)` already exists and is nullable; Phase 5 populates it with `sha256(price:rooms:lat:lng)`. `lat`, `lng` columns already exist.
- `backend/app/scheduler.py` — APScheduler already embedded in FastAPI lifespan; Phase 5 adds 2 new job functions to the existing chain
- `backend/app/scrapers/` — Playwright browser setup and Bright Data Web Unlocker proxy pattern already implemented (quick task 260402-uad); reuse for Google Maps fallback geocoding
- `backend/app/database.py` — `get_db` async session pattern; geocoding and dedup passes will use the same session factory

### Established Patterns
- Alembic migrations use `render_as_batch=True` in `env.py` for SQLite ALTER TABLE compatibility (Phase 1 decision)
- APScheduler jobs use deferred imports inside the job function to avoid circular dependencies (Phase 3 decision)
- Yad2 scraper already populates `lat`, `lng` from the Yad2 API response — geocoding pass must skip those

### Integration Points
- `backend/app/routers/listings.py:51` — neighborhood filter currently does `address.ilike` — Phase 5 changes this to `Listing.neighborhood == neighborhood` after the column is added
- `backend/app/schemas/listing.py` — `ListingResponse` needs `neighborhood: Optional[str] = None` added
- Frontend neighborhood toggle in `MapView` — already sends `neighborhood` param to `GET /listings`; works correctly once the DB column is populated

</code_context>

<specifics>
## Specific Ideas

- User specifically wants the Google Maps geocoding fallback to use **Playwright + Bright Data Web Unlocker** (not a paid Google Maps API key) — same browser scraping infrastructure used in Phase 2/quick tasks. Navigate to `google.com/maps?q=<address>+חיפה` and extract lat/lng from the URL (Google Maps encodes `@lat,lng` in the URL after navigation) or from page structured data.
- Neighborhood bounding boxes in the context file are approximate — downstream agents should treat them as starting values and refine if the geocoded test listings fall outside expected neighborhoods.

</specifics>

<deferred>
## Deferred Ideas

- **Fuzzy text dedup** (DEDUP-01 in v2 requirements) — fuzzy matching on listing description text to catch duplicates with slightly different addresses. This is v2 scope, not Phase 5.
- **Admin dedup review view** (DEDUP-02) — UI to review merged/duplicate pairs. Out of scope for Phase 5.
- **"Other" neighborhood category** — surfacing unassigned listings in a 4th filter toggle. Deferred — not needed for current Haifa search scope.
- **OR-merge for is_seen/is_favorited** — promoting user interactions from duplicate to canonical. Not needed for Phase 5; canonical's state is sufficient.

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 05-geocoding-dedup-neighborhoods*
*Context gathered: 2026-04-02*
