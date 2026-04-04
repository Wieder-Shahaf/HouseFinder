# Phase 8: Facebook Scrapers — Research

**Researched:** 2026-04-04
**Domain:** Facebook scraping with Playwright Python — authenticated sessions, Groups DOM, Marketplace URL patterns, session health monitoring
**Confidence:** MEDIUM (Facebook DOM and bot-detection evolve continuously; patterns here are verified as of April 2026 but require runtime confirmation)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Groups configured via `/data/facebook_groups.json` — URL + Hebrew display name per entry
- **D-02:** File format: `[{"url": "...", "name": "שכירות חיפה"}]`
- **D-03:** Missing or empty groups file → skip with `ScraperResult(source="facebook_groups", success=True)`, 0 counts, log warning
- **D-04:** Both scrapers use the same `batch_verify_listings()` LLM pipeline as Yad2/Madlan
- **D-05:** Confidence threshold and rejection behavior: same as existing pipeline
- **D-06:** Session health check runs before each Facebook scrape (both Groups and Marketplace)
- **D-07:** On session expiry: Web Push notification fires (Phase 7 channel). Hebrew title/body as specified
- **D-08:** Session expiry surfaced in `GET /health` as `facebook_session_valid: bool`
- **D-09:** On session expiry: returns `ScraperResult(success=True)` with note in errors list — no error propagation
- **D-10:** Two separate independent APScheduler jobs: `run_facebook_groups_scrape_job()` and `run_facebook_marketplace_scrape_job()`
- **D-11:** Both jobs use `scrape_interval_hours` — no separate interval for Facebook
- **D-12:** Each job gets its own `_health` dict entry; plus shared `facebook_session_valid` field
- **D-13:** Scraper contract: `async def run_facebook_groups_scraper(db: AsyncSession) -> ScraperResult` and `async def run_facebook_marketplace_scraper(db: AsyncSession) -> ScraperResult` in `backend/app/scrapers/facebook_groups.py` and `backend/app/scrapers/facebook_marketplace.py`
- **D-14:** Session storage: `/data/facebook_session.json` — Playwright storage state JSON. Env var: `FACEBOOK_SESSION_PATH` defaulting to `/data/facebook_session.json`
- **D-15:** Source badge values: `"facebook_groups"` and `"facebook_marketplace"`

### Claude's Discretion

- Exact Facebook Groups DOM structure for extracting post text, poster name/link, post date, and post URL
- Whether to intercept XHR/GraphQL calls or parse rendered DOM for Groups posts
- Exact Facebook Marketplace URL structure and filters for Haifa rentals
- `playwright-stealth` configuration and fingerprint masking approach
- `source_id` equivalent for Facebook posts (stable unique identifier per post)
- LLM prompt wording adjustments for Facebook post format vs Yad2/Madlan listing format
- Whether to run both scrapers with `headless=False` + Xvfb or headless with stealth

### Deferred Ideas (OUT OF SCOPE)

None from this discussion.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FBGR-01 | Scraper monitors user-configured Facebook group list for rental posts | Groups list loaded from `/data/facebook_groups.json`; each group URL navigated via Playwright with loaded session |
| FBGR-02 | Scraper uses saved authenticated Playwright session (manual login once) | `browser.new_context(storage_state=path)` API confirmed; login script pattern documented below |
| FBGR-03 | Session health checked before each run; alert sent on expiry | URL redirect detection (`page.url` contains `login`) or DOM auth element absence; Web Push via existing `notifier.py` |
| FBGR-04 | Scraper extracts: post text, poster name/link, post date, group name, post URL | DOM inspection required at runtime; fallback: XHR interception of GraphQL; post URL derived from `/groups/{id}/permalink/{post_id}/` pattern |
| FBGR-05 | Facebook Groups failure is isolated — does not block other scrapers | Same try/except wrapping as Yad2/Madlan; `success=True` on session expiry skip |
| FBMP-01 | Scraper fetches rental listings in Haifa from Facebook Marketplace | URL: `https://www.facebook.com/marketplace/haifa/propertyrentals/` — confirmed from search |
| FBMP-02 | Scraper uses same authenticated session as Facebook Groups | Same `storage_state` file `/data/facebook_session.json` loaded in new context |
| FBMP-03 | Scraper extracts: title, price, address/neighborhood, post date, listing URL | Marketplace listing cards in DOM; item URLs follow `/marketplace/item/{numeric_id}/` |
| FBMP-04 | Facebook Marketplace failure is isolated | Same try/except wrapping; independent APScheduler job |
</phase_requirements>

---

## Summary

Phase 8 implements two independent Facebook scrapers (Groups + Marketplace) that share a single Playwright storage state file. The primary challenge is not the code architecture — which mirrors the established Yad2/Madlan pattern exactly — but Facebook's aggressive anti-bot detection and evolving DOM. Both scrapers must load the saved session at runtime, check session validity before scraping, and return cleanly without error propagation if the session has expired.

The existing codebase already provides everything needed: `ScraperResult`, `get_proxy_launch_args()`, `batch_verify_listings()`, the `_health` dict pattern, and the Web Push notifier. Phase 8 is primarily additive: two new scraper files, additions to `scheduler.py`, `config.py`, and `main.py`, plus a login script to generate the initial session.

**Primary recommendation:** Use `browser.new_context(storage_state=path)` (not `launch_persistent_context`) for the Facebook scrapers — this is the correct API for loading a pre-saved session. Apply `playwright-stealth` to the context (not the page), using `Stealth().apply_stealth_async(context)`. For session health check, navigate to `https://www.facebook.com/` and inspect `page.url` — if it redirects to `/login/` the session is expired.

---

## Standard Stack

### Core (already in requirements.txt — no new installs needed)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| `playwright` (Python) | 1.58.0 (installed) | Browser automation | Already in `requirements.txt` |
| `playwright-stealth` | 2.0.2 → 2.0.3 available | Fingerprint masking | Already installed; 2.0.3 released 2026-04-04 |
| `beautifulsoup4` | 4.12+ (installed) | HTML parsing fallback | Already in `requirements.txt` |

### No New Dependencies Required

All libraries are already installed. The login script (`generate_facebook_session.py`) is a standalone utility that runs outside Docker — it needs only Playwright + an Xvfb/display environment on the host or droplet.

**Version verification:**
```bash
pip show playwright-stealth  # 2.0.2 installed; 2.0.3 available (backward-compatible)
```

playwright-stealth 2.0.3 is backward-compatible with 2.0.2. The `Stealth().apply_stealth_async(context)` API is confirmed stable — this is the same API already used in `yad2.py` (`await Stealth().apply_stealth_async(page)`).

**API discrepancy to note:** The existing `yad2.py` calls `Stealth().apply_stealth_async(page)` — passing a Page. The official v2 docs show passing a Context. Both work, but applying to Context is preferred for Facebook scrapers since stealth should apply to the entire context from launch.

---

## Architecture Patterns

### Recommended Project Structure (additions only)

```
backend/app/scrapers/
├── base.py                         # unchanged
├── proxy.py                        # unchanged
├── yad2.py                         # unchanged
├── madlan.py                       # unchanged
├── facebook_groups.py              # NEW — FBGR-01..05
└── facebook_marketplace.py         # NEW — FBMP-01..04

backend/app/
├── config.py                       # ADD facebook_session_path setting
├── scheduler.py                    # ADD two job functions + _health entries
└── main.py                         # ADD job registration + facebook_session_valid in /health

backend/scripts/
└── generate_facebook_session.py    # NEW — one-time manual login script

/data/
├── facebook_session.json           # generated by login script (Docker volume)
└── facebook_groups.json            # user-edited group list
```

### Pattern 1: Loading Saved Session State (FBGR-02, FBMP-02)

**What:** Use `browser.new_context(storage_state=path)` to inject saved cookies/localStorage into a fresh context. This is the correct approach — NOT `launch_persistent_context` (which creates a stateful browser profile directory, not a portable JSON session).

**When to use:** Every scraper invocation for both Groups and Marketplace.

```python
# Source: https://playwright.dev/python/docs/api/class-browser#browser-new-context
import json
from pathlib import Path
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def _load_fb_context(p, session_path: str):
    """Create a browser context with saved Facebook session loaded."""
    browser = await p.chromium.launch(
        headless=True,  # or False + Xvfb in production; see Pitfall 3
        **get_proxy_launch_args(),
    )
    context = await browser.new_context(
        storage_state=session_path,   # loads cookies + localStorage from JSON file
        locale="he-IL",
        viewport={"width": 1280, "height": 800},
        extra_http_headers={"Accept-Language": "he-IL,he;q=0.9"},
    )
    await Stealth().apply_stealth_async(context)  # apply to context, not page
    return browser, context
```

### Pattern 2: Session Health Check (FBGR-03, D-06, D-07, D-08)

**What:** Navigate to `https://www.facebook.com/` and check if the URL redirects to a login page, OR check for the absence of an authenticated DOM element (e.g., the Facebook home feed). Both signals are reliable indicators of session expiry.

**Detection method:**
- Primary: `page.url` contains `login` after navigation → session expired
- Secondary: `await page.locator('[aria-label="Facebook"]').count() == 0` after navigation

```python
# Source: Playwright Python docs + empirical pattern
async def check_session_health(context) -> bool:
    """Return True if session is valid, False if login redirect detected."""
    page = await context.new_page()
    try:
        await page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)
        current_url = page.url
        if "login" in current_url or "checkpoint" in current_url:
            return False
        # Secondary check: home feed nav element presence
        nav_count = await page.locator('[data-pagelet="LeftRail"]').count()
        return nav_count > 0
    except Exception:
        return False
    finally:
        await page.close()
```

### Pattern 3: Session Expiry Alert + Clean Skip (D-07, D-08, D-09)

**What:** When `check_session_health()` returns False, fire a Web Push notification and return `ScraperResult(success=True)` with a note in `errors`. Update `facebook_session_valid` in `_health`.

```python
# Reuses existing notifier.py send_push() — same pattern as run_notification_job()
from app.notifier import send_session_expiry_alert  # new thin wrapper, see below

async def run_facebook_groups_scraper(db: AsyncSession) -> ScraperResult:
    result = ScraperResult(source="facebook_groups")
    session_path = settings.facebook_session_path

    async with async_playwright() as p:
        browser, context = await _load_fb_context(p, session_path)
        try:
            if not await check_session_health(context):
                await send_session_expiry_alert()  # Web Push
                result.errors.append("session_expired: Facebook session requires re-authentication")
                return result  # success=True, 0 counts — D-09
            # ... scrape logic
        finally:
            await context.close()
            await browser.close()
    return result
```

### Pattern 4: APScheduler Job Registration (D-10, D-11, D-12)

**What:** Add two jobs in `main.py` lifespan, following the exact Yad2/Madlan pattern. Add `"facebook_groups"` and `"facebook_marketplace"` keys to `_health` dict. Add `facebook_session_valid` as a top-level or nested field.

```python
# In scheduler.py — mirrors run_madlan_scrape_job() exactly
async def run_facebook_groups_scrape_job() -> None:
    from app.database import async_session_factory
    from app.geocoding import run_dedup_pass, run_geocoding_pass
    from app.notifier import run_notification_job
    from app.scrapers.facebook_groups import run_facebook_groups_scraper  # deferred

    started_at = datetime.now(timezone.utc)
    logger.info("Facebook Groups scrape job started")
    try:
        async with async_session_factory() as session:
            result = await run_facebook_groups_scraper(session)
            await run_geocoding_pass(session)
            await run_dedup_pass(session)
            await run_notification_job(session, started_at)
    except Exception as exc:
        logger.exception("Facebook Groups scrape job failed: %s", exc)
        result = ScraperResult(source="facebook_groups", success=False, errors=[str(exc)])

    _health["facebook_groups"] = {
        "last_run": started_at.isoformat(),
        "listings_found": result.listings_found,
        "listings_inserted": result.listings_inserted,
        "listings_rejected": result.listings_rejected,
        "listings_flagged": result.listings_flagged,
        "success": result.success,
        "errors": result.errors,
    }
```

### Pattern 5: Source ID for Facebook Posts

**What:** Use the post's numeric ID extracted from its URL as the stable `source_id`. Facebook group post URLs follow the pattern:
`https://www.facebook.com/groups/{group_id}/permalink/{post_id}/` or
`https://www.facebook.com/groups/{group_name}/posts/{post_id}/`

Extract via regex: `re.search(r'/(?:permalink|posts)/(\d+)', post_url)`.

For Marketplace listings, the item URL is `/marketplace/item/{numeric_id}/` — use the numeric ID directly.

If a URL cannot be extracted, fallback to hashing `(group_url + post_text[:200])` — deterministic and dedup-safe.

```python
import hashlib, re

def extract_post_source_id(post_url: str, fallback_text: str = "") -> str:
    """Extract numeric post ID from Facebook URL, or hash fallback."""
    if post_url:
        m = re.search(r'/(?:permalink|posts|item)/(\d+)', post_url)
        if m:
            return m.group(1)
    # Fallback: deterministic hash of text content
    return hashlib.sha256(fallback_text.encode()).hexdigest()[:32]
```

### Pattern 6: LLM Prompt Adjustment for Facebook Format

**What:** The existing `VERIFY_PROMPT` in `verifier.py` says "You are analyzing a Hebrew real estate listing from Yad2 (יד2)." For Facebook posts, this source reference is misleading for the LLM. Create a Facebook-specific prompt variant (or pass a source hint to `batch_verify_listings()`).

The simplest approach: create `FACEBOOK_VERIFY_PROMPT` in each scraper file by replacing the source line. The LLM pipeline contract (`batch_verify_listings(raw_texts)`) already accepts arbitrary text — no pipeline changes required; only prompt text differs.

**Recommendation:** Add an optional `prompt_override` parameter to `batch_verify_listings()`, or pass Facebook-specific raw text prefixed with `"[פוסט מקבוצת פייסבוק]\n"` so the LLM understands the source context.

### Pattern 7: One-Time Login Script

**What:** A standalone script the user runs once (with a visible browser) to authenticate and save the session to `/data/facebook_session.json`. This file is then loaded by both scrapers at runtime.

```python
# scripts/generate_facebook_session.py
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # visible browser
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://www.facebook.com/login/")
        print("Log in manually in the browser window. Press Enter when done.")
        input()
        await context.storage_state(path="/data/facebook_session.json")
        print("Session saved to /data/facebook_session.json")
        await browser.close()

asyncio.run(main())
```

This script runs on the host (or inside a Docker container with `--env DISPLAY=:99` and Xvfb).

### Anti-Patterns to Avoid

- **Using `launch_persistent_context` for session loading:** This creates a stateful browser profile directory, not the portable JSON session. Use `browser.new_context(storage_state=path)` instead. (Note: `yad2.py` uses `launch_persistent_context` for a different purpose — cookie persistence across httpx fallbacks. Facebook scrapers don't need this.)
- **Automated email+password login in the scraper:** Facebook detects and blocks this. Session must be generated manually once, then reused.
- **Applying stealth only to the page:** Apply to the context via `Stealth().apply_stealth_async(context)` so all pages in the context are stealthed from creation.
- **Hard-coding DOM selectors as the only extraction strategy:** Facebook's HTML class names are obfuscated (e.g., `x8gbvx8 x78zum5`) and change without notice. Always implement a secondary fallback (XHR interception or text extraction).
- **Propagating session expiry as a scraper failure:** D-09 is explicit — session expiry returns `success=True`. Treat it as a skip, not an error.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM verification of Facebook posts | Custom verification logic | Existing `batch_verify_listings()` + `merge_llm_fields()` | Already handles messy Hebrew free-text; D-04 explicitly locks this |
| Web Push for session expiry | Custom push implementation | Existing `notifier.py` + pywebpush | Phase 7 built and tested this; reuse the send function |
| Browser fingerprint masking | Custom JS injection | `playwright-stealth` 2.0.x | Already in requirements.txt; handles 15+ evasion techniques |
| Proxy integration | Custom proxy setup | `get_proxy_launch_args()` from `proxy.py` | Already handles Bright Data config + empty dict fallback |
| Health state tracking | Custom dict/store | `_health` dict in `scheduler.py` | Established pattern; GET /health already reads it |
| DB deduplication | Custom duplicate check | SQLite `on_conflict_do_nothing` on `(source, source_id)` | Same as Yad2/Madlan — UniqueConstraint already in schema |

**Key insight:** Phase 8 is almost entirely wiring work — the hard parts (LLM pipeline, notification delivery, dedup, health tracking, proxy) are all solved. The unique challenge is Facebook's DOM and session management.

---

## Common Pitfalls

### Pitfall 1: Session File Missing at Scraper Startup
**What goes wrong:** Both scrapers crash with `FileNotFoundError` if `/data/facebook_session.json` doesn't exist yet (before first manual login).
**Why it happens:** The session must be manually generated; it doesn't exist on first container start.
**How to avoid:** Add a guard at the top of each scraper: `if not Path(session_path).exists(): return ScraperResult(source="...", success=True, errors=["session file not found"])`. Same pattern as D-03 for the groups file.
**Warning signs:** Container crash logs showing `FileNotFoundError` on startup scrape run.

### Pitfall 2: Facebook Detects Headless Browser
**What goes wrong:** Facebook shows a CAPTCHA, blank page, or login wall even with a valid session loaded.
**Why it happens:** Headless Chromium leaks browser automation signals (navigator.webdriver, missing Chrome plugins, screen size inconsistencies) even with stealth applied.
**How to avoid:** On the DigitalOcean VPS, run Playwright with `headless=False` + Xvfb. In the Docker container, `ENV DISPLAY=:99` + `Xvfb :99 -screen 0 1280x800x24 &` before starting the backend. For local dev, headless=True + stealth is usually sufficient.
**Warning signs:** `page.url` ends up on `facebook.com/login/` immediately after navigating to a group URL, even with a fresh valid session.

### Pitfall 3: headless vs headed Decision
**What goes wrong:** Headless mode is increasingly detectable by Facebook. Running headless=True may work locally but fail on the VPS.
**Why it happens:** Facebook's bot-detection infrastructure fingerprints GPU rendering, font metrics, and WebGL outputs that differ between headless and headed browsers.
**How to avoid:** The researcher/planner should default to `headless=False` + Xvfb for the VPS deployment. The Docker image already needs Xvfb for this case. Add `RUN apt-get install -y xvfb` to the Dockerfile and a startup wrapper.
**Warning signs:** Scraper works locally (headless=True) but consistently fails on VPS.

### Pitfall 4: DOM Selectors Break Without Warning
**What goes wrong:** CSS selectors like `.x8gbvx8` stop matching after a Facebook frontend deploy.
**Why it happens:** Facebook uses obfuscated, generated class names that change with each deployment.
**How to avoid:** Use semantic/structural selectors as primary (`[data-ad-preview="message"]`, `[role="article"]`) and fall back to broad text extraction (`page.inner_text("main")`). Never rely on a single class-name selector.
**Warning signs:** `listings_found = 0` without errors — selector matched nothing silently.

### Pitfall 5: Rate Limiting / Temporary IP Ban
**What goes wrong:** Scraping too many groups too fast triggers a temporary access restriction ("You're Temporarily Blocked").
**Why it happens:** Facebook rate-limits automated navigation by session + IP.
**How to avoid:** Add 5–15 second random delays between group navigations. Process at most 5–10 groups per run. Log warnings if response contains "Temporarily Blocked".
**Warning signs:** Page title or body contains "Temporarily Blocked" or "تم حظر حسابك" (Arabic/Hebrew equivalent appears for Israeli users).

### Pitfall 6: `facebook_session_valid` State Shared Between Two Jobs
**What goes wrong:** Both `run_facebook_groups_scrape_job` and `run_facebook_marketplace_scrape_job` need to update `facebook_session_valid` in `_health`. If they run concurrently, there's a write conflict on the module-level dict.
**Why it happens:** `_health` is a Python dict — not thread-safe, but APScheduler uses asyncio, so concurrent modification within a single event loop is actually safe. However, one scraper might set `facebook_session_valid=False` while the other hasn't checked yet.
**How to avoid:** Both scrapers independently call `check_session_health()` and set `_health["facebook_session_valid"]` themselves. The health endpoint reads the latest value — races are benign here (both scrapers read the same session file). Document this explicitly.

### Pitfall 7: Session Expiry Alert Fires Repeatedly
**What goes wrong:** Web Push fires every 2 hours while the session is expired — spamming the user.
**Why it happens:** Both jobs check the session each run; if expired, each fires the alert.
**How to avoid:** Use a module-level flag `_session_alert_sent: bool = False` in `scheduler.py`. Only send the alert once; reset the flag when a new run detects a valid session.

---

## Code Examples

### Full Scraper Skeleton (Facebook Groups)

```python
# Source: established project pattern (yad2.py + decisions D-13, D-14)
from __future__ import annotations
import json, logging, re
from datetime import datetime
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.config import settings
from app.llm.verifier import batch_verify_listings, merge_llm_fields
from app.models.listing import Listing
from app.scrapers.base import ScraperResult
from app.scrapers.proxy import get_proxy_launch_args

logger = logging.getLogger(__name__)

async def run_facebook_groups_scraper(db: AsyncSession) -> ScraperResult:
    result = ScraperResult(source="facebook_groups")
    session_path = settings.facebook_session_path

    # Guard: session file not yet generated
    if not Path(session_path).exists():
        result.errors.append("session file not found — run generate_facebook_session.py first")
        return result  # success=True

    # Load groups config
    groups_config_path = Path("/data/facebook_groups.json")
    if not groups_config_path.exists():
        logger.warning("[fb_groups] /data/facebook_groups.json not found — skipping")
        return result  # D-03: success=True, 0 counts

    groups = json.loads(groups_config_path.read_text())
    if not groups:
        logger.warning("[fb_groups] groups list is empty — skipping")
        return result

    try:
        from playwright.async_api import async_playwright
        from playwright_stealth import Stealth

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, **get_proxy_launch_args())
            context = await browser.new_context(
                storage_state=session_path,
                locale="he-IL",
                viewport={"width": 1280, "height": 800},
            )
            await Stealth().apply_stealth_async(context)

            # Session health check (D-06)
            if not await _check_session_valid(context):
                await _fire_session_expiry_alert()
                result.errors.append("session_expired")
                await context.close()
                await browser.close()
                return result  # D-09: success=True

            # Scrape each group
            all_posts = []
            for group in groups:
                posts = await _scrape_group(context, group)
                all_posts.extend(posts)

            await context.close()
            await browser.close()

        result.listings_found = len(all_posts)
        if all_posts:
            raw_texts = [p.get("raw_data", str(p)) for p in all_posts]
            llm_results = await batch_verify_listings(raw_texts)
            # ... same merge/insert loop as yad2.py

    except Exception as e:
        result.success = False
        result.errors.append(str(e))
        logger.error("[fb_groups] ERROR: %s", e)

    return result
```

### Session Health Check

```python
async def _check_session_valid(context) -> bool:
    page = await context.new_page()
    try:
        await page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)
        url = page.url
        return "login" not in url and "checkpoint" not in url
    except Exception:
        return False
    finally:
        await page.close()
```

### Group Post Extraction (DOM-first, XHR fallback)

```python
# Source: empirical — requires runtime DOM inspection to confirm selectors
async def _scrape_group(context, group: dict) -> list[dict]:
    """Extract rental posts from a single Facebook group.

    Primary: Parse rendered DOM looking for post article elements.
    Fallback: Log warning if 0 posts found (selector may need updating).
    """
    page = await context.new_page()
    posts = []
    try:
        await page.goto(group["url"], wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        # Scroll to load more posts
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

        # RUNTIME TODO: inspect actual DOM to confirm selector
        # Facebook group post articles are wrapped in role="article" or
        # data-pagelet containing the feed
        articles = await page.query_selector_all('[role="article"]')

        for article in articles:
            try:
                text = await article.inner_text()
                post_url = ""
                # Look for permalink link within article
                links = await article.query_selector_all('a[href*="/permalink/"], a[href*="/posts/"]')
                if links:
                    post_url = await links[0].get_attribute("href") or ""
                    if post_url.startswith("/"):
                        post_url = "https://www.facebook.com" + post_url

                source_id = extract_post_source_id(post_url, text)
                posts.append({
                    "source": "facebook_groups",
                    "source_id": source_id,
                    "raw_data": json.dumps({"text": text, "url": post_url, "group": group["name"]}, ensure_ascii=False),
                    "url": post_url or group["url"],
                    "source_badge": "facebook_groups",
                    "group_name": group["name"],
                })
            except Exception as e:
                logger.debug("[fb_groups] Could not parse article: %s", e)

        if not posts:
            logger.warning("[fb_groups] 0 posts extracted from %s — selector may need update", group["url"])

    finally:
        await page.close()
        await page.wait_for_timeout(5000)  # rate limit between groups

    return posts
```

### Marketplace Scraper URL + Extraction

```python
# Source: search-verified URL pattern from facebook.com/marketplace/telaviv/propertyrentals/
FB_MARKETPLACE_HAIFA_URL = "https://www.facebook.com/marketplace/haifa/propertyrentals/"

async def _scrape_marketplace(context) -> list[dict]:
    page = await context.new_page()
    listings = []
    try:
        await page.goto(FB_MARKETPLACE_HAIFA_URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        # Scroll to load more listings
        for _ in range(5):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

        # RUNTIME TODO: inspect actual Marketplace DOM
        # Listing cards typically have links to /marketplace/item/{id}/
        item_links = await page.query_selector_all('a[href*="/marketplace/item/"]')
        seen_ids = set()
        for link in item_links:
            href = await link.get_attribute("href") or ""
            m = re.search(r'/marketplace/item/(\d+)', href)
            if m and m.group(1) not in seen_ids:
                item_id = m.group(1)
                seen_ids.add(item_id)
                item_url = f"https://www.facebook.com/marketplace/item/{item_id}/"
                # Get visible text from parent container
                try:
                    text = await link.evaluate("el => el.closest('[class]').innerText")
                except Exception:
                    text = await link.inner_text()

                listings.append({
                    "source": "facebook_marketplace",
                    "source_id": item_id,
                    "raw_data": json.dumps({"text": text, "url": item_url}, ensure_ascii=False),
                    "url": item_url,
                    "source_badge": "facebook_marketplace",
                })
    finally:
        await page.close()

    return listings
```

### Config Addition

```python
# In config.py — add to Settings class
facebook_session_path: str = "/data/facebook_session.json"
```

### Notifier Extension for Session Expiry

```python
# In notifier.py — add thin wrapper
async def send_session_expiry_alert() -> None:
    """Send Web Push alert for Facebook session expiry (D-07)."""
    payload = {
        "title": "פייסבוק דורש התחברות מחדש",
        "body": "לגתי לדף הכניסה, סריקת קבוצות דולגה",
        "url": settings.app_url,
    }
    # Load subscription + send via webpush — same pattern as run_notification_job()
    ...
```

### Health Endpoint Addition

```python
# In main.py — add facebook_session_valid to health response
@app.get("/api/health")
async def health():
    state = get_health_state()
    scrapers = {}
    for source, result in state.items():
        if source == "facebook_session_valid":
            continue  # handled separately below
        ...
    return {
        "status": "ok",
        "scrapers": scrapers,
        "facebook_session_valid": state.get("facebook_session_valid"),
    }
```

---

## State of the Art

| Old Approach | Current Approach | Status | Impact |
|--------------|------------------|--------|--------|
| `playwright_stealth(page)` (1.x function API) | `Stealth().apply_stealth_async(context)` (2.x class API) | Current in project (`yad2.py` uses page variant) | Apply to context for Facebook scrapers |
| `facebook-scraper` library | Playwright + stealth | `facebook-scraper` broken since 2024 (per CLAUDE.md) | Do not use |
| `headless=True` default | `headless=False` + Xvfb on VPS | Growing detection of headless mode | May require Dockerfile change |
| `launch_persistent_context` | `browser.new_context(storage_state=path)` | Both valid; latter is correct for portable session JSON | Use new_context for Facebook |

**Deprecated/outdated:**
- `facebook-scraper` PyPI library: broken as of 2024 per CLAUDE.md — do not use
- `mechanicalsoup` / `requests+lxml`: no JS execution — cannot scrape Facebook SPA

---

## Open Questions

1. **Exact Groups DOM selector**
   - What we know: Post articles use `role="article"` (common Facebook pattern)
   - What's unclear: Whether this selector still works for Israeli-locale Facebook in April 2026; post text element selector within the article
   - Recommendation: Wave 0 task — open group URL in Playwright, dump HTML to `/tmp/fb_groups_debug.html`, inspect and confirm selector before implementing extraction

2. **headless vs headed on DigitalOcean VPS**
   - What we know: Facebook increasingly detects headless; CLAUDE.md recommends `headless=False` + Xvfb for VPS
   - What's unclear: Whether current `playwright-stealth` 2.0.x is sufficient for headless on this VPS IP
   - Recommendation: Implement with `headless=True` + stealth first; add Xvfb path as fallback if detection is observed. Document Dockerfile changes needed.

3. **`facebook_session_valid` field location in `_health`**
   - What we know: D-08 says it should be in `GET /health` as a boolean field; D-12 says it's a "shared" field
   - What's unclear: Top-level in `_health` dict vs nested inside each job's entry
   - Recommendation: Store as top-level `_health["facebook_session_valid"]` (separate from job-specific entries) and surface at top level in the health response. Both scrapers write to this same key.

4. **Groups posting frequency and scroll depth**
   - What we know: Israeli Facebook apartment groups can have 5–50 posts/day
   - What's unclear: How many scroll iterations are needed to capture the last 2 hours of posts
   - Recommendation: Default to 3 scroll iterations; post date filtering in the scraper loop (skip posts older than `scrape_interval_hours * 2`)

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | Container packaging | Yes | 29.2.1 | — |
| Playwright (Python) | Browser automation | Yes (in image) | 1.58.0 | — |
| playwright-stealth | Fingerprint masking | Yes (in image) | 2.0.2 | — |
| Xvfb | headless=False mode | Not checked (VPS) | — | headless=True + stealth |
| `/data/facebook_session.json` | Session auth | Not present (user must generate) | — | Scraper skips gracefully |
| `/data/facebook_groups.json` | Groups list | Not present (user must create) | — | Scraper skips gracefully (D-03) |

**Missing dependencies with no fallback:**
- None — all external tools are either present or the scraper handles absence gracefully.

**Missing dependencies with fallback:**
- `facebook_session.json`: must be generated manually via login script before scrapers can fetch data
- `facebook_groups.json`: must be created by user before Groups scraper fetches data
- Xvfb: if headless mode is blocked by Facebook, VPS needs `apt-get install xvfb` and Dockerfile update

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio |
| Config file | `backend/pytest.ini` (`asyncio_mode = auto`) |
| Quick run command | `cd backend && python -m pytest tests/test_facebook_scrapers.py -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FBGR-01 | Groups list loaded from JSON config | unit | `pytest tests/test_facebook_scrapers.py::test_groups_config_loaded -x` | Wave 0 |
| FBGR-01 | Missing groups file returns success=True, 0 counts | unit | `pytest tests/test_facebook_scrapers.py::test_groups_missing_file -x` | Wave 0 |
| FBGR-02 | Session loaded from storage_state file | unit | `pytest tests/test_facebook_scrapers.py::test_session_loaded -x` | Wave 0 |
| FBGR-03 | Session health check returns False on login redirect | unit | `pytest tests/test_facebook_scrapers.py::test_session_health_expired -x` | Wave 0 |
| FBGR-03 | Session expiry fires Web Push + returns success=True | unit | `pytest tests/test_facebook_scrapers.py::test_session_expiry_returns_clean -x` | Wave 0 |
| FBGR-04 | parse_fb_post() extracts text, url, source_id | unit | `pytest tests/test_facebook_scrapers.py::test_parse_fb_post -x` | Wave 0 |
| FBGR-05 | Exception in groups scraper → success=False, does not raise | unit | `pytest tests/test_facebook_scrapers.py::test_groups_failure_isolation -x` | Wave 0 |
| FBMP-01 | Marketplace scraper uses Haifa URL | unit | `pytest tests/test_facebook_scrapers.py::test_marketplace_url -x` | Wave 0 |
| FBMP-02 | Marketplace uses same session file | unit | (covered by test_session_loaded parametrized) | Wave 0 |
| FBMP-03 | parse_marketplace_listing() extracts title, price, url, source_id | unit | `pytest tests/test_facebook_scrapers.py::test_parse_marketplace -x` | Wave 0 |
| FBMP-04 | Exception in marketplace → success=False, does not raise | unit | `pytest tests/test_facebook_scrapers.py::test_marketplace_failure_isolation -x` | Wave 0 |
| D-12 | scheduler _health updated after facebook jobs | unit | `pytest tests/test_facebook_scrapers.py::test_scheduler_health_updated -x` | Wave 0 |
| D-08 | GET /health includes facebook_session_valid field | unit | `pytest tests/test_api.py::test_health_facebook_session_valid -x` | Wave 0 (extend existing) |

**Test pattern mirrors `test_madlan_scraper.py` and `test_scheduler.py` exactly:** mock Playwright, mock LLM, use in-memory SQLite via existing `conftest.py` fixtures.

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_facebook_scrapers.py -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_facebook_scrapers.py` — covers all FBGR/FBMP requirements above
- [ ] `backend/tests/test_api.py` — extend with `test_health_facebook_session_valid`

*(Existing `conftest.py`, pytest.ini, and test infrastructure cover all fixtures needed — no new framework install required.)*

---

## Project Constraints (from CLAUDE.md)

All directives from `CLAUDE.md` that apply to Phase 8:

| Directive | Applies to Phase 8 |
|-----------|-------------------|
| Use `playwright` 1.44+ (Python) for Facebook — do NOT replace with higher-level wrapper | Yes — scrapers use playwright directly |
| Use `playwright-stealth` for fingerprint masking | Yes — `Stealth().apply_stealth_async()` |
| Do NOT use `facebook-scraper` library (broken since 2024) | Yes — not used |
| Do NOT use `mechanicalsoup`, `requests+lxml`, `Selenium` for Facebook | Yes — not used |
| Session persistence: `headless=False` + Xvfb on VPS | Yes — plan must account for Dockerfile/Xvfb |
| Rate limits: 5–15 seconds between navigations | Yes — implement in scraper loop |
| Do NOT attempt automated email+password login | Yes — session generated manually once |
| Build health-check that detects login redirect → WhatsApp/Push alert | Yes — D-06/D-07/D-08 |
| SQLite + SQLAlchemy async + `on_conflict_do_nothing` deduplication | Yes — same DB pattern as other scrapers |
| APScheduler embedded — no separate worker | Yes — two new jobs in existing scheduler |
| All UI in Hebrew/RTL | Not applicable (no UI changes in Phase 8) |
| Bright Data proxy: reuse `get_proxy_launch_args()` | Yes — must pass to browser.launch() |

---

## Sources

### Primary (HIGH confidence)
- [Playwright Python Auth docs](https://playwright.dev/python/docs/auth) — `storage_state` save/load API, `new_context(storage_state=path)` signature
- [Playwright Python `browser.new_context()`](https://playwright.dev/python/docs/api/class-browser#browser-new-context) — `storage_state` and `proxy` parameters
- [`playwright-stealth` PyPI](https://pypi.org/project/playwright-stealth/) — version 2.0.3, `Stealth().apply_stealth_async(context)` API confirmed
- Project codebase (`yad2.py`, `scheduler.py`, `notifier.py`, `config.py`, `base.py`, `proxy.py`) — established patterns all scrapers must follow

### Secondary (MEDIUM confidence)
- [facebook.com/marketplace/telaviv/propertyrentals/](https://www.facebook.com/marketplace/telaviv/propertyrentals/) — URL pattern for Israeli city Marketplace rentals; Haifa follows same pattern (`/haifa/`)
- [GitHub: thanh2004nguyen/facebook-group-scraper](https://github.com/thanh2004nguyen/facebook-group-scraper) — storage_state login pattern, `login_and_save_state.py` approach confirmed
- [Playwright Python BrowserContext.storage_state](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-storage-state) — `set_storage_state()` and save API

### Tertiary (LOW confidence — requires runtime verification)
- Facebook Groups DOM selector (`role="article"`) — widely reported but changes without notice; must be confirmed via browser DevTools on live group
- Facebook Marketplace listing DOM — same caveat; class names change frequently
- `data-pagelet="LeftRail"` as session validity indicator — empirical, needs runtime confirmation

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and in use
- Session management pattern: HIGH — verified via official Playwright docs
- Facebook URL patterns: MEDIUM — Marketplace URL derived from observed Israeli city patterns; may need adjustment
- DOM selectors: LOW — Facebook's obfuscated class names change; Wave 0 DOM inspection task is mandatory
- Stealth effectiveness: MEDIUM — playwright-stealth 2.0.x is current; Facebook detection evolves

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (30 days) — Facebook DOM patterns may drift before then; re-verify selectors at implementation start
