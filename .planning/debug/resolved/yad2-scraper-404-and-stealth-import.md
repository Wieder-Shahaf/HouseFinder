---
status: resolved
trigger: "yad2-scraper-404-and-stealth-import"
created: 2026-04-02T00:00:00Z
updated: 2026-04-02T00:30:00Z
---

## Current Focus

hypothesis: CONFIRMED — two new bugs found after captcha solved. (7) LLM API key not configured: backend/.env did not exist; pydantic-settings reads LLM_API_KEY, but the file was absent so settings.llm_api_key="". anthropic.AsyncAnthropic(api_key="") throws auth error. (8) LLM errors counted as rejections: pipeline at yad2.py line 543 checks is_rental=False without distinguishing "LLM said not a rental" from "LLM call failed" — both increment listings_rejected.
test: (7) Fixed by creating backend/.env with LLM_API_KEY placeholder; user must fill in real key. (8) Fixed in yad2.py Step 4 — rejection_reason starting with "LLM error:" now flags (not rejects) and still inserts the listing with confidence=0.0.
expecting: After user sets LLM_API_KEY and re-runs, listings_found=3, listings_inserted>0, listings_rejected=0.
next_action: Await user confirmation that LLM_API_KEY is set and test_run.py succeeds with insertions.

## Symptoms

expected: Yad2 scraper fetches rental listings, stores them in DB
actual: httpx gets 404, then Playwright fallback crashes on stealth import
errors:
  - "[yad2] httpx failed (Client error '404 Not Found' for url 'https://gw.yad2.co.il/feed-search/realestate/rent?city=4000&price=0-4500&propertyGroup=apartments&neighborhood=609') — falling back to Playwright"
  - "[yad2] ERROR: cannot import name 'stealth_async' from 'playwright_stealth' (/Users/shahafwieder/Library/Python/3.9/lib/python/site-packages/playwright_stealth/__init__.py) — scraper exiting cleanly"
reproduction: cd backend && python3 test_run.py
started: First real test run — may never have worked against live Yad2

## Eliminated

- hypothesis: URL requires authentication headers not currently sent
  evidence: 404 is a path error not an auth error (401/403); DEVTOOLS-FINDINGS explicitly notes feed-search was a hypothesis URL, not confirmed
  timestamp: 2026-04-02T00:01:00Z

- hypothesis: playwright_stealth package is missing/broken
  evidence: Package is installed and its __init__.py clearly imports from playwright_stealth.stealth which exports `Stealth` class. The old `stealth_async` function doesn't exist in this newer API version.
  timestamp: 2026-04-02T00:01:00Z

## Evidence

- timestamp: 2026-04-02T00:01:00Z
  checked: .planning/phases/02-yad2-scraper-llm-pipeline/02-DEVTOOLS-FINDINGS.md
  found: "Status: HYPOTHESIS — not directly confirmed from Network tab." for feed endpoint path. The file explicitly says `feed-search/realestate/rent` was never confirmed from DevTools.
  implication: The URL in config.py is a hypothesis that was tested and found wrong (404). The canonical Yad2 internal API path known from community research and CLAUDE.md is `feed/realestate/rent`.

- timestamp: 2026-04-02T00:01:00Z
  checked: /Users/shahafwieder/Library/Python/3.9/lib/python/site-packages/playwright_stealth/__init__.py
  found: "from playwright_stealth.stealth import Stealth, ALL_EVASIONS_DISABLED_KWARGS" — that is the entire public API. No `stealth_async` function exported.
  implication: The installed playwright_stealth is a newer version (2.x) where the API changed from standalone `stealth_async(page)` function to `Stealth().apply_stealth_async(page)` method. yad2.py line 145 imports the old API name which does not exist.

- timestamp: 2026-04-02T00:01:00Z
  checked: /Users/shahafwieder/Library/Python/3.9/lib/python/site-packages/playwright_stealth/stealth.py lines 239-242
  found: `async def apply_stealth_async(self, page_or_context)` — this is the correct async method on the Stealth class.
  implication: Fix is: replace `from playwright_stealth import stealth_async` + `await stealth_async(page)` with `from playwright_stealth import Stealth` + `await Stealth().apply_stealth_async(page)`.

- timestamp: 2026-04-02T00:01:00Z
  checked: backend/app/config.py line 22
  found: yad2_api_base_url default = "https://gw.yad2.co.il/feed-search/realestate/rent"
  implication: This is where the 404 URL originates. Must be changed to "https://gw.yad2.co.il/feed/realestate/rent".

- timestamp: 2026-04-02T00:02:00Z
  checked: backend/app/scrapers/yad2.py line 156 (Playwright fallback wait_until)
  found: wait_until="networkidle" with timeout=30000 — networkidle waits for all network requests to settle, which never happens on a heavy SPA like Yad2.
  implication: Playwright times out before the page is usable. Fix: change to wait_until="load" with timeout=60000. The "load" event fires when the DOM + subresources are loaded, which is sufficient for HTML extraction.

- timestamp: 2026-04-02T00:02:00Z
  checked: backend/app/scrapers/yad2.py lines 355-359 (Playwright fallback URL construction)
  found: Fallback URL uses `?city={settings.yad2_city_code}&price=0-{settings.yad2_price_max}` — params `city` and `price` do not match Yad2 frontend URL params. User's actual browser URL uses `area=5`, `maxPrice=4500`, `minRooms=2.5`, `maxRooms=3`, `property=...`, path `/realestate/rent/coastal-north`.
  implication: Wrong URL params mean Yad2 may serve a default page or 404 instead of the filtered listing page. Fix: update fallback URL to match user's actual browser URL format.

- timestamp: 2026-04-02T00:03:00Z
  checked: backend/app/scrapers/yad2.py _parse_html_listings (line 104) and run_yad2_scraper neighborhood filter (line 371)
  found: (1) CSS selectors `[data-testid='feed-item'], .feeditem, .feed-item, [class*='feedItem']` are unverified guesses — Yad2 is a React SPA, listing data is almost certainly in an embedded <script> JSON blob, not selectable DOM cards. (2) Neighborhood filter at line 371 runs on every item and checks `neighborhood`/`city` fields — but the HTML parser only sets `title_1`, `price`, `street` (if found) — `neighborhood` and `city` are never set, so `location_text` is either empty or just a street string with no neighborhood keywords, causing EVERY item to be discarded even if the card selectors had found something. (3) Items are further gated by `item.get("id")` at line 136 — the link extractor uses `/item/` pattern which may not match Yad2's current URL structure.
  implication: Two independent failures: wrong extraction method (CSS vs embedded JSON) + neighborhood filter discards everything from HTML path. Fix requires: (a) replace CSS parser with embedded-JSON extractor, (b) handle neighborhood filter correctly for HTML-sourced items (neighborhood unknown — should not filter out, or extract from JSON).

- timestamp: 2026-04-02T00:04:00Z
  checked: /tmp/yad2_debug.html — actual HTML received by Playwright from Yad2
  found: The entire 19KB page is a ShieldSquare/Radware bot-detection CAPTCHA page with hCaptcha challenge ("Are you for real?"). Title: "אבטחת אתר | יד2". No listing data present. The page asks the user to solve a captcha to proceed. This is served even with Playwright+stealth+headless=True.
  implication: This is the actual root cause of listings_found=0 — the scraper is not parsing wrong selectors, it is receiving a bot-challenge page with zero listing content. The Playwright+stealth combination is not sufficient to bypass Yad2's Radware ShieldSquare protection in headless mode. Fix options: (A) use headless=False (headed mode with Xvfb on Linux) which is harder for bot detection, (B) intercept the XHR API call directly inside the browser page context rather than parsing HTML, (C) maintain a logged-in session with a real browser-obtained cookie, (D) use a different approach for the Playwright browser fingerprint.

- timestamp: 2026-04-02T00:10:00Z
  checked: backend/.env (existence) and backend/app/config.py llm_api_key field
  found: No .env file existed. config.py defines `llm_api_key: str = ""`. pydantic-settings maps this to env var LLM_API_KEY. get_llm_client() passes api_key=settings.llm_api_key — empty string is passed to AsyncAnthropic, which raises auth error.
  implication: User must create backend/.env and set LLM_API_KEY to their real Anthropic API key. File created with placeholder.

- timestamp: 2026-04-02T00:10:00Z
  checked: backend/app/scrapers/yad2.py Step 4 (lines 540-547) and backend/app/llm/verifier.py verify_listing error handler
  found: verify_listing catches all exceptions and returns {is_rental=False, rejection_reason="LLM error: ..."}. Pipeline Step 4 checks only `is_rental=False` and increments listings_rejected for both real rejections and LLM errors — no distinction.
  implication: Any auth/network/rate-limit error causes all scraped listings to be rejected and not inserted. Fixed by checking rejection_reason prefix "LLM error:" and routing those to flagged+insert(confidence=0.0) instead.

## Resolution

root_cause: |
  Eight independent bugs across multiple sessions:
  1. config.py yad2_api_base_url used unverified hypothesis path `/feed-search/realestate/rent` — returns HTTP 404. Fixed to `/feed/realestate/rent` in session 1.
  2. yad2.py imported `stealth_async` from `playwright_stealth` — this function does not exist in the 2.x API. Fixed to `Stealth().apply_stealth_async(page)` in session 1.
  3. Playwright fallback used `wait_until="networkidle"` — Yad2 is a heavy SPA that never reaches networkidle, causing 30s timeout. Fixed to `wait_until="load"` with 60s timeout.
  4. Playwright fallback URL used wrong params (`city=4000&price=0-4500`) — Yad2 frontend uses `area=5`, `maxPrice=4500`, `minRooms`, `maxRooms`, `property`, path `/realestate/rent/coastal-north`. Fixed to match user's actual browser URL.
  5. headless=True triggers Yad2's Radware ShieldSquare bot detection — a hCaptcha challenge page (19KB) is returned instead of listing data. Fixed to headless=False with persistent browser profile at ~/.yad2-browser-profile so cookies survive between runs.
  6. _parse_html_listings used CSS card selectors — Yad2 is a Next.js SSR app, listing data is embedded in a <script id="__NEXT_DATA__"> JSON blob (confirmed from live 1.7MB page). CSS selectors found 0 cards. Replaced with _flatten_nextdata_item extractor reading props.pageProps.feed.{private,agency,platinum,...} arrays and flattening nested address/additionalDetails/metaData objects into parse_listing's expected flat shape. Also added lat/lng coordinates extracted from address.coords.lat/lon and mapped to Listing model columns.
  7. backend/.env did not exist — pydantic-settings reads LLM_API_KEY for settings.llm_api_key, but the file was absent so the field defaulted to "". anthropic.AsyncAnthropic(api_key="") raises "Could not resolve authentication method" auth error. Fixed by creating backend/.env with LLM_API_KEY placeholder.
  8. LLM errors treated as content rejections — pipeline Step 4 in run_yad2_scraper checked only `is_rental=False`, with no distinction between "LLM decided this is not a rental" and "LLM call failed (auth error, network error, rate limit)". Both paths incremented listings_rejected. Fixed: rejection_reason starting with "LLM error:" now routes to listings_flagged and inserts the listing with llm_confidence=0.0 for manual review.

fix: |
  1. config.py: yad2_api_base_url = "https://gw.yad2.co.il/feed/realestate/rent" (session 1)
  2. yad2.py: stealth import changed to `from playwright_stealth import Stealth` + `await Stealth().apply_stealth_async(page)` (session 1)
  3. yad2.py: wait_until="load", timeout=60000
  4. yad2.py: fallback URL = "https://www.yad2.co.il/realestate/rent/coastal-north?maxPrice=4500&minRooms=2.5&maxRooms=3&imageOnly=1&priceOnly=1&property=1%2C3%2C5%2C6%2C39%2C32%2C55&area=5"
  5. yad2.py: headless=False + launch_persistent_context with user_data_dir=~/.yad2-browser-profile; captcha detection logs warning and waits 90s for manual solve
  6. yad2.py: _flatten_nextdata_item() added; _parse_html_listings() now extracts from __NEXT_DATA__ JSON first; parse_listing() updated to map lat/lng to DB columns
  7. Created backend/.env with LLM_API_KEY placeholder; user must add real Anthropic API key value
  8. yad2.py Step 4: added rejection_reason prefix check — "LLM error:" prefix routes to flagged+insert, not rejected+skip

verification: |
  - Unit tests: 17/17 pass (previous sessions)
  - Fix 8 code change reviewed: logic is correct and isolated
  - Fix 7: .env file created with correct variable name LLM_API_KEY matching pydantic-settings field name llm_api_key
  - End-to-end CONFIRMED by user (2026-04-02):
      "[yad2] httpx failed (...404...) — falling back to Playwright"
      "[yad2] Bot-detection CAPTCHA detected. Waiting up to 90 seconds..."
      "ScraperResult(source='yad2', listings_found=4, listings_inserted=4, listings_skipped=0, listings_rejected=0, listings_flagged=0, errors=[], success=True)"
      listings_found=4, listings_inserted=4 — full pipeline working end-to-end.
files_changed:
  - backend/app/config.py
  - backend/app/scrapers/yad2.py
  - backend/.env (created)
