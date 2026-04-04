---
phase: "08"
name: facebook-scrapers
status: discussed
discussed: "2026-04-04"
---

# Phase 8: Facebook Scrapers — Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Facebook Groups and Marketplace listings flow into the pipeline as an isolated, best-effort source — with session health monitoring that alerts the user when re-authentication is needed. Both scrapers use a saved Playwright session, run through the existing LLM verification pipeline, and integrate into APScheduler as independent jobs alongside Yad2 and Madlan. A failure in either Facebook scraper does not block other scrapers.

</domain>

<decisions>
## Implementation Decisions

### Facebook Groups List Configuration
- **D-01:** Groups are configured via a user-editable **JSON file at `/data/facebook_groups.json`**. Consistent with `push_subscription.json` storage pattern from Phase 7. No rebuild needed to update the list.
- **D-02:** File format: `[{"url": "https://www.facebook.com/groups/...", "name": "שכירות חיפה"}]` — URL + Hebrew display name per group. Name used in health logs and as the group label on listings from that group.
- **D-03:** If the file is **missing or empty**, the Facebook Groups scraper **skips and logs a warning** — returns `ScraperResult(source="facebook_groups", success=True)` with 0 counts. Graceful degradation; no error propagation.

### LLM Verification Pipeline
- **D-04:** Both Facebook Groups posts (raw unstructured text) and Facebook Marketplace listings (semi-structured) go through the **same `batch_verify_listings()` pipeline** as Yad2 and Madlan. The LLM already handles messy Hebrew text and rejects irrelevant posts. Researcher/planner may adjust prompt wording for Facebook format but no new code path.
- **D-05:** Confidence threshold and rejection behavior: same as existing pipeline (flagged in DB, not deleted; excluded from map view below threshold).

### Session Health Alert
- **D-06:** Session health check runs **before each Facebook scrape** (both Groups and Marketplace). Detection: login redirect or absence of authenticated DOM element after navigation.
- **D-07:** On session expiry: **Web Push notification fires** (active channel from Phase 7). WhatsApp stub exists but remains inactive. Notification content in Hebrew, brief:
  - Title: `"פייסבוק דורש התחברות מחדש"`
  - Body: `"לגתי לדף הכניסה, סריקת קבוצות דולגה"`
- **D-08:** Session expiry is also **surfaced in `GET /health`** as a `facebook_session_valid` boolean field. Consistent with existing health tracking. Both signals (push + health endpoint) are provided.
- **D-09:** On session expiry, the scrape is **skipped cleanly** — returns `ScraperResult(success=True)` with a note in errors list. Does not propagate as a failure to the scheduler.

### Scheduler Integration
- **D-10:** **Two separate independent APScheduler jobs**: `run_facebook_groups_scrape_job()` and `run_facebook_marketplace_scrape_job()`. Consistent with Phase 6 pattern (separate job per source). A Marketplace hang or crash does not block Groups, and vice versa.
- **D-11:** Both Facebook jobs use the **same `scrape_interval_hours` config knob** as Yad2 and Madlan. No separate Facebook interval setting — one config controls all sources.
- **D-12:** Each job gets its own entry in the `_health` dict in `scheduler.py`: `"facebook_groups"` and `"facebook_marketplace"`, tracking the same fields as Yad2/Madlan (`last_run`, `listings_found`, `listings_inserted`, `listings_rejected`, `listings_flagged`, `success`, `errors`). Plus a shared `facebook_session_valid` field.

### Scraper Contract
- **D-13:** Follow established Phase 2/6 contract: `async def run_facebook_groups_scraper(db: AsyncSession) -> ScraperResult` and `async def run_facebook_marketplace_scraper(db: AsyncSession) -> ScraperResult`. Live in `backend/app/scrapers/facebook_groups.py` and `backend/app/scrapers/facebook_marketplace.py`.
- **D-14:** Session storage: **`/data/facebook_session.json`** — Playwright storage state file. Loaded by both scrapers at runtime. Generated once via a manual login script (to be documented). Path configurable via `FACEBOOK_SESSION_PATH` env var, defaulting to `/data/facebook_session.json`.
- **D-15:** Source badge values: `"facebook_groups"` and `"facebook_marketplace"` (lowercase, consistent with `"yad2"` and `"madlan"`).

### Claude's Discretion
- Exact Facebook Groups DOM structure for extracting post text, poster name/link, post date, and post URL (researcher discovers via browser DevTools + Playwright inspection at build time)
- Whether to intercept XHR/GraphQL calls or parse rendered DOM for Groups posts
- Exact Facebook Marketplace URL structure and filters for Haifa rentals
- `playwright-stealth` configuration and fingerprint masking approach
- `source_id` equivalent for Facebook posts (stable unique identifier per post — researcher identifies)
- LLM prompt wording adjustments for Facebook post format vs Yad2/Madlan listing format
- Whether to run both scrapers with `headless=False` + Xvfb or headless with stealth (researcher evaluates detection risk)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 8 Requirements
- `.planning/REQUIREMENTS.md` — FBGR-01, FBGR-02, FBGR-03, FBGR-04, FBGR-05, FBMP-01, FBMP-02, FBMP-03, FBMP-04

### Existing Scraper Pattern (MUST READ — implement Facebook scrapers to match)
- `backend/app/scrapers/yad2.py` — Playwright fallback pattern, LLM pipeline integration, `ScraperResult` usage, deferred imports
- `backend/app/scrapers/madlan.py` — Second scraper implementation; established independent job pattern
- `backend/app/scrapers/base.py` — `ScraperResult` dataclass
- `backend/app/scrapers/proxy.py` — `get_proxy_launch_args()`, `is_proxy_enabled()` — reuse as-is

### Scheduler Integration
- `backend/app/scheduler.py` — `run_yad2_scrape_job()`, `run_madlan_scrape_job()`, `_health` dict, deferred import pattern; Phase 8 adds `run_facebook_groups_scrape_job()`, `run_facebook_marketplace_scrape_job()`, and `"facebook_groups"` / `"facebook_marketplace"` keys to `_health`

### Config & Notification
- `backend/app/config.py` — `Settings` class; add `facebook_session_path: str = "/data/facebook_session.json"`
- `backend/app/notifier.py` — Web Push send function from Phase 7; reuse for session-expiry alert

### Facebook Scraping (Research flag from ROADMAP)
- ROADMAP.md Phase 8 note: "Facebook DOM structure, group access policies, and stealth effectiveness evolve continuously. Run a targeted research pass immediately before implementation. Ensure the scraper Facebook account has Haifa set as home city and the server is on an Israeli IP before any testing."

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/scrapers/base.py` → `ScraperResult` — use unchanged for both Facebook scrapers
- `backend/app/scrapers/proxy.py` → `get_proxy_launch_args()`, `is_proxy_enabled()` — reuse as-is for Playwright launch
- `backend/app/llm/verifier.py` → `batch_verify_listings()`, `merge_llm_fields()` — feed Facebook post text through as-is
- `backend/app/notifier.py` → Web Push send function — reuse for session-expiry alert
- `backend/app/scheduler.py` → `_health` dict pattern, deferred import pattern, `run_notification_job()` call — replicate for Facebook jobs

### Established Patterns
- Separate independent APScheduler job per scraper source (Phase 6, D-03)
- One `scrape_interval_hours` config knob for all scrapers (Phase 6, D-04)
- Source badge: lowercase string constant (`"yad2"`, `"madlan"`) — Facebook follows same convention
- Graceful degradation: scraper failure returns `ScraperResult(success=False)` with errors list; does not raise

### Integration Points
- `scheduler.py` — add two new job functions + two new `_health` entries + `facebook_session_valid` field
- `config.py` — add `facebook_session_path` setting
- `GET /health` router — expose `facebook_session_valid` in response
- `/data/` volume — `facebook_groups.json` (group list) and `facebook_session.json` (Playwright state)

</code_context>

<deferred>
## Deferred Ideas

None from this discussion.

</deferred>
