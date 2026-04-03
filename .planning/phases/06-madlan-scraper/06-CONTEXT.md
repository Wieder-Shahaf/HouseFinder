# Phase 6: Madlan Scraper - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a Madlan scraper that fetches Haifa rental listings filtered to target neighborhoods and price ≤ 4,500 ₪, runs them through the existing LLM verification/normalization pipeline, and integrates into APScheduler as an independent job alongside Yad2 — with no disruption to the existing Yad2 pipeline. Madlan appears in `GET /health` with its own last-run timestamp and listing count.

</domain>

<decisions>
## Implementation Decisions

### Scraping Approach
- **D-01:** **Playwright-first — skip httpx API discovery.** Given ROADMAP's explicit low-confidence flag on Madlan's API/GraphQL shape, do not attempt a direct httpx API call. Go straight to Playwright+stealth browser automation. The httpx discovery path risks being a dead-end (complex auth, unknown GraphQL schema) and is not worth the investment for a second structured source.
- **D-02:** Playwright setup mirrors Yad2 exactly: `playwright-stealth` + optional Bright Data Web Unlocker proxy via `proxy.py` (`get_proxy_launch_args`, `is_proxy_enabled`). Reuse all existing proxy infrastructure.

### Scheduler Integration
- **D-03:** Madlan runs as a **separate independent APScheduler job** (`run_madlan_scrape_job()`), not chained inside the existing `run_yad2_scrape_job()`. Each job runs its own geocode+dedup pass after scraping:
  - `run_yad2_scrape_job()` → yad2 scrape → geocode → dedup
  - `run_madlan_scrape_job()` → madlan scrape → geocode → dedup
  Both jobs run on the same cron interval, in parallel. A Madlan hang or crash does not delay Yad2's geocode/dedup chain.
- **D-04:** Both scrapers use the **same `scrape_interval_hours` config knob** (default: 2h). No separate `madlan_scrape_interval_hours` setting — one config controls both.
- **D-05:** Madlan gets its own entry in the `_health` dict in `scheduler.py` (`"madlan": None`), tracking the same fields as Yad2 (`last_run`, `listings_found`, `listings_inserted`, `listings_rejected`, `listings_flagged`, `success`, `errors`).

### Scraper Contract
- **D-06:** Follow the established Phase 2 contract: `async def run_madlan_scraper(db: AsyncSession) -> ScraperResult`. Lives in `backend/app/scrapers/madlan.py`. Importable by `run_madlan_scrape_job()` via deferred import (per Phase 3 APScheduler pattern, D-12 from Phase 5). Manual invocation: `python -m scrapers.madlan`.
- **D-07:** Source badge: `"מדלן"` (per ROADMAP success criterion). `source` column value: `"madlan"` (lowercase, consistent with `"yad2"`).

### Claude's Discretion
- Exact Madlan URL(s) to navigate and method to extract listing data (researcher discovers at build time via network inspection)
- Whether to use Playwright's `page.goto()` + DOM parsing or intercept XHR/fetch calls during page load
- Madlan's pagination approach (infinite scroll vs page params vs GraphQL cursor)
- Whether neighborhood filtering is possible at the URL/request level or must be post-scrape only
- Exact `source_id` equivalent in Madlan's listing data (researcher identifies stable listing identifier)
- LLM prompt adjustments for Madlan's listing format (if different from Yad2)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 6 Requirements
- `.planning/REQUIREMENTS.md` — MADL-01, MADL-02, MADL-03

### Existing Scraper Pattern (MUST READ — implement Madlan to match)
- `backend/app/scrapers/yad2.py` — Full Yad2 scraper: Playwright fallback pattern, LLM pipeline integration, `ScraperResult` usage, deferred imports
- `backend/app/scrapers/base.py` — `ScraperResult` dataclass
- `backend/app/scrapers/proxy.py` — `get_proxy_launch_args()`, `is_proxy_enabled()` — reuse as-is

### Scheduler Integration
- `backend/app/scheduler.py` — `run_yad2_scrape_job()`, `_health` dict, deferred import pattern; Phase 6 adds `run_madlan_scrape_job()` and `"madlan"` key to `_health`

### Config & Settings
- `backend/app/config.py` — `Settings` class; add any Madlan-specific config vars here (e.g., Madlan base URL if needed)

### Roadmap & State
- `.planning/ROADMAP.md` — Phase 6 success criteria (3 checkpoints), research flag on Madlan API shape
- `.planning/STATE.md` — Blocker note: "Madlan API/GraphQL shape is low-confidence and requires network inspection at build time"

### Prior Phase Context
- `.planning/phases/02-yad2-scraper-llm-pipeline/02-CONTEXT.md` — LLM pipeline decisions (D-01 through D-04): confidence threshold 0.7, `asyncio.gather()` batch LLM calls, scraper invocation contract
- `.planning/phases/05-geocoding-dedup-neighborhoods/05-CONTEXT.md` — Geocode/dedup chain (D-12): geocoding pass runs after scraper, dedup pass runs after geocoding

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/scrapers/base.py` — `ScraperResult` dataclass: reuse as-is, no changes needed
- `backend/app/scrapers/proxy.py` — Bright Data Web Unlocker proxy helpers: reuse as-is
- `backend/app/scrapers/yad2.py` — Playwright fallback block (~100 lines): template for Madlan's Playwright scraper
- `backend/app/llm/verifier.py` — `batch_verify_listings()`, `merge_llm_fields()`: reuse as-is, same LLM pipeline
- `backend/app/geocoding.py` — `run_geocoding_pass()`, `run_dedup_pass()`: called by both jobs, no changes needed
- `backend/app/database.py` — `async_session_factory`: same session pattern for Madlan's job

### Established Patterns
- Deferred imports inside APScheduler job functions to avoid circular dependencies (Phase 3 decision)
- `asyncio.gather()` for parallel LLM batch calls after scrape (Phase 2 decision D-03)
- `sqlite_insert(...).on_conflict_do_nothing()` for same-source dedup at DB level (existing constraint on `source` + `source_id`)
- `pydantic_settings` for config — add Madlan-specific vars to `Settings`, not hardcoded

### Integration Points
- `backend/app/scheduler.py` — Add `run_madlan_scrape_job()` function + `"madlan": None` to `_health` dict + register job in lifespan startup
- `backend/app/routers/health.py` — `GET /health` already returns `_health` dict; Madlan appears automatically once added to `_health`
- `backend/app/models/listing.py` — Listing model is complete; Madlan writes to same table with `source="madlan"`, `source_badge="מדלן"`

</code_context>

<specifics>
## Specific Ideas

- ROADMAP research flag: "Madlan's API/GraphQL shape is low-confidence and must be discovered via network inspection at build time." The plan should include a discovery task (inspect Madlan network tab, identify listing data source) as the first explicit step before writing scraper code.
- Source badge "מדלן" is explicitly required by the Phase 6 success criterion in ROADMAP.md.
- Madlan failure must be fully isolated from Yad2 (MADL-03) — the separate job architecture handles this structurally. The Madlan job should also have a try/except at the top level mirroring `run_yad2_scrape_job()`.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 06-madlan-scraper*
*Context gathered: 2026-04-03*
