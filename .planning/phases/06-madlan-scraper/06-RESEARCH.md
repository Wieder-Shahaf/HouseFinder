# Phase 6: Madlan Scraper - Research

**Researched:** 2026-04-03
**Domain:** Web scraping (Playwright + stealth), Israeli real estate, FastAPI/APScheduler integration
**Confidence:** MEDIUM (implementation patterns HIGH, Madlan-specific API shape requires runtime discovery)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Playwright-first — skip httpx API discovery. Do not attempt a direct httpx API call to Madlan. Go straight to Playwright+stealth browser automation.
- **D-02:** Playwright setup mirrors Yad2 exactly: `playwright-stealth` + optional Bright Data Web Unlocker proxy via `proxy.py` (`get_proxy_launch_args`, `is_proxy_enabled`). Reuse all existing proxy infrastructure.
- **D-03:** Madlan runs as a separate independent APScheduler job (`run_madlan_scrape_job()`), not chained inside the existing `run_yad2_scrape_job()`. Each job runs its own geocode+dedup pass after scraping. Both jobs run on the same cron interval, in parallel.
- **D-04:** Both scrapers use the same `scrape_interval_hours` config knob (default: 2h). No separate `madlan_scrape_interval_hours` setting.
- **D-05:** Madlan gets its own entry in the `_health` dict in `scheduler.py` (`"madlan": None`), tracking the same fields as Yad2 (`last_run`, `listings_found`, `listings_inserted`, `listings_rejected`, `listings_flagged`, `success`, `errors`).
- **D-06:** Follow the established Phase 2 contract: `async def run_madlan_scraper(db: AsyncSession) -> ScraperResult`. Lives in `backend/app/scrapers/madlan.py`. Manual invocation: `python -m scrapers.madlan`.
- **D-07:** Source badge: `"מדלן"`. `source` column value: `"madlan"`.

### Claude's Discretion
- Exact Madlan URL(s) to navigate and method to extract listing data (discovered at build time via network inspection)
- Whether to use Playwright's `page.goto()` + DOM parsing or intercept XHR/fetch calls during page load
- Madlan's pagination approach (infinite scroll vs page params vs GraphQL cursor)
- Whether neighborhood filtering is possible at the URL/request level or must be post-scrape only
- Exact `source_id` equivalent in Madlan's listing data (identify stable listing identifier)
- LLM prompt adjustments for Madlan's listing format (if different from Yad2)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MADL-01 | Scraper fetches active rental listings in Haifa filtered by neighborhoods and price ≤ 4,500 ₪ | Playwright navigation to `madlan.co.il/rent` with Haifa + price URL params; post-scrape neighborhood filter mirrors yad2 pattern |
| MADL-02 | Scraper extracts same fields as Yad2 (title, price, rooms, size, address, contact, date, URL) | DOM parsing after page load OR XHR interception; `parse_listing()` mirrors yad2's function; LLM fills gaps |
| MADL-03 | Scraper runs via Playwright with stealth; Madlan failure is isolated | Playwright persistent context + playwright-stealth 2.x; top-level try/except in `run_madlan_scrape_job()` mirrors Yad2 job exactly |
</phase_requirements>

---

## Summary

Phase 6 adds a second structured scraper for Madlan (מדלן), Israel's primary real estate portal alongside Yad2. Because Madlan's internal API shape is explicitly flagged as LOW confidence in the project roadmap, the plan takes a Playwright-first approach — no httpx API discovery attempt. The scraper must mirror the Yad2 scraper structure almost exactly, reusing all proxy/stealth/LLM pipeline infrastructure.

The critical unknown — Madlan's exact data format — cannot be resolved programmatically. The plan must include a mandatory DevTools discovery task as Wave 0 work: navigate to `madlan.co.il/rent`, filter for Haifa, and inspect the Network tab to determine whether listing data arrives via embedded JSON (like Yad2's `__NEXT_DATA__`), XHR/fetch API calls, or GraphQL. The outcome of that discovery determines which of two Playwright extraction strategies to implement.

The integration work (scheduler, config, health endpoint, tests) is entirely deterministic — it is a near-exact copy of the Yad2 integration with `"madlan"` substituted throughout. The scraper file itself is the only part with runtime-dependent discovery.

**Primary recommendation:** Structure the phase as three waves — (1) discovery task, (2) scraper core, (3) scheduler integration + tests. The discovery task must produce a written finding before any scraper code is written.

---

## Standard Stack

### Core (all pre-existing — no new installs required)
| Library | Version (verified) | Purpose | Why |
|---------|-------------------|---------|-----|
| playwright (Python) | 1.58.0 (installed) | Browser automation | Confirmed installed; same version used for Yad2 |
| playwright-stealth | 2.0.2 (installed) | Stealth fingerprint masking | `Stealth().apply_stealth_async(page)` — 2.x API already in use |
| SQLAlchemy | (existing) | Async ORM + `sqlite_insert` | `on_conflict_do_nothing` for dedup is already used |
| pydantic-settings | (existing) | Config via `.env` | Madlan-specific settings added to existing `Settings` class |
| APScheduler | (existing) | Periodic job | New job function registered in `main.py` lifespan |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| BeautifulSoup4 | (existing) | HTML fallback parsing | Only if neither `__NEXT_DATA__` nor XHR interception yields data |
| httpx | (existing) | HTTP client | NOT used per D-01; here for reference only |

**No new dependencies are required for this phase.**

**Version verification:** All packages verified against locally installed environment. Playwright 1.58.0, playwright-stealth 2.0.2, pytest 8.4.2 all confirmed installed.

---

## Architecture Patterns

### Recommended Project Structure

No new directories needed. One new file + modifications to existing files:

```
backend/app/scrapers/
├── base.py          # ScraperResult — no changes
├── proxy.py         # Proxy helpers — no changes
├── yad2.py          # Yad2 scraper — no changes
└── madlan.py        # NEW — Madlan scraper (mirrors yad2.py structure)

backend/app/
├── config.py        # ADD: madlan_base_url setting
├── scheduler.py     # ADD: run_madlan_scrape_job() + "madlan" key in _health
└── main.py          # ADD: register run_madlan_scrape_job in lifespan

backend/tests/
└── test_madlan_scraper.py  # NEW — mirrors test_yad2_scraper.py structure
```

### Pattern 1: Playwright Persistent Context (mirrors Yad2 exactly)

The Madlan scraper uses an identical Playwright setup to Yad2. The only difference is the profile directory name and target URL.

```python
# Source: backend/app/scrapers/yad2.py (existing, proven pattern)
user_data_dir = os.path.expanduser("~/.madlan-browser-profile")  # separate from yad2 profile
os.makedirs(user_data_dir, exist_ok=True)
singleton_lock = os.path.join(user_data_dir, "SingletonLock")
if os.path.exists(singleton_lock):
    os.remove(singleton_lock)

async with async_playwright() as p:
    context = await p.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        headless=True,
        locale="he-IL",
        viewport={"width": 1280, "height": 800},
        extra_http_headers={"Accept-Language": "he-IL,he;q=0.9"},
        **get_proxy_launch_args(),
    )
    page = await context.new_page()
    await Stealth().apply_stealth_async(page)
    # URL and extraction strategy determined by DevTools discovery task
```

### Pattern 2: XHR Interception Strategy (preferred if API endpoint found)

If the DevTools discovery task reveals that listing data loads via a distinct XHR/fetch call (REST or GraphQL), intercept it during page load instead of parsing HTML. This yields cleaner structured data.

```python
# Source: https://playwright.dev/python/docs/network
captured_responses: list[dict] = []

async def handle_response(response):
    if "api" in response.url and "rent" in response.url:
        try:
            captured_responses.append(await response.json())
        except Exception:
            pass

page.on("response", handle_response)
await page.goto(url, wait_until="networkidle", timeout=60000)
# captured_responses now contains API payloads
```

### Pattern 3: __NEXT_DATA__ Extraction Strategy (fallback if Madlan uses Next.js)

Madlan may be a Next.js app (likely, given Israeli tech stack trends). If so, the same `__NEXT_DATA__` pattern used for Yad2 may apply.

```python
# Source: backend/app/scrapers/yad2.py — _parse_html_listings()
import re, json

nextdata_match = re.search(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    html, re.DOTALL,
)
if nextdata_match:
    data = json.loads(nextdata_match.group(1))
    # Navigate data['props']['pageProps'] to find listings array
    # Structure will differ from Yad2 — discover at runtime
```

### Pattern 4: APScheduler Job Registration (mirrors Yad2 exactly)

```python
# Source: backend/app/main.py (existing pattern to replicate)
scheduler.add_job(
    run_madlan_scrape_job,
    trigger="interval",
    hours=settings.scrape_interval_hours,
    id="madlan_scrape",
    max_instances=1,
    coalesce=True,
    misfire_grace_time=300,
    next_run_time=datetime.now(timezone.utc),
)
```

### Pattern 5: Health Dict Initialization (mirrors Yad2 exactly)

```python
# Source: backend/app/scheduler.py (existing, add "madlan" key)
_health: dict[str, Optional[dict]] = {
    "yad2": None,
    "madlan": None,   # ADD THIS
}
```

### Pattern 6: Scraper Job Function (mirrors run_yad2_scrape_job exactly)

```python
# Source: backend/app/scheduler.py — run_yad2_scrape_job() pattern
async def run_madlan_scrape_job() -> None:
    """APScheduler job: run Madlan scraper → geocoding pass → dedup pass."""
    from app.database import async_session_factory
    from app.geocoding import run_dedup_pass, run_geocoding_pass
    from app.scrapers.madlan import run_madlan_scraper  # deferred import (Phase 3 pattern)

    started_at = datetime.now(timezone.utc)
    logger.info("Madlan scrape job started")
    try:
        async with async_session_factory() as session:
            result: ScraperResult = await run_madlan_scraper(session)
            await run_geocoding_pass(session)
            await run_dedup_pass(session)
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
```

### Pattern 7: Neighborhood Filter (reuse Yad2 logic with Madlan neighborhoods)

The Yad2 `is_in_target_neighborhood()` function checks for Hebrew neighborhood name substrings. Madlan may use the same neighborhood names (כרמל, מרכז העיר, נווה שאנן) in its address fields. The filter function can be copied verbatim; the config key `yad2_neighborhoods` is already a shared list.

```python
# Source: backend/app/scrapers/yad2.py — is_in_target_neighborhood()
def is_in_target_neighborhood(item: dict) -> bool:
    neighborhood = item.get("neighborhood", "") or ""
    address = item.get("street", "") or ""
    city = item.get("city", "") or ""
    location_text = f"{neighborhood} {address} {city}"
    return any(n in location_text for n in settings.yad2_neighborhoods)
    # NOTE: settings.yad2_neighborhoods is shared (contains כרמל, מרכז העיר, נווה שאנן)
    # No new config key needed — same neighborhoods apply to Madlan
```

### Pattern 8: LLM Prompt Adjustment

The existing `VERIFY_PROMPT` in `verifier.py` is hardcoded to say "Yad2 (יד2)". For Madlan, the scraper should pass a modified prompt text, OR the verifier should be source-aware. The simplest approach: pass Madlan listings with a note substituting "Madlan (מדלן)" for "Yad2 (יד2)" — OR accept the existing prompt as-is since the verification logic is identical and the source name in the prompt only affects context. Recommend keeping the existing prompt unchanged (the LLM behavior is identical for structured listings from either source).

### Anti-Patterns to Avoid

- **Separate proxy.py for Madlan:** Do not create a new proxy module. Import `get_proxy_launch_args` and `is_proxy_enabled` from the existing `app.scrapers.proxy` — identical to Yad2.
- **Chaining Madlan inside run_yad2_scrape_job:** Per D-03, Madlan is a fully separate job. Failure must be isolated at the job level.
- **Skipping the DevTools discovery task:** Madlan's data shape is UNKNOWN. Writing parse logic before discovery is guaranteed to produce broken code.
- **Using a shared browser profile with Yad2:** Use `~/.madlan-browser-profile` — a separate profile prevents session conflicts and cookie contamination between scrapers.
- **Hardcoding Madlan URL:** Add `madlan_base_url` to `Settings` in `config.py` so it's overridable without code changes.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Browser stealth | Custom UA/header spoofing | `playwright-stealth` 2.x `Stealth().apply_stealth_async(page)` | Already installed and tested; covers WebGL fingerprint, navigator properties, timing attacks |
| Proxy integration | New proxy wrapper | `app.scrapers.proxy.get_proxy_launch_args()` | Already written, tested, handles all three env vars |
| LLM verification | New LLM caller | `app.llm.verifier.batch_verify_listings()` + `merge_llm_fields()` | Already handles errors, low-confidence flagging, field merging |
| DB deduplication | Custom duplicate check | `sqlite_insert(...).on_conflict_do_nothing(index_elements=["source", "source_id"])` | Existing constraint on `(source, source_id)` handles it at DB level |
| Geocoding + dedup | Run in scraper | `run_geocoding_pass(session)` + `run_dedup_pass(session)` after scraping | Already written; called identically by both jobs |
| Health tracking | New state object | Extend existing `_health` dict in `scheduler.py` | `GET /api/health` already returns this dict — no router changes needed |

---

## Runtime State Inventory

Step 2.5 SKIPPED — this phase is a new feature addition (not a rename/refactor/migration). No existing runtime state contains "madlan" strings that require migration.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.x | Scraper runtime | ✓ | 3.9.6 | — |
| playwright (Python) | Browser automation | ✓ | 1.58.0 | — |
| playwright-stealth | Stealth fingerprint masking | ✓ | 2.0.2 | — |
| Chromium browser | Playwright headless | ✓ (installed with playwright) | (bundled) | — |
| pytest + pytest-asyncio | Test suite | ✓ | 8.4.2 | — |
| Bright Data proxy | CAPTCHA bypass (optional) | Config-dependent | — | Scraper proceeds without proxy; proxy adds resilience |
| madlan.co.il network access | Live scraping | Runtime-dependent | — | Cannot test scraper output without network access to site |

**Missing dependencies with no fallback:** None — all required tools are installed.

**Missing dependencies with fallback:**
- Bright Data proxy: optional; scraper works without it (proxy increases reliability against bot detection)

---

## Common Pitfalls

### Pitfall 1: Madlan data shape unknown until DevTools inspection
**What goes wrong:** Developer writes `parse_listing()` based on guessed field names. Scraper runs, returns 0 listings, silently skips all items because field name assumptions are wrong.
**Why it happens:** Madlan's internal data structure is undocumented. It may use GraphQL (object keys will be camelCase query-specific), REST JSON, or Next.js `__NEXT_DATA__` embedding (keys will differ from Yad2).
**How to avoid:** The discovery task MUST precede any code. Open `madlan.co.il/rent`, filter by Haifa, open DevTools Network tab, look for: (a) `__NEXT_DATA__` script tag in page source, (b) XHR/Fetch calls to `api.madlan.co.il` or similar, (c) GraphQL POST to `/graphql`. Document the exact field names found before writing parse code.
**Warning signs:** `listings_found: 0` after first run; no parse errors logged (items silently dropped due to missing `source_id`).

### Pitfall 2: Proxy scheme mismatch (https vs http)
**What goes wrong:** `page.goto("https://...")` silently fails or returns SSL error when Bright Data proxy is active.
**Why it happens:** Bright Data Web Unlocker handles SSL termination itself. Sending https:// through it causes double-SSL wrapping.
**How to avoid:** Mirror the Yad2 pattern exactly:
```python
url = "https://www.madlan.co.il/rent/..."
if is_proxy_enabled():
    url = url.replace("https://", "http://", 1)
```
**Warning signs:** `ERR_SSL_PROTOCOL_ERROR` in Playwright logs when proxy is enabled.

### Pitfall 3: Shared browser profile causes session conflicts
**What goes wrong:** Yad2 and Madlan share `~/.yad2-browser-profile`. One scraper's cookies/session state corrupt the other. Both scrapers start failing intermittently.
**Why it happens:** Persistent context uses on-disk profile. Concurrent writes to the same profile cause corruption.
**How to avoid:** Use `~/.madlan-browser-profile` — a completely separate directory from Yad2's profile.
**Warning signs:** Both scrapers failing after working individually; `SingletonLock` file conflicts in log.

### Pitfall 4: Circular import if Madlan is imported at module level in scheduler.py
**What goes wrong:** `ImportError` or circular dependency crash on startup.
**Why it happens:** The existing `run_yad2_scrape_job()` uses deferred imports (Phase 3 decision) to avoid this. If `run_madlan_scrape_job()` imports `run_madlan_scraper` at the top of `scheduler.py`, the circular import problem re-emerges.
**How to avoid:** All scraper imports inside the job function body (deferred import pattern):
```python
async def run_madlan_scrape_job() -> None:
    from app.scrapers.madlan import run_madlan_scraper  # deferred — inside function
    ...
```
**Warning signs:** `ImportError` on FastAPI startup before any request is served.

### Pitfall 5: Madlan source_id is not unique or stable
**What goes wrong:** `on_conflict_do_nothing` fails to deduplicate because `source_id` values change between runs (e.g., using a timestamp-based ID rather than a stable listing ID).
**Why it happens:** The discovery task must identify the stable listing identifier. Madlan may use a numeric ID, a slug, or a UUID — all are fine if stable across runs.
**How to avoid:** During DevTools discovery, verify the candidate `source_id` field by reloading the page and confirming the same listing has the same ID value. If no stable ID is found, construct a composite from `price + address hash`.
**Warning signs:** `listings_inserted` grows without bound on repeated runs; same listings appear multiple times in DB with different `source_id` values.

### Pitfall 6: `_health["madlan"]` is None on first /health call before job runs
**What goes wrong:** The `GET /api/health` endpoint returns `"madlan": {"last_run": null, "success": null}` immediately after startup. This is correct behavior — the job has not fired yet.
**Why it happens:** `next_run_time=datetime.now(timezone.utc)` fires the job immediately on startup, but there is a small window between lifespan start and first job completion.
**How to avoid:** This is not a bug — it's the same behavior as Yad2 and is handled by the existing health endpoint null-check. No special action needed.
**Warning signs:** None — this is expected behavior.

### Pitfall 7: Madlan may use bot-detection (Cloudflare or proprietary)
**What goes wrong:** All Playwright requests return a 403/challenge page. Scraper logs "0 listings found" or captures a bot-detection page instead of listing HTML.
**Why it happens:** Madlan is a high-traffic commercial site and may use Cloudflare Bot Management or similar. `playwright-stealth` reduces detection risk but does not eliminate it.
**How to avoid:**
1. `playwright-stealth` (already in use) covers most fingerprint-based detection.
2. Enable Bright Data proxy for CAPTCHA bypass.
3. Save page HTML to `/tmp/madlan_debug.html` (mirror Yad2's debug save) so bot-detection pages can be identified in logs.
4. Add bot-detection keyword check (similar to Yad2's `ShieldSquare`/`hcaptcha` check).
**Warning signs:** `listings_found: 0` with no parse errors; `/tmp/madlan_debug.html` contains "captcha", "cloudflare", "access denied" in page title.

---

## Code Examples

### DevTools Discovery Checklist (mandatory Wave 0 task)

This is not code — it is the procedure the implementer MUST follow before writing any parse logic:

1. Open `https://www.madlan.co.il/rent` in Chrome.
2. Open DevTools → Network tab → clear all existing requests.
3. Filter by city "חיפה", price max 4500 ₪, at least one target neighborhood.
4. **Check page source** (`Cmd+U` or DevTools → Sources): search for `__NEXT_DATA__`. If found, note the JSON structure at `props.pageProps` — look for a listings array key.
5. **Check Network → Fetch/XHR**: look for calls to `api.madlan.co.il`, `/graphql`, or any URL containing `rent` or `listings`. Note: (a) the URL, (b) whether it's GET or POST, (c) the response JSON structure.
6. **Identify `source_id`**: find the stable per-listing unique ID field (likely `id`, `listingId`, `token`, `slug`).
7. **Map fields to DB columns**: price, rooms, size_sqm, address/street/neighborhood, contact_info, post_date, listing URL pattern.
8. **Document findings** in a comment block at the top of `madlan.py` before writing any parse code.

### Scraper Skeleton (to be filled after discovery)

```python
# backend/app/scrapers/madlan.py
# Source: mirrors backend/app/scrapers/yad2.py structure exactly

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.config import settings
from app.llm.verifier import batch_verify_listings, merge_llm_fields
from app.models.listing import Listing
from app.scrapers.base import ScraperResult
from app.scrapers.proxy import get_proxy_launch_args, is_proxy_enabled

logger = logging.getLogger(__name__)

# Field mapping documented after DevTools discovery:
# [FILL IN after discovery task]
# source_id field: ???
# price field: ???
# rooms field: ???
# etc.

async def run_madlan_scraper(db: AsyncSession) -> ScraperResult:
    result = ScraperResult(source="madlan")
    try:
        # Playwright fetch → parse → neighborhood filter → price filter → LLM → insert
        ...
    except Exception as e:
        result.success = False
        result.errors.append(str(e))
        logger.error(f"[madlan] ERROR: {e} — scraper exiting cleanly")
    return result

if __name__ == "__main__":
    import asyncio, sys
    from app.database import async_session_factory
    async def main():
        async with async_session_factory() as db:
            result = await run_madlan_scraper(db)
            print(f"[madlan] Run complete: {result.listings_inserted} inserted")
            sys.exit(0 if result.success else 1)
    asyncio.run(main())
```

### Config Addition

```python
# backend/app/config.py — add to Settings class
madlan_base_url: str = "https://www.madlan.co.il/rent/haifa"
# Note: exact URL and query params determined by DevTools discovery
```

### parse_listing() Template (field names TBD from discovery)

```python
def parse_listing(item: dict) -> dict | None:
    """Extract and normalise fields from a single Madlan listing item.
    
    Field mapping documented after DevTools inspection.
    Returns dict ready for Listing table, or None if source_id is missing.
    """
    # source_id: use stable listing ID discovered via DevTools
    source_id = str(item.get("id") or item.get("listingId") or "").strip()
    if not source_id:
        return None

    return {
        "source": "madlan",
        "source_id": source_id,
        "title": ...,
        "price": ...,
        "rooms": ...,
        "size_sqm": ...,
        "address": ...,
        "contact_info": ...,
        "post_date": ...,
        "url": f"https://www.madlan.co.il/listing/{source_id}",  # verify pattern
        "source_badge": "מדלן",
        "raw_data": json.dumps(item, ensure_ascii=False),
        "lat": None,   # geocoded later by run_geocoding_pass
        "lng": None,
    }
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| playwright-stealth 1.x (`stealth_async(page)`) | playwright-stealth 2.x (`Stealth().apply_stealth_async(page)`) | 2024 | New API — already in use in yad2.py; Madlan must use same 2.x API |
| Separate worker process for scrapers | APScheduler embedded in FastAPI process | Phase 3 | No separate worker needed; deferred imports prevent circular imports |
| Per-listing LLM calls | Batch LLM calls via `asyncio.gather` | Phase 2 | Faster, rate-limit friendly; same pattern for Madlan |

---

## Open Questions

1. **Madlan's exact data format**
   - What we know: Madlan is a high-traffic Israeli real estate SPA. May be Next.js (common in Israeli tech). May use GraphQL (CLAUDE.md flags this as likely). Has listing pages with Haifa rental data.
   - What's unclear: Whether listing data is in `__NEXT_DATA__` (parseable without XHR interception), a REST API, or GraphQL POST. Field names, pagination approach, stable listing ID.
   - Recommendation: DevTools discovery is Wave 0 plan item. No code written until discovery complete.

2. **Madlan URL structure for Haifa + neighborhood + price filtering**
   - What we know: `madlan.co.il/rent` is the known entry point. The URL likely supports city/neighborhood/price query params (standard for Israeli real estate SaaS).
   - What's unclear: Exact query parameter names. Whether neighborhood codes differ from Yad2 (Yad2 uses numeric IDs like `609` for כרמל; Madlan may use slug strings).
   - Recommendation: Document URL structure during DevTools discovery. If URL-level filtering is not possible, apply post-scrape neighborhood + price filter (same fallback strategy as Yad2).

3. **Bot-detection level**
   - What we know: Madlan is commercial and likely has some bot protection. `playwright-stealth` + Bright Data proxy covers most scenarios.
   - What's unclear: Whether Madlan uses Cloudflare (aggressive) or a simpler rate-limiting approach. Whether headless=True works or headless=False is needed.
   - Recommendation: Start with `headless=True`. If bot-detection page appears in `/tmp/madlan_debug.html`, enable proxy or investigate `headless=False` option.

4. **LLM prompt: source name substitution**
   - What we know: Existing `VERIFY_PROMPT` says "from Yad2 (יד2)". This is cosmetic only — the LLM verification logic is identical.
   - What's unclear: Whether having "Yad2" in the prompt affects LLM behavior for Madlan listings (unlikely but possible if Madlan's format is significantly different).
   - Recommendation: Use existing prompt unchanged for initial implementation. Adjust only if LLM rejection rate for Madlan is unexpectedly high after first live run.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 + pytest-asyncio (asyncio_mode = auto) |
| Config file | `backend/pytest.ini` |
| Quick run command | `python3 -m pytest backend/tests/test_madlan_scraper.py -q` |
| Full suite command | `python3 -m pytest backend/tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MADL-01 | Scraper fetches Haifa listings filtered by neighborhood and price ≤ 4500 | unit | `pytest backend/tests/test_madlan_scraper.py::test_scraper_returns_haifa_listings_filtered_by_neighborhood_and_price -x` | ❌ Wave 0 |
| MADL-02 | Scraper extracts all required fields (title, price, rooms, size, address, contact, date, URL) | unit | `pytest backend/tests/test_madlan_scraper.py::test_scraper_extracts_all_required_fields -x` | ❌ Wave 0 |
| MADL-03 | Playwright + stealth runs; Madlan failure is fully isolated from Yad2 | unit | `pytest backend/tests/test_madlan_scraper.py::test_scraper_error_isolation -x` | ❌ Wave 0 |
| MADL-03 | source="madlan", source_badge="מדלן" set correctly | unit | `pytest backend/tests/test_madlan_scraper.py::test_source_badge_is_madlan -x` | ❌ Wave 0 |
| D-05 | `_health["madlan"]` updated after job run | unit | `pytest backend/tests/test_scheduler.py::test_madlan_scrape_job_updates_health -x` | ❌ Wave 0 |
| D-05 | `GET /api/health` returns madlan entry | unit | `pytest backend/tests/test_api.py::test_health_includes_madlan -x` | ❌ extends existing file |

### Sampling Rate
- **Per task commit:** `python3 -m pytest backend/tests/test_madlan_scraper.py -q`
- **Per wave merge:** `python3 -m pytest backend/tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_madlan_scraper.py` — covers MADL-01, MADL-02, MADL-03, D-07 (source_badge)
- [ ] Extend `backend/tests/test_scheduler.py` — add `test_madlan_scrape_job_updates_health` + `test_madlan_scrape_job_updates_health_on_failure`
- [ ] Extend `backend/tests/test_api.py` — add `test_health_includes_madlan` to verify the health endpoint returns the madlan key

**Existing test infrastructure covers:** conftest.py fixtures (`db_session`, `llm_valid_rental_response`, `llm_rejected_response`) are reusable as-is for Madlan tests.

---

## Sources

### Primary (HIGH confidence)
- `backend/app/scrapers/yad2.py` — exact patterns to replicate (read in full)
- `backend/app/scheduler.py` — integration target (read in full)
- `backend/app/config.py` — settings extension point (read in full)
- `backend/app/main.py` — lifespan job registration pattern (read in full)
- `backend/tests/test_yad2_scraper.py` — test structure to mirror (read in full)
- `backend/tests/conftest.py` — reusable fixtures (read in full)
- https://playwright.dev/python/docs/network — `page.on("response")` and `page.route()` API (verified)

### Secondary (MEDIUM confidence)
- CLAUDE.md — Playwright-first decision for Madlan confirmed; playwright-stealth 2.x API confirmed
- `.planning/phases/06-madlan-scraper/06-CONTEXT.md` — all decisions and integration points (read in full)
- `.planning/STATE.md` — blocker note on Madlan API shape confirmed LOW confidence

### Tertiary (LOW confidence)
- WebSearch: No public documentation, GitHub projects, or community reports on Madlan's specific API endpoint shape found. Confirms that runtime DevTools discovery is the only reliable path.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all tools pre-installed and version-verified
- Architecture (scheduler/health/config integration): HIGH — exact Yad2 pattern to replicate; code read in full
- Madlan data parsing (field names, source_id, URL pattern): LOW — requires DevTools discovery at build time; no public documentation found
- Bot-detection risk: MEDIUM — playwright-stealth + proxy covers standard cases; Madlan-specific behavior unknown

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (stable stack); Madlan discovery findings valid indefinitely once captured
