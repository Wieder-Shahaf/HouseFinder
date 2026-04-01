# Phase 2: Yad2 Scraper + LLM Pipeline - Research

**Researched:** 2026-04-02
**Domain:** Python web scraping (httpx + Playwright fallback), Anthropic Claude API, async SQLAlchemy write patterns
**Confidence:** MEDIUM (Yad2 API endpoint requires DevTools verification; all other areas HIGH)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Try the Yad2 internal XHR API first using `httpx` (no browser). If the endpoint requires auth, returns incomplete data, or is blocked — fall back to Playwright+stealth. The ROADMAP research flag (verify API via DevTools before coding) applies here: the plan should include a research step before writing the scraper.
- **D-02:** Default threshold = **0.7**. Listings with `llm_confidence < 0.7` are flagged in the database (`llm_confidence` column) and excluded from the map view — but not deleted. Threshold must be configurable via `settings` (add `llm_confidence_threshold: float = 0.7` to `Settings`).
- **D-03:** LLM verification runs **after the full scrape batch**, not per-listing during the scrape. Implementation: `asyncio.gather()` over all scraped listings — parallel LLM calls, non-blocking from the scraper's perspective. This fulfills LLM-05 ("does not block the scraper pipeline") without adding background task infrastructure that belongs in Phase 3.
- **D-04:** Core scraper logic lives in `async def run_yad2_scraper(db: AsyncSession) -> ScraperResult`. This function is importable by APScheduler in Phase 3 without modification. A `__main__` block wraps it for manual invocation: `python -m scrapers.yad2`. No FastAPI endpoint needed in Phase 2 — the scheduler in Phase 3 imports and calls the function directly.

### Claude's Discretion

- Directory layout for scraper modules (e.g., `backend/app/scrapers/` vs `backend/scrapers/`)
- LLM prompt design for Hebrew listing verification/extraction
- `ScraperResult` return type shape (listings written, listings rejected, errors)
- Whether to log rejected listings to a separate table or just skip them
- Exact httpx request headers to mimic a browser for the Yad2 API call

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| YAD2-01 | Scraper fetches active rental listings in Haifa filtered by neighborhoods (Carmel, Downtown, Neve Shanan) and price ≤ 4,500 ₪ | httpx-first approach with Playwright fallback; Haifa city code confirmed as requiring DevTools verification |
| YAD2-02 | Scraper extracts: title, price, rooms, size (sqm), address, contact info, post date, listing URL | Listing model already has all target columns; LLM supplements missing fields |
| YAD2-03 | Scraper runs via Playwright (stealth) to bypass bot detection | playwright 1.58.0 + playwright-stealth 2.0.2 confirmed available; stealth API confirmed |
| YAD2-04 | Scraper failure is isolated — Yad2 error does not block other scrapers | try/except wrapping run_yad2_scraper; ScraperResult return type with error field |
| LLM-01 | Each scraped post is passed through an LLM to verify it is an actual rental listing (not "looking for apartment", not a sale, not spam) | Anthropic SDK 0.88.0; output_config.format json_schema for structured output |
| LLM-02 | LLM extracts and normalizes structured fields from free-form Hebrew text: price, rooms, size, address, contact info, availability date | Claude Haiku 4.5 supports Hebrew; structured JSON output via output_config.format |
| LLM-03 | LLM assigns a confidence score to each extraction; listings below threshold are flagged and excluded from the map | llm_confidence column exists; threshold 0.7 from D-02; confidence field in JSON schema |
| LLM-04 | LLM-extracted fields override or supplement scraper-extracted fields when scraper returns incomplete data | LLM JSON response merges with scraped fields; scraper fields take precedence when populated |
| LLM-05 | LLM verification runs asynchronously after scraping — does not block the scraper pipeline | asyncio.gather() over batch; D-03 locked this pattern |
| LLM-06 | Model used is configurable (default: claude-haiku-4-5 for cost efficiency) | Confirmed model ID: claude-haiku-4-5-20251001; alias: claude-haiku-4-5; $1/input MTok, $5/output MTok |
</phase_requirements>

---

## Summary

Phase 2 builds a Yad2 rental scraper and an LLM verification pipeline. The scraper attempts the Yad2 internal XHR API first (httpx, no browser) and falls back to Playwright+stealth if the API is blocked or insufficient. Scraped listings are written to the existing `listings` table in raw form, then a batch of async Claude Haiku 4.5 calls verifies each listing and extracts/normalizes structured fields. Listings below the 0.7 confidence threshold are flagged but not deleted.

The most critical unknown going into implementation is the exact Yad2 XHR API endpoint URL and parameters — confirmed by the project's own ROADMAP and multiple independent sources to require browser DevTools verification at build time. The plan must include an explicit DevTools-inspection step before writing scraper code. The Crawl4AI fallback (v0.7.4) and Playwright fallback are both well-understood and ready to use.

The LLM layer is well-understood: Anthropic SDK 0.88.0 is current, Claude Haiku 4.5 (alias `claude-haiku-4-5`) is the correct cost-efficient model, and structured outputs via `output_config.format` / `json_schema` are generally available without beta headers.

**Primary recommendation:** Write the scraper in two parts — a thin DevTools-research wave that confirms the API shape, then the implementation waves for the httpx path, Playwright fallback, LLM pipeline, and integration. Use `asyncio.gather()` for batch LLM calls and `insert().on_conflict_do_nothing()` for DB upserts.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | 0.88.0 | Claude API client | Official SDK; structured output via output_config.format; async support |
| httpx | 0.28.1 (already pinned) | First-attempt Yad2 API calls | Async HTTP client; already in requirements.txt |
| playwright | 1.58.0 | Fallback browser automation for Yad2 | Project standard; required by CLAUDE.md for Yad2 fallback |
| playwright-stealth | 2.0.2 | Mask headless browser fingerprints | Required by CLAUDE.md for all scrapers; current release |
| crawl4ai | 0.7.4 | Optional second fallback (JS-rendered scraping) | CLAUDE.md preferred tool for Yad2; LLM-ready markdown output |
| pydantic | 2.12.5 (already pinned) | ScraperResult type, LLM response models | Already in requirements.txt; used for structured validation |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio (stdlib) | Python 3.12 | Parallel LLM calls with gather() | D-03: batch LLM pipeline |
| aiosqlite | 0.22.1 (pinned) | Async SQLite driver | Already in requirements.txt |
| json (stdlib) | — | raw_data serialization | Store scraped payload pre-LLM |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| output_config.format json_schema | Prompt-only JSON extraction | Structured outputs guarantee valid JSON; no retry logic needed |
| playwright-stealth 2.0.2 | undetected-playwright | playwright-stealth is the CLAUDE.md standard; 2.x rewrote API |
| asyncio.gather() | Sequential LLM calls | gather() cuts wall-clock time from O(N) to ~O(1) concurrent |

**Installation (new dependencies only):**
```bash
pip install "anthropic==0.88.0" "playwright==1.58.0" "playwright-stealth==2.0.2" "crawl4ai==0.7.4"
playwright install chromium
crawl4ai-setup  # installs Playwright browsers for crawl4ai
```

**Version verification:** Confirmed against PyPI 2026-04-02.
- anthropic: 0.88.0 (latest)
- playwright: 1.58.0 (latest)
- playwright-stealth: 2.0.2 (latest)
- crawl4ai: 0.7.4 (latest)

---

## Architecture Patterns

### Recommended Project Structure
```
backend/app/scrapers/          # Claude's discretion: place under app/ for importability
├── __init__.py
├── base.py                    # ScraperResult dataclass, base exception types
└── yad2.py                    # run_yad2_scraper() + __main__ block

backend/app/llm/
├── __init__.py
└── verifier.py                # verify_listing(), batch_verify_listings()
```

**Why `backend/app/scrapers/` (not `backend/scrapers/`):** Placing scrapers under `app/` keeps the import path `from app.scrapers.yad2 import run_yad2_scraper` consistent with how APScheduler in Phase 3 will import it, and the existing codebase is `backend/app/`-rooted.

### Pattern 1: httpx-First API Approach with Playwright Fallback

**What:** Try the Yad2 internal XHR gateway endpoint with httpx (no browser, fastest). If blocked (403, empty response, CAPTCHA redirect), fall back to Playwright+stealth browser session.

**When to use:** Always for Yad2 (D-01 locked). httpx first = no browser startup cost, ~100x faster.

**Example (httpx path — parameters to be confirmed via DevTools):**
```python
# Source: CLAUDE.md Yad2 scraping section + httpx 0.28 docs
import httpx

YAD2_API_BASE = "https://gw.yad2.co.il/feed/realestate/rent"  # VERIFY via DevTools

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "he-IL,he;q=0.9",
    "Referer": "https://www.yad2.co.il/realestate/rent",
}

async def fetch_yad2_api(city_code: int, price_max: int) -> dict:
    params = {
        "city": city_code,   # VERIFY: Haifa city code (likely 4000 or 700 — must confirm)
        "priceOnly": 1,
        "price": f"0-{price_max}",
        # topArea, area params — VERIFY via DevTools
    }
    async with httpx.AsyncClient(headers=HEADERS, timeout=30.0) as client:
        response = await client.get(YAD2_API_BASE, params=params)
        response.raise_for_status()
        return response.json()
```

### Pattern 2: Playwright+Stealth Fallback

**What:** Browser session with stealth patches applied. Used when httpx path is blocked.

**When to use:** When `fetch_yad2_api()` raises `httpx.HTTPStatusError` with 403/429, or returns empty/non-JSON response.

**Example:**
```python
# Source: playwright 1.58 docs + playwright-stealth 2.0 README
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

async def fetch_yad2_browser(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="he-IL",
            extra_http_headers={"Accept-Language": "he-IL,he;q=0.9"},
        )
        page = await context.new_page()
        await stealth_async(page)
        await page.goto(url, wait_until="networkidle")
        content = await page.content()
        await browser.close()
        return content
```

**Note on playwright-stealth 2.x:** The 2.0.0 release changed the API. The stealth function is now `stealth_async(page)` (async) — not the old `stealth(page)` synchronous call. Always import from `playwright_stealth` (underscore), not `playwright-stealth`.

### Pattern 3: ScraperResult Return Type

**What:** Typed dataclass returned by `run_yad2_scraper()` so APScheduler in Phase 3 can log outcomes.

**Example:**
```python
# Source: pydantic 2.12 docs + D-04 contract
from dataclasses import dataclass, field

@dataclass
class ScraperResult:
    source: str
    listings_found: int = 0
    listings_inserted: int = 0
    listings_skipped: int = 0      # duplicates (on_conflict_do_nothing)
    listings_rejected: int = 0     # LLM rejection
    listings_flagged: int = 0      # below confidence threshold
    errors: list[str] = field(default_factory=list)
    success: bool = True
```

### Pattern 4: Async Batch LLM Verification

**What:** After scrape completes, fire all LLM calls concurrently with asyncio.gather(). Each call uses Anthropic SDK structured output.

**When to use:** D-03 locked this — always batch after scrape, never per-listing during scrape.

**Example (Anthropic SDK 0.88 structured output):**
```python
# Source: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
import asyncio
import anthropic
import json

client = anthropic.Anthropic(api_key=settings.llm_api_key)

LISTING_SCHEMA = {
    "type": "object",
    "properties": {
        "is_rental": {"type": "boolean"},
        "rejection_reason": {"type": "string"},   # null if is_rental=true
        "confidence": {"type": "number"},
        "price": {"type": ["integer", "null"]},
        "rooms": {"type": ["number", "null"]},
        "size_sqm": {"type": ["integer", "null"]},
        "address": {"type": ["string", "null"]},
        "contact_info": {"type": ["string", "null"]},
    },
    "required": ["is_rental", "rejection_reason", "confidence"],
    "additionalProperties": False,
}

async def verify_listing(raw_text: str) -> dict:
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.messages.create(
            model=settings.llm_model,   # default: "claude-haiku-4-5"
            max_tokens=512,
            messages=[{"role": "user", "content": VERIFY_PROMPT.format(text=raw_text)}],
            output_config={
                "format": {"type": "json_schema", "schema": LISTING_SCHEMA}
            },
        ),
    )
    return json.loads(response.content[0].text)

async def batch_verify_listings(raw_texts: list[str]) -> list[dict]:
    return await asyncio.gather(*[verify_listing(t) for t in raw_texts])
```

**Important:** The Anthropic SDK 0.88 Python client is synchronous by default. Use `loop.run_in_executor(None, ...)` to call it from async code without blocking the event loop. An async wrapper (`AsyncAnthropic`) is also available: `anthropic.AsyncAnthropic()` with `await client.messages.create(...)` — this is the cleaner path.

### Pattern 5: DB Upsert with on_conflict_do_nothing

**What:** Insert scraped listings without failing on duplicates (same source + source_id).

**When to use:** Every listing insert in the scraper.

**Example:**
```python
# Source: SQLAlchemy 2.0 async docs + existing UniqueConstraint("source", "source_id")
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

stmt = sqlite_insert(Listing).values(**listing_data)
stmt = stmt.on_conflict_do_nothing(
    index_elements=["source", "source_id"]
)
result = await db.execute(stmt)
await db.commit()
inserted = result.rowcount  # 0 = duplicate, 1 = new
```

### Anti-Patterns to Avoid

- **Per-listing LLM calls during scrape:** Blocked by D-03. LLM runs after the batch completes, not inline.
- **Deleting low-confidence listings:** D-02 is explicit — flag in `llm_confidence` column, do not delete. Map view filters by threshold.
- **Hardcoding Yad2 API URL/params without DevTools verification:** The training-data URL `gw.yad2.co.il/feed/realestate/rent` is a hypothesis, not confirmed fact. The plan must include a DevTools inspection step before scraper code is written.
- **Using synchronous `stealth(page)` from playwright-stealth 1.x:** playwright-stealth 2.x changed to `stealth_async(page)`. Using the old API silently does nothing.
- **Storing LLM-extracted fields without merging:** LLM-04 says LLM supplements scraper fields, not replaces. Scraper-extracted values (non-null) take precedence; LLM fills nulls.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Browser fingerprint evasion | Custom UA rotation / JS injection | playwright-stealth 2.0.2 | stealth patches 20+ browser fingerprint leaks; maintaining manually is a full-time job |
| JSON schema validation of LLM output | Manual JSON parsing + validation | output_config.format json_schema | Constrained decoding guarantees valid JSON; eliminates retry logic entirely |
| Duplicate insertion logic | Custom check-before-insert | SQLAlchemy insert().on_conflict_do_nothing() | Atomic at DB level; immune to race conditions |
| Concurrent async rate limiting | Manual semaphore + sleep | asyncio.Semaphore (stdlib) | If Anthropic rate limits become an issue, wrap gather() with a semaphore — do not hand-roll |
| Playwright session management | Custom context lifecycle | `async with async_playwright() as p:` context manager | Guarantees cleanup even on errors |

**Key insight:** The Yad2 anti-bot layer and Anthropic JSON schema validation are both "deceptively deep" problems — surface-level solutions break quickly. Use the existing tools that handle the hard parts.

---

## Common Pitfalls

### Pitfall 1: Yad2 API Endpoint is Stale / Changed

**What goes wrong:** The endpoint `gw.yad2.co.il/feed/realestate/rent` referenced in CLAUDE.md returns 404 or redirects to a different URL because Yad2 updated their internal API between when that was written and now.

**Why it happens:** Yad2 is a commercial site that has no obligation to keep internal API endpoints stable. Multiple sources confirm the endpoint changes without notice.

**How to avoid:** The first task in Wave 1 must be a manual DevTools inspection step. The developer opens `yad2.co.il/realestate/rent` in Chrome DevTools → Network tab → filter XHR → identify the actual feed URL and parameters. This is a human research step, not automatable. The plan must block scraper coding on this step completing.

**Warning signs:** 403 with no body, redirect to `/login`, or response HTML instead of JSON on first httpx call.

### Pitfall 2: playwright-stealth 2.x API Change

**What goes wrong:** Code written based on playwright-stealth 1.x examples calls `stealth(page)` (synchronous, no await). In playwright-stealth 2.x this function was renamed to `stealth_async(page)` and must be awaited.

**Why it happens:** The 2.0.0 release was a breaking change. Most blog posts and Stack Overflow answers show the 1.x API.

**How to avoid:** Always `from playwright_stealth import stealth_async` and `await stealth_async(page)`. If `stealth` (non-async) is imported from `playwright_stealth`, it does not exist in 2.x and raises ImportError — which is actually good (fail loudly rather than silently not stealthing).

**Warning signs:** `ImportError: cannot import name 'stealth' from 'playwright_stealth'`.

### Pitfall 3: Anthropic SDK Sync vs Async Confusion

**What goes wrong:** `anthropic.Anthropic()` creates a synchronous client. Calling `client.messages.create()` from within an `async def` blocks the event loop, defeating the point of `asyncio.gather()`.

**Why it happens:** The SDK has two clients: `anthropic.Anthropic` (sync) and `anthropic.AsyncAnthropic` (async). The sync one is more commonly shown in docs examples.

**How to avoid:** Use `anthropic.AsyncAnthropic()` for async code. Then `await client.messages.create(...)` is non-blocking and `asyncio.gather()` works correctly.

**Warning signs:** All LLM calls complete sequentially despite gather(); scraper hangs; event loop blocked warnings.

### Pitfall 4: LLM Confidence as Float vs LLM Rejection as Bool

**What goes wrong:** The schema conflates "is this a rental?" (boolean rejection) with "how confident is the extraction?" (float 0–1). A post might be a genuine rental but have a low confidence score because the address is unclear.

**Why it happens:** Prompt design ambiguity — asking the LLM for a single score that means both "is valid" and "extraction quality."

**How to avoid:** The LLM schema should have two separate fields: `is_rental: bool` (rejection gate — must be True to insert) and `confidence: float` (extraction quality — stored in `llm_confidence`, filtered by 0.7 threshold). A listing where `is_rental=False` is rejected regardless of confidence score and never inserted.

**Warning signs:** "Looking for apartment" posts appearing in the database.

### Pitfall 5: asyncio.gather() Partial Failure

**What goes wrong:** If one LLM call in a `gather()` batch raises an exception, by default `gather()` propagates the first exception and cancels remaining tasks, losing the results from successful calls.

**Why it happens:** Default `return_exceptions=False` behavior.

**How to avoid:** Use `asyncio.gather(*coros, return_exceptions=True)` and filter the results. Log exceptions separately; continue processing successful results.

```python
results = await asyncio.gather(*coros, return_exceptions=True)
successes = [r for r in results if not isinstance(r, Exception)]
failures = [r for r in results if isinstance(r, Exception)]
```

### Pitfall 6: Hebrew Text Encoding in httpx

**What goes wrong:** Yad2 API responses are UTF-8 with Hebrew text. If `response.text` is not decoded correctly (e.g., wrong charset assumption), Hebrew characters become garbled, breaking LLM input.

**Why it happens:** httpx auto-detects charset from Content-Type header; if Yad2 omits the charset declaration, httpx may fall back to ISO-8859-1.

**How to avoid:** Explicitly decode: `text = response.content.decode("utf-8")`. Or use `response.json()` which always assumes UTF-8 for JSON.

---

## Code Examples

### Verified Pattern: Anthropic SDK 0.88 Structured Output (no beta header needed)
```python
# Source: https://platform.claude.com/docs/en/build-with-claude/structured-outputs (verified 2026-04-02)
import anthropic

client = anthropic.AsyncAnthropic(api_key="...")

response = await client.messages.create(
    model="claude-haiku-4-5",   # alias; resolves to claude-haiku-4-5-20251001
    max_tokens=512,
    messages=[{"role": "user", "content": "..."}],
    output_config={
        "format": {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {
                    "is_rental": {"type": "boolean"},
                    "confidence": {"type": "number"},
                },
                "required": ["is_rental", "confidence"],
                "additionalProperties": False,
            },
        }
    },
)
import json
data = json.loads(response.content[0].text)
```

**Note:** `output_format` (old beta parameter) still works for transition but `output_config.format` is the current API. No beta header required.

### Verified Pattern: SQLAlchemy 2.0 Async on_conflict_do_nothing
```python
# Source: SQLAlchemy 2.0 docs + existing project pattern
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.models.listing import Listing

stmt = (
    sqlite_insert(Listing)
    .values(
        source="yad2",
        source_id=listing["id"],
        title=listing.get("title"),
        price=listing.get("price"),
        raw_data=json.dumps(listing),
    )
    .on_conflict_do_nothing(index_elements=["source", "source_id"])
)
result = await db.execute(stmt)
await db.commit()
```

### Verified Pattern: crawl4ai 0.7 AsyncWebCrawler (fallback)
```python
# Source: https://docs.crawl4ai.com/core/quickstart/ (verified 2026-04-02)
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

browser_config = BrowserConfig(headless=True)
run_config = CrawlerRunConfig()

async with AsyncWebCrawler(config=browser_config) as crawler:
    result = await crawler.arun(
        url="https://www.yad2.co.il/realestate/rent?city=...",
        config=run_config,
    )
    markdown_content = result.markdown  # LLM-ready markdown string
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `output_format` beta header for structured JSON | `output_config.format` (GA, no beta header) | Late 2025 | Clean API; no transition overhead for new code |
| `playwright-stealth` 1.x synchronous `stealth(page)` | `playwright-stealth` 2.x `await stealth_async(page)` | 2024 (2.0.0 release) | Breaking import — must use async form |
| `claude-3-haiku-20240307` | `claude-haiku-4-5` (claude-haiku-4-5-20251001) | Oct 2025 | Haiku 3 deprecated April 19, 2026; use Haiku 4.5 now |
| Inline LLM calls per listing | Batch asyncio.gather() after scrape | D-03 (project decision) | Better throughput; no blocking |

**Deprecated/outdated:**
- `claude-3-haiku-20240307`: Deprecated, retires April 19, 2026. Use `claude-haiku-4-5` instead.
- `playwright-stealth` 1.x `stealth()` sync API: Removed in 2.0.0.
- `output_format` beta header approach: Superseded by `output_config.format` (still works during transition, but don't use for new code).

---

## Open Questions

1. **Yad2 XHR API Endpoint URL and Parameters**
   - What we know: CLAUDE.md references `gw.yad2.co.il/feed/realestate/rent` as the XHR endpoint. This is a hypothesis from training data (acknowledged as potentially stale in both CLAUDE.md and ROADMAP blockers section).
   - What's unclear: Current URL, exact parameter names for city (Haifa), price range, neighborhood, pagination. Whether authentication cookies are required. Whether the endpoint is rate-limited at a per-IP or per-session level.
   - Recommendation: **The plan's Wave 1 must be a manual DevTools step.** The developer opens `yad2.co.il/realestate/rent` in Chrome, inspects XHR requests, and records the actual endpoint URL, parameters, and required headers. This step MUST complete before writing any scraper code. Block Wave 2 on Wave 1 completion.

2. **Haifa City Code / Neighborhood Filter Parameters**
   - What we know: CONTEXT.md specifies neighborhoods כרמל, מרכז העיר, נווה שאנן. Yad2 uses city codes and area codes in URL parameters.
   - What's unclear: Whether neighborhood filtering is a URL parameter, a post-scrape filter, or requires separate API queries per neighborhood.
   - Recommendation: Document Haifa city code and neighborhood filter parameters as part of the DevTools wave. If neighborhood filtering is not available at API query level, apply it post-scrape by checking the listing's address field.

3. **Crawl4AI vs Raw Playwright for Fallback**
   - What we know: CLAUDE.md lists Crawl4AI as the preferred Yad2 fallback. crawl4ai 0.7.4 wraps Playwright and outputs LLM-ready markdown.
   - What's unclear: Whether crawl4ai's internal stealth settings are sufficient for Yad2, or whether raw Playwright+playwright-stealth gives better control for a site with active bot detection.
   - Recommendation: Implement Playwright+stealth fallback as the primary fallback (more control, proven pattern). Crawl4AI is a secondary fallback if raw Playwright approach proves difficult to parse. This is within Claude's discretion.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Backend runtime | ✗ (local: 3.9.6) | 3.9.6 locally; project targets 3.12 in Docker | Docker container runs 3.12 — dev on local 3.9 is fine for most code, test in Docker |
| httpx | YAD2-01 (API path) | ✓ (in requirements.txt) | 0.28.1 | — |
| playwright | YAD2-03 (fallback) | Needs install | 1.58.0 on PyPI | — |
| playwright-stealth | YAD2-03 | Needs install | 2.0.2 on PyPI | — |
| crawl4ai | Yad2 fallback | Needs install | 0.7.4 on PyPI | Raw Playwright+BS4 |
| anthropic SDK | LLM-01 through LLM-06 | Needs install | 0.88.0 on PyPI | — |
| ANTHROPIC_API_KEY | LLM calls | Not verified — env var | — | No fallback; blocking for LLM tasks |

**Missing dependencies with no fallback:**
- `ANTHROPIC_API_KEY` env var must be present for LLM pipeline. Wave 0 should verify this is set before LLM tasks run. Add to `.env` and Settings class.

**Missing dependencies with fallback:**
- `crawl4ai`: Raw Playwright+BeautifulSoup4 is a viable fallback.
- Python 3.9.6 local vs 3.12 in Docker: Code should be written to 3.12 target; test critical paths in Docker.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio (asyncio_mode=auto) |
| Config file | `backend/pytest.ini` — exists, `asyncio_mode = auto` set |
| Quick run command | `cd backend && python -m pytest tests/ -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| YAD2-01 | Scraper returns listings filtered to Haifa + price ≤ 4500 | unit (mock httpx) | `pytest tests/test_yad2_scraper.py::test_filter_haifa_price -x` | ❌ Wave 0 |
| YAD2-02 | Scraper extracts all 8 required fields | unit (mock response) | `pytest tests/test_yad2_scraper.py::test_field_extraction -x` | ❌ Wave 0 |
| YAD2-03 | Playwright fallback invoked when httpx returns 403 | unit (mock httpx 403) | `pytest tests/test_yad2_scraper.py::test_playwright_fallback_triggered -x` | ❌ Wave 0 |
| YAD2-04 | ScraperResult.errors populated, no exception raised, on network error | unit | `pytest tests/test_yad2_scraper.py::test_error_isolation -x` | ❌ Wave 0 |
| LLM-01 | LLM rejects "looking for apartment" posts | unit (mock anthropic) | `pytest tests/test_llm_verifier.py::test_rejects_looking_for_apt -x` | ❌ Wave 0 |
| LLM-02 | LLM extracts price/rooms/address from Hebrew text | unit (mock anthropic) | `pytest tests/test_llm_verifier.py::test_field_extraction_hebrew -x` | ❌ Wave 0 |
| LLM-03 | Listings with confidence < 0.7 are flagged, not deleted | unit + db | `pytest tests/test_llm_verifier.py::test_confidence_threshold_flagging -x` | ❌ Wave 0 |
| LLM-04 | LLM fields supplement (not replace) scraper fields | unit | `pytest tests/test_llm_verifier.py::test_field_merge_precedence -x` | ❌ Wave 0 |
| LLM-05 | batch_verify_listings uses gather() — no sequential blocking | unit (timing/mock) | `pytest tests/test_llm_verifier.py::test_batch_is_concurrent -x` | ❌ Wave 0 |
| LLM-06 | Model name comes from Settings.llm_model, default claude-haiku-4-5 | unit | `pytest tests/test_llm_verifier.py::test_model_configurable -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/ -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_yad2_scraper.py` — covers YAD2-01, YAD2-02, YAD2-03, YAD2-04
- [ ] `backend/tests/test_llm_verifier.py` — covers LLM-01 through LLM-06
- [ ] Mock fixtures for: httpx responses (success + 403), anthropic SDK responses (rental / non-rental / low confidence)
- [ ] New package installs: `pip install anthropic playwright playwright-stealth crawl4ai` before test run

---

## Sources

### Primary (HIGH confidence)
- Anthropic Models Overview: https://platform.claude.com/docs/en/about-claude/models/overview — confirmed claude-haiku-4-5 model ID and pricing
- Anthropic Structured Outputs: https://platform.claude.com/docs/en/build-with-claude/structured-outputs — confirmed output_config.format API, no beta header required
- crawl4ai docs: https://docs.crawl4ai.com/core/quickstart/ — confirmed AsyncWebCrawler usage pattern for 0.7.x
- PyPI version checks (2026-04-02): anthropic==0.88.0, playwright==1.58.0, playwright-stealth==2.0.2, crawl4ai==0.7.4
- Existing project code: `backend/app/models/listing.py`, `backend/app/config.py`, `backend/app/database.py`, `backend/tests/conftest.py` — confirmed existing patterns

### Secondary (MEDIUM confidence)
- CLAUDE.md Yad2 scraping section — XHR API approach hypothesis (`gw.yad2.co.il/feed/realestate/rent`); marked MEDIUM confidence in CLAUDE.md itself
- Multiple Yad2 scraping community projects (GitHub, Apify, ZenRows) confirm: Yad2 uses XHR endpoints with city/price query params, rate-limits aggressively (~3 req/min), and blocks scrapers. Specific endpoint URL unverified.

### Tertiary (LOW confidence)
- Specific Yad2 API endpoint URL `gw.yad2.co.il/feed/realestate/rent` and city code for Haifa — LOW, training data only, requires DevTools verification at build time.

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — all versions verified against PyPI on 2026-04-02
- Architecture: HIGH — patterns derived from official docs and existing project code
- LLM pipeline: HIGH — Anthropic docs verified directly; SDK 0.88 confirmed
- Yad2 API endpoint: LOW — training data hypothesis; MUST verify via DevTools before coding
- Pitfalls: HIGH — derived from official changelog (stealth 2.x, SDK sync/async), official docs (gather exceptions), and confirmed project constraints

**Research date:** 2026-04-02
**Valid until:** Stack section stable for 30 days; Yad2 API endpoint must be re-verified at build time regardless of age.
