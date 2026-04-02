# Phase 3: REST API + Scheduler - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver: (a) a real `GET /listings` endpoint with filter params (price, rooms, neighborhood, recency, seen, favorited), (b) `PUT /listings/{id}/seen` and `PUT /listings/{id}/favorited` mutation endpoints, (c) an enhanced `GET /health` endpoint showing last-run timestamps and per-source listing counts, and (d) APScheduler embedded in the backend process running the Yad2 scraper automatically every 2 hours with job lock. Phase 3 is done when all four ROADMAP success criteria are met.

</domain>

<decisions>
## Implementation Decisions

### Scheduler Startup
- **D-01:** Fire the first Yad2 scrape **immediately on startup** (not after the first 2-hour interval). Cold-start result: fresh data is available as soon as the backend is up. APScheduler `next_run_time=datetime.now(timezone.utc)` achieves this on the first job registration.

### Health Data Storage
- **D-02:** Track run results in an **in-memory dict** — a module-level `dict[str, ScraperResult]` (or similar) updated after each scheduler run. `GET /health` reads from this dict. Data is lost on process restart (shows "never run" until next run completes). No new DB table or migration needed.

### API Default Visibility
- **D-03:** `GET /listings` with no params returns all **active** listings (`is_active=True`). No default exclusion of `is_seen=True` — the frontend (Phase 4) handles seen visibility on the client side.
- **D-04:** Low-confidence listings (`llm_confidence < threshold`) are **excluded by default** from all `GET /listings` responses. They remain in the DB but are invisible to the frontend unless a future admin endpoint explicitly requests them.

### Neighborhood Filter
- **D-05:** Implement neighborhood filtering in Phase 3 via **address text matching** — filter on `address` column containing כרמל / מרכז העיר / נווה שאנן. This works with current Yad2 data. Phase 5 replaces this with coordinate-based matching once geocoding is added.

### Claude's Discretion
- Query param naming conventions (e.g., `price_max`, `rooms_min`, `is_seen`, `neighborhood`)
- Pagination design (if any — not in success criteria, but may be useful)
- Whether to add a `neighborhood` column to the Listing model or derive from `address` at query time
- Exact APScheduler job config (interval trigger, coalesce setting, misfire grace time)
- In-memory health dict structure and thread-safety approach

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 3 Requirements
- `.planning/REQUIREMENTS.md` — SCHED-01, SCHED-02, SCHED-03 (scheduler requirements for this phase)

### Stack Decisions
- `CLAUDE.md` — APScheduler 3.10+ (embedded scheduler), FastAPI 0.111+, Python 3.12; full stack reference

### Roadmap
- `.planning/ROADMAP.md` — Phase 3 success criteria (4 checkpoints that define done)

### Prior Phase Contracts
- `.planning/phases/02-yad2-scraper-llm-pipeline/02-CONTEXT.md` — D-04: `run_yad2_scraper(db: AsyncSession) -> ScraperResult` is the contract Phase 3 imports
- `backend/app/scrapers/base.py` — `ScraperResult` dataclass (fields: source, listings_found, listings_inserted, listings_skipped, listings_rejected, listings_flagged, errors, success)

### Existing Code
- `backend/app/main.py` — `lifespan` context manager (stubbed) — APScheduler starts/stops here
- `backend/app/routers/listings.py` — Stub router at `/api/listings` — Phase 3 implements it fully
- `backend/app/schemas/listing.py` — `ListingResponse` schema (all fields present)
- `backend/app/config.py` — `Settings` with `llm_confidence_threshold`, `yad2_neighborhoods` list

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/database.py` — Async SQLAlchemy session factory; scheduler job will need to create a session manually (not via FastAPI dependency injection)
- `backend/app/schemas/listing.py` — `ListingResponse` is complete; no new schema fields needed for Phase 3
- `backend/app/config.py` — `Settings.yad2_neighborhoods` list already contains the three neighborhoods for text-match filtering
- `backend/app/scrapers/base.py` — `ScraperResult` provides all fields needed to populate the health response

### Established Patterns
- Async SQLAlchemy with `AsyncSession` — scheduler job must create its own session context (not rely on FastAPI's `Depends(get_db)`)
- `pydantic_settings` for config — `scrape_interval_hours` and any scheduler tunables should be added to `Settings`
- Existing `lifespan` in `main.py` is the correct place to start/stop APScheduler

### Integration Points
- APScheduler job calls `run_yad2_scraper(db)` — the Phase 2 contract
- `GET /health` reads from the in-memory run-result dict (set by the scheduler job, read by the router)
- Phase 4 frontend will call `GET /listings` — the filter contract defined here is the API surface Phase 4 builds against

</code_context>

<specifics>
## Specific Ideas

- Job lock (SCHED-02): APScheduler's `max_instances=1` on the job prevents overlap — do not start a new run if previous is still running.
- Health response shape should include: `{ "status": "ok", "scrapers": { "yad2": { "last_run": "ISO timestamp or null", "listings_inserted": N, "success": bool } } }` — Claude decides exact field names.
- `llm_confidence_threshold` is already in `Settings` (0.7 default) — use it as the filter cutoff in the listings query.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-rest-api-scheduler*
*Context gathered: 2026-04-02*
