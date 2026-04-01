# Phase 2: Yad2 Scraper + LLM Pipeline - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver the first real data flow: a Yad2 scraper that fetches Haifa rental listings filtered to target neighborhoods and price ≤ 4,500 ₪, plus an LLM verification/normalization pipeline that rejects invalid posts, extracts structured fields, assigns confidence scores, and writes verified listings to the database. Phase 2 is done when running the scraper manually produces real listings in the DB.

</domain>

<decisions>
## Implementation Decisions

### Yad2 Scraping Approach
- **D-01:** Try the Yad2 internal XHR API first using `httpx` (no browser). If the endpoint requires auth, returns incomplete data, or is blocked — fall back to Playwright+stealth. The ROADMAP research flag (verify API via DevTools before coding) applies here: the plan should include a research step before writing the scraper.

### LLM Confidence Threshold
- **D-02:** Default threshold = **0.7**. Listings with `llm_confidence < 0.7` are flagged in the database (`llm_confidence` column) and excluded from the map view — but not deleted. Threshold must be configurable via `settings` (add `llm_confidence_threshold: float = 0.7` to `Settings`).

### LLM Call Placement
- **D-03:** LLM verification runs **after the full scrape batch**, not per-listing during the scrape. Implementation: `asyncio.gather()` over all scraped listings — parallel LLM calls, non-blocking from the scraper's perspective. This fulfills LLM-05 ("does not block the scraper pipeline") without adding background task infrastructure that belongs in Phase 3.

### Scraper Invocation Contract
- **D-04:** Core scraper logic lives in `async def run_yad2_scraper(db: AsyncSession) -> ScraperResult`. This function is importable by APScheduler in Phase 3 without modification. A `__main__` block wraps it for manual invocation: `python -m scrapers.yad2`. No FastAPI endpoint needed in Phase 2 — the scheduler in Phase 3 imports and calls the function directly.

### Claude's Discretion
- Directory layout for scraper modules (e.g., `backend/app/scrapers/` vs `backend/scrapers/`)
- LLM prompt design for Hebrew listing verification/extraction
- `ScraperResult` return type shape (listings written, listings rejected, errors)
- Whether to log rejected listings to a separate table or just skip them
- Exact httpx request headers to mimic a browser for the Yad2 API call

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 2 Requirements
- `.planning/REQUIREMENTS.md` — YAD2-01, YAD2-02, YAD2-03, YAD2-04, LLM-01, LLM-02, LLM-03, LLM-04, LLM-05, LLM-06 (all Phase 2 requirement IDs)

### Stack and Scraping Guidance
- `CLAUDE.md` — Yad2 scraping section: XHR API approach (httpx first, Crawl4AI fallback), Playwright+stealth guidance, exact library versions; LLM section: Claude Haiku default (LLM-06); Facebook scraping NOT in scope for this phase

### Data Model
- `backend/app/models/listing.py` — Full Listing model with all columns scrapers write to (`source`, `source_id`, `raw_data`, `llm_confidence`, `title`, `price`, `rooms`, `size_sqm`, `address`, `contact_info`, `post_date`, `url`, `source_badge`)
- `backend/app/config.py` — Settings class with `llm_api_key` already present; add `llm_confidence_threshold` here

### Phase Context
- `.planning/ROADMAP.md` — Phase 2 success criteria (5 checkpoints), research flag on Yad2 API endpoint
- `.planning/phases/01-foundation/01-CONTEXT.md` — Phase 1 decisions (DB schema choices D-01 through D-05, async SQLAlchemy pattern)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/database.py` — Async SQLAlchemy session factory; scraper will use the same `get_db()` pattern
- `backend/app/models/listing.py` — Listing model is complete; scraper writes directly to this table
- `backend/app/config.py` — Settings via `pydantic_settings`; add `llm_confidence_threshold` and any Yad2-specific config here

### Established Patterns
- Async SQLAlchemy with `AsyncSession` — all DB operations must be awaited
- `pydantic_settings` for config — add new env vars to `Settings`, not hardcoded
- Existing `UniqueConstraint("source", "source_id")` handles same-source dedup at DB level; scraper can use INSERT OR IGNORE / `on_conflict_do_nothing`

### Integration Points
- Phase 3 (APScheduler) will import `run_yad2_scraper` — the function signature `async def run_yad2_scraper(db: AsyncSession)` is the contract
- `raw_data` column stores the scraped payload pre-LLM (JSON string); `llm_confidence` stores the score post-LLM

</code_context>

<specifics>
## Specific Ideas

- ROADMAP research flag: "Yad2 internal API endpoint URL and parameters must be verified via browser DevTools at build time — training data may be stale." The plan should include this as an explicit step.
- LLM model: Claude Haiku (claude-haiku-4-5) per LLM-06 — cost-efficient at volume. Model ID configurable via `llm_api_key` and a `llm_model` setting.
- Filters: Haifa city + neighborhoods (כרמל, מרכז העיר, נווה שאנן), price ≤ 4,500 ₪ — applied at the API/scraper query level, not post-scrape.
- LLM rejection categories (LLM-01): "looking for apartment" posts (מחפש דירה), sale listings (מכירה), spam, non-rental content.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-yad2-scraper-llm-pipeline*
*Context gathered: 2026-04-02*
