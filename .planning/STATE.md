---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: verifying
stopped_at: Completed 06-01 (Madlan Scraper Core + Scheduler Integration) — Phase 06 complete
last_updated: "2026-04-03T09:17:37.992Z"
last_activity: 2026-04-03
progress:
  total_phases: 8
  completed_phases: 6
  total_plans: 17
  completed_plans: 17
  percent: 67
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-28)

**Core value:** New Haifa rental listings from all sources appear on a single live map every morning — no manual searching required.
**Current focus:** Phase 06 — madlan-scraper

## Current Position

Phase: 06 (madlan-scraper) — EXECUTING
Plan: 1 of 1
Status: Phase complete — ready for verification
Last activity: 2026-04-03

Progress: [██████░░░░] 67%

## Performance Metrics

**Velocity:**

- Total plans completed: 2
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: none yet
- Trend: -

*Updated after each plan completion*
| Phase 01-foundation P01 | 5min | 2 tasks | 19 files |
| Phase 01-foundation P02 | 2min | 2 tasks | 14 files |
| Phase 02-yad2-scraper-llm-pipeline P01 | 30 | 3 tasks | 9 files |
| Phase 02-yad2-scraper-llm-pipeline P03 | 10 | 1 tasks | 2 files |
| Phase 02-yad2-scraper-llm-pipeline P02 | 6 | 2 tasks | 2 files |
| Phase 03-rest-api-scheduler P01 | 1 | 2 tasks | 6 files |
| Phase 04-map-web-ui P01 | 3 | 2 tasks | 12 files |
| Phase 04-map-web-ui P02 | 5 | 2 tasks | 7 files |
| Phase 04-map-web-ui P03 | 5 | 1 tasks | 5 files |
| Phase 04-map-web-ui P04 | 10 | 2 tasks | 0 files |
| Phase 05-geocoding-dedup-neighborhoods P05-01 | 3 | 3 tasks | 4 files |
| Phase 05-geocoding-dedup-neighborhoods P05-02 | 3 | 3 tasks | 3 files |
| Phase 05-geocoding-dedup-neighborhoods P05-03 | 4 | 3 tasks | 3 files |
| Phase 06-madlan-scraper P01 | 21 | 2 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Stack confirmed — Python/FastAPI/SQLite/APScheduler backend; React+Vite+Tailwind+React-Leaflet frontend; Playwright+stealth for all scrapers (including Yad2/Madlan, not just Facebook)
- [Roadmap]: Facebook scrapers deferred to Phase 8 — core app must be fully functional on Yad2+Madlan alone
- [Roadmap]: LLM verification co-located with Phase 2 (first scraper) to validate pipeline end-to-end before API or UI depend on it
- [Phase 01-foundation]: Used latest available PyPI versions (fastapi==0.128.8, alembic==1.16.5, pydantic==2.12.5) — plan research referenced future unreleased versions
- [Phase 01-foundation]: Alembic render_as_batch=True required in env.py for SQLite ALTER TABLE compatibility
- [Phase 01-foundation]: React 19 + Vite 8 + Tailwind v4 used (not older CLAUDE.md floor versions); Tailwind v4 CSS-based config (@import tailwindcss + @theme), no tailwind.config.js
- [Phase 01-foundation]: Docker Compose multi-file: base defines services; dev adds hot-reload; prod adds Nginx+Certbot SSL termination
- [Phase 01-foundation]: VPS provider = DigitalOcean EU (Amsterdam/Frankfurt) using $200 GitHub Student Pack credit. Israeli IP not required — Facebook Marketplace geo-filtering is URL-based, not IP-enforced. Israeli proxy deferred to Phase 8 if needed in practice.
- [Phase 01-foundation]: Droplet size = $6/mo (1 CPU, 1GB RAM, 25GB SSD) + 2GB swap file to handle Playwright memory spikes. Upgrade to $12/mo if needed.
- [Phase 02-yad2-scraper-llm-pipeline]: Yad2 feed endpoint hypothesis kept as-is (gw.yad2.co.il/feed-search/realestate/rent) — to verify at runtime
- [Phase 02-yad2-scraper-llm-pipeline]: Dual neighborhood filter strategy: API param neighborhood=609 for כרמל (confirmed), post-scrape address.neighborhood.text match for מרכז העיר and נווה שאנן (codes unknown)
- [Phase 02-yad2-scraper-llm-pipeline]: Yad2 guest_token JWT cookie required for API access — Plan 02 must acquire before calling feed endpoint
- [Phase 02-yad2-scraper-llm-pipeline]: get_llm_client() factory function extracted for mockability — tests patch this instead of anthropic module directly
- [Phase 02-yad2-scraper-llm-pipeline]: AsyncAnthropic used for non-blocking event loop behavior inside asyncio.gather batch calls
- [Phase 02-yad2-scraper-llm-pipeline]: output_config.format json_schema for structured LLM output — no retry logic needed
- [Phase 02-yad2-scraper-llm-pipeline]: guest_token preflight: GET yad2.co.il/realestate/rent before feed API to acquire JWT cookie — best-effort, continues without on failure
- [Phase 02-yad2-scraper-llm-pipeline]: from __future__ import annotations added to yad2.py for Python 3.9 union type syntax compatibility
- [Phase 03-rest-api-scheduler]: APScheduler embedded in FastAPI lifespan with deferred imports in job function to avoid circular dependencies
- [Phase 03-rest-api-scheduler]: GET /api/health returns per-source scraper state (last_run, listings_inserted, success) from in-memory _health dict
- [Phase 04-map-web-ui]: MapView empty state: absolute overlay on map container at z-index 1000 (map still renders behind)
- [Phase 04-map-web-ui]: MapView owns all filter/sheet state internally (showFilters, filters) — selectedListing removed; listing detail now rendered inside Leaflet <Popup> component, not a custom bottom sheet
- [Phase 04-map-web-ui]: Multiple neighborhood selections result in no neighborhood filter (API takes single value)
- [Phase 04-map-web-ui]: FavoritesView fetches data via useListings({ is_favorited: true }) — same hook as MapView, no new query pattern needed
- [Phase 04-map-web-ui]: BottomNav rendered outside Routes in App.jsx so it persists across all route transitions
- [Phase 04-map-web-ui]: Listing detail uses Leaflet native <Popup> (not custom bottom sheet) — avoids all event propagation complexity; ListingSheet is a compact popup card (max 320×420px) with image carousel and swipe support
- [Phase 04-map-web-ui]: All pin icons wrapped in 44×44px transparent hit area div for reliable mobile tap targets while keeping visual indicator small
- [Phase 04-map-web-ui]: Vite API proxy target changed from localhost:8000 to http://backend:8000 (Docker service hostname) with VITE_API_URL env override; docker-compose.dev.yml frontend service now has explicit build config
- [Phase 04-map-web-ui]: No code changes required in plan 04 — integration passed verification without fixes; human checkpoint approved on first pass
- [Phase 05-geocoding-dedup-neighborhoods]: test_merkaz_center adjusted to lng=35.025 to avoid bbox overlap with כרמל (bounding boxes overlap at lat=32.825, lng=35.00-35.02)
- [Phase 05-geocoding-dedup-neighborhoods]: Nominatim 'lon' string-to-float cast documented prominently — cast is mandatory as Nominatim JSON returns strings not numbers
- [Phase 05-geocoding-dedup-neighborhoods]: Google Maps Playwright fallback uses http:// when Bright Data proxy is enabled (proxy handles SSL termination)
- [Phase 05-geocoding-dedup-neighborhoods]: Dedup canonical is first-inserted (lowest id) per D-09 — deterministic and stable across reruns
- [Phase 05-geocoding-dedup-neighborhoods]: Geocoders fail in Docker without internet but pipeline handles gracefully — lat stays NULL, retry on next pass
- [Phase 06-madlan-scraper]: Madlan PerimeterX+Cloudflare blocks datacenter IPs — scraper requires Bright Data proxy or residential IP in production; listing URL pattern /listings/{id} confirmed via public sitemap
- [Phase 06-madlan-scraper]: Three-strategy extraction for Madlan: XHR interception (primary) → __NEXT_DATA__ (secondary) → DOM parsing (tertiary); parse_listing() handles both nested address.neighborhood.text and flat field structures

### Pending Todos

- ACTION REQUIRED: Submit Twilio WhatsApp message template to Meta for approval during Phase 1 — approval takes days to weeks and blocks Phase 7. Template: "{{count}} new listings found in Haifa. Open app: {{url}}"

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260402-uad | Integrate Bright Data Web Unlocker proxy into Yad2 scraper for CAPTCHA bypass | 2026-04-02 | ff5a1f5 | [260402-uad-integrate-bright-data-web-unlocker-proxy](./quick/260402-uad-integrate-bright-data-web-unlocker-proxy/) |
| 260402-v7j | Increase Yad2 Playwright scraper listing yield via scroll-to-load loop | 2026-04-02 | 00c47a2 | [260402-v7j-increase-yad2-playwright-scraper-listing](./quick/260402-v7j-increase-yad2-playwright-scraper-listing/) |

### Blockers/Concerns

- [Pre-Phase 2] Yad2 internal API endpoint URL and parameters must be verified via browser DevTools before writing the scraper — training data may be stale
- [Pre-Phase 6] Madlan API/GraphQL shape is low-confidence and requires network inspection at build time
- [Pre-Phase 8] Facebook DOM and stealth requirements evolve; run targeted research immediately before Phase 8 implementation
- [Pre-Phase 8] Israeli VPS must be provisioned (or confirmed) before Facebook Marketplace testing — geo-restriction requires Israeli IP

## Session Continuity

Last session: 2026-04-03T09:17:37.989Z
Stopped at: Completed 06-01 (Madlan Scraper Core + Scheduler Integration) — Phase 06 complete
Resume file: None
