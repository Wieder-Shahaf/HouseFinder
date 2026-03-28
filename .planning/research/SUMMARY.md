# Project Research Summary

**Project:** ApartmentFinder
**Domain:** Personal apartment listing aggregator — web scraping, interactive map, Israeli real estate (Haifa)
**Researched:** 2026-03-28
**Confidence:** MEDIUM (stack HIGH; Facebook scraping MEDIUM; Madlan API LOW)

## Executive Summary

ApartmentFinder is a scraping-based personal tool for a single user in Haifa, Israel. The expert pattern for this class of product is a unidirectional pipeline: scheduled scrapers write normalized listings to a database, a REST API serves them to a React frontend, and a notification service fires on new matches. The entire stack should be Python on the backend (FastAPI + SQLAlchemy + APScheduler) with React + Vite + Tailwind on the frontend — this is the shortest path to working Hebrew RTL support, Playwright-based scraping, and WhatsApp notifications in a single maintainable codebase.

The most important architectural decision is to treat the storage and deduplication layer as the single source of truth from day one. Every downstream concern — map pins, notifications, seen/favorites state — depends on a clean, deduplicated listings table. The schema must handle address normalization, cross-source dedup fingerprinting, and geocoded coordinates before any scraper is written. Getting the schema wrong means rewriting it later under load.

The highest-risk component by a significant margin is Facebook scraping. Facebook actively detects and blocks headless browsers, sessions expire silently, and group content requires a fully authenticated and geo-appropriate account. This component should be built last, isolated from the rest of the pipeline, and treated as "best-effort" — the core app must be fully functional without it using only Yad2 and Madlan. A secondary risk is WhatsApp template approval: Meta requires pre-approved message templates for notifications sent outside a 24-hour session window. Template submission must happen at project start, not at the end of development.

---

## Key Findings

### Recommended Stack

The backend is Python throughout: FastAPI as the API server, SQLAlchemy 2.0 (async) as the ORM, SQLite as the database (zero-ops, sufficient for single-user scale), Alembic for migrations, APScheduler embedded in the FastAPI process for cron-style scraping, Playwright for all browser-based scraping, and httpx for direct API calls against Yad2/Madlan JSON endpoints. The Twilio Python SDK handles WhatsApp notifications.

The frontend is React 18 + Vite 5, styled with Tailwind CSS (which has native RTL variant support via `rtl:` and logical margin utilities). Maps use React-Leaflet 4.x over OpenStreetMap tiles — free, MIT-licensed, and OSM tiles already include Hebrew labels for Israeli cities and streets. TanStack Query handles server-state caching. The entire stack runs in Docker Compose with a volume-mounted SQLite file.

**Core technologies:**
- Python 3.12 + FastAPI 0.111+: primary backend runtime — dominant ecosystem for scraping and async APIs
- SQLite 3.45+ via SQLAlchemy 2.0 + aiosqlite: zero-ops database — adequate for single-user; trivial migration to Postgres later
- Alembic 1.13+: schema migrations — keeps DB changes reproducible
- APScheduler 3.10+: in-process cron scheduler — no Redis/Celery overhead needed at this scale
- Playwright 1.44+ (Python) + playwright-stealth: browser automation — required for Facebook and JS-heavy Israeli sites
- httpx 0.27+: async HTTP client — for Yad2/Madlan JSON API calls (faster than full browser when it works)
- Twilio Python SDK 9.0+: WhatsApp notifications — only reliable option; unofficial alternatives are broken
- React 18 + Vite 5: frontend — best RTL/Hebrew ecosystem, fastest dev server
- Tailwind CSS 3.4+: styling — native `rtl:` variants eliminate need for a separate RTL library
- React-Leaflet 4.2+ + Leaflet 1.9+: map display — free OSM tiles, Hebrew labels, MIT licensed
- TanStack Query 5.x: server-state management — keeps listing data fresh without manual polling

**What NOT to use:** PostgreSQL (unnecessary ops overhead for single user), Celery + Redis (overkill for hourly scraping), `facebook-scraper` library (broken since 2024), `whatsapp-web.js` / `pywhatkit` (unofficial, routinely broken), Google Maps (billing required; OSM is free).

### Expected Features

**Must have (table stakes):**
- Periodic background scraping of Yad2 and Madlan — app has no value without listings
- Listing storage with deduplication across sources — same apartment posted on multiple platforms creates map clutter
- Geocoding pipeline (address string to lat/lng) — required for map pin placement and neighborhood filtering
- Interactive map with all listings as pins, clustered at zoom-out — primary navigation surface
- Default filters on load: rent ≤ 4,500 ₪, 2.5–3.5+ rooms — without this, irrelevant listings dominate
- Listing card showing price, rooms, size, contact info, post date, source, and source URL
- Mark "seen" to mute/hide reviewed listings — single most important daily-use interaction
- Favorites / bookmarking for shortlisted listings
- WhatsApp or web push notification when a new listing matches active filters
- Mobile-responsive Hebrew UI with full RTL layout — primary usage context is a smartphone browser

**Should have (differentiators):**
- Source badge ("יד2", "מדלן", "פייסבוק") — landlord-direct listings from Facebook mean no agency fee
- "New today" / "חדש" visual distinction on pins and cards — reinforces morning review habit
- Listing age indicator ("פורסם לפני 3 שעות")
- Price-per-sqm display (where size is available)
- Scraper status dashboard (last run per source, error flags) — critical for self-debugging
- Facebook group and Marketplace scraping — highest-value differentiator but highest-risk component

**Defer to v2+:**
- Neighborhood heatmap
- Contact history log
- Manual listing add (paste URL)
- Smart dedup confidence score (debugging tool only)
- Filter by floor (when floor data is available)

**Never build:** User auth, multi-user support, automated messaging to landlords, native iOS/Android app, price history charts, server-side rendering for SEO.

### Architecture Approach

The system is a five-component unidirectional pipeline: Scraper Workers fetch raw listings and write normalized records to the database; the Scheduler (APScheduler embedded in FastAPI) triggers scrapers on a configurable interval; the Storage + Dedup Layer owns the canonical listing record and enforces deduplication via a UNIQUE constraint on `(source, source_id)` plus a proximity-based cross-source dedup query; the REST API serves listings to the frontend and hosts the scheduler; and the Map Web UI is a dumb display layer that reads only from the API. The Notification Service is triggered as a post-scrape hook inside the backend. There is no bidirectional coupling between scrapers and the frontend.

**Major components:**
1. Scraper Workers — one per source (Yad2, Madlan, Facebook Groups, Facebook Marketplace); each fully isolated with its own try/except; failure in one does not block others
2. APScheduler (in FastAPI process) — triggers scraper runs every 2 hours; enforces `max_instances=1` per job to prevent overlap; tracks run timestamps in DB
3. Storage + Dedup Layer — `listings` table with UNIQUE `(source, source_id)` index; Level 1 dedup via idempotent inserts; Level 2 cross-source dedup via proximity query (same price + rooms + lat/lng within 100m)
4. FastAPI REST API — thin read/write layer over DB; hosts scheduler; no scraping logic; key endpoints: `GET /listings` (with filter params), `PUT /listings/{id}/seen`, `PUT /listings/{id}/favorited`, `GET /health`
5. React Map UI — React-Leaflet map with clustered pins; listing card on tap; RTL layout set at `<html dir="rtl" lang="he">` root; all filter logic lives in the API, not the frontend
6. Notification Service — called by backend post-scrape; sends Twilio WhatsApp message with new listing count and app URL

### Critical Pitfalls

1. **Facebook session expiry is silent** — the scraper lands on a login redirect and returns zero listings with no error. Prevention: after every Facebook scrape run, check if the page URL contains "login" or "checkpoint"; alert via WhatsApp immediately; never use your primary Facebook account for scraping; store last-successful-scrape timestamp and alert if gap exceeds 2x the scrape interval.

2. **WhatsApp template approval blocks notifications** — Twilio WhatsApp API requires Meta-approved message templates for outbound messages outside a 24-hour session window. Template approval takes days to weeks. Prevention: submit a simple notification template ("{{count}} new listings found. Open app: {{url}}") at the very start of the project; use the Twilio Sandbox during development; build Web Push as a fallback that requires no approval.

3. **Yad2 and Madlan use TLS fingerprinting (JA3) to detect bots** — a simple `requests` or `httpx` call with a spoofed User-Agent gets an immediate 403 or Cloudflare challenge. Prevention: use Playwright with `playwright-stealth` from the start for these sites; never attempt plain HTTP scraping first; add 2–8 second random delays between requests.

4. **Address variation breaks cross-source deduplication** — "רחוב הנביאים 14, חיפה" and "הנביאים 14 חיפה" are the same address but fail exact-string matching. Prevention: build a normalization function (strip common prefixes, extract street number separately) before the first scraper run; use geocoded lat/lng proximity as the primary cross-source dedup key, not the raw address string; design the dedup schema before writing any scraper.

5. **Deferred Facebook complexity is easy to underestimate** — Facebook Marketplace geo-restricts results to accounts with a matching city; fresh scraper accounts return zero results; headless browser detection is aggressive and evolving. Prevention: configure the scraper Facebook account with Haifa as home city; host on an Israeli VPS or route scraping traffic through an Israeli IP; build Facebook scrapers as the last phase, fully isolated, with a fallback path when they fail.

---

## Implications for Roadmap

Based on research, the dependency chain is unambiguous: storage schema must exist before any scraper; geocoding must exist before the map; the API must exist before the frontend; notifications depend on the full pipeline. The suggested phases below respect these dependencies and front-load the lowest-risk work.

### Phase 1: Foundation — DB Schema, Migrations, and Dev Environment

**Rationale:** Every other component depends on the listings table. Schema design is the hardest thing to change later (especially dedup fingerprinting and geocoding columns). All other work is blocked until this is done. Docker Compose setup here means consistent environments from day one.
**Delivers:** SQLite DB with full listings schema (including `source`, `source_id`, `lat`, `lng`, `is_seen`, `is_favorited`, `raw_data`); Alembic migration pipeline; Docker Compose stack; `.env` config pattern for secrets.
**Addresses:** Listing storage, deduplication foundation.
**Avoids:** Hebrew encoding pitfall (set UTF-8 from first migration); dedup schema pitfall (design canonical fingerprint before first insert).

### Phase 2: First Scraper — Yad2

**Rationale:** Yad2 is the most accessible source (structured, potential JSON API via httpx). Building one scraper end-to-end validates the normalization pipeline, the dedup logic, and the schema before investing in harder sources. This phase also produces the first real data.
**Delivers:** Working Yad2 scraper writing normalized listings to DB; Level 1 dedup (idempotent inserts on `(source, source_id)`); price and room count normalization module with unit tests; address normalization stub.
**Addresses:** Periodic scraping (Yad2), listing storage, deduplication.
**Avoids:** TLS fingerprinting pitfall (use Playwright + stealth from the start, even if httpx works initially — builds the right pattern); price parsing pitfall (dedicated `parsePrice()` utility with tests); room count convention pitfall (store חדרים values as-is, never convert to bedrooms).

### Phase 3: REST API + Scheduler

**Rationale:** The frontend and notification service both depend on the API. APScheduler embedded in FastAPI collocates the scheduler with the backend, eliminating a separate infrastructure component. This phase also wires the Yad2 scraper to a schedule, producing the first automatically-refreshed data.
**Delivers:** FastAPI server with `GET /listings` (filter params: price, rooms, neighborhood, since, seen, favorited), `PUT .../seen`, `PUT .../favorited`, `GET /health` (last run timestamps per source); APScheduler running Yad2 scraper every 2 hours; job lock preventing overlapping runs.
**Addresses:** Periodic scheduling, scraper status/health visibility.
**Avoids:** Overlapping scrape runs (add `max_instances=1` and job lock in this phase, not as a patch later).

### Phase 4: Map Web UI (MVP)

**Rationale:** The map is the core user interface. Building it against real Yad2 data (from Phase 2) means immediately testing against actual Hebrew addresses, prices, and listing volumes — not synthetic fixtures.
**Delivers:** React + Vite app; React-Leaflet map with clustered pins; listing card on tap (price, rooms, size, contact, source, date); default filters applied on load (≤ 4,500 ₪, 2.5–3.5+ rooms); RTL layout (`dir="rtl" lang="he"` on `<html>`, Tailwind `rtl:` variants throughout); mark seen on tap; Tailwind CSS with Noto Sans Hebrew font.
**Addresses:** Interactive map, default filters, listing card, seen marking, Hebrew RTL UI, mobile-responsive layout.
**Avoids:** Mixed bidi rendering pitfall (wrap each card field in `dir="rtl"`; use `direction: ltr` on phone number spans; use `unicode-bidi: isolate` on numeric elements); iOS Safari input pitfall (test on real iPhone, set `direction: ltr` on number inputs); map pin performance pitfall (use `react-leaflet-cluster` from day one — not as a later optimization).

### Phase 5: Geocoding Pipeline

**Rationale:** Geocoding unlocks neighborhood filtering and accurate cross-source dedup (proximity-based). It is deferred until after the basic map works so the map can display listings immediately (with null coordinates handled gracefully as list-only items), and geocoding can be added as an async background task.
**Delivers:** Nominatim geocoding via FastAPI background task (async, non-blocking); geocode-once-and-cache pattern (never re-geocode a resolved address); neighborhood assignment from geocoded coordinates (bounding boxes for Carmel, Downtown/Merkaz, Neve Shanan); Level 2 cross-source dedup (proximity query: same price + rooms + lat/lng within 100m).
**Addresses:** Haifa neighborhood filter, cross-source dedup, map pin placement for listings with address-only data.
**Avoids:** Geocoding quota pitfall (cache in DB; deduplicate addresses before geocoding); geocoding-on-insert pitfall (always async/deferred, never inline in the scrape transaction).

### Phase 6: Madlan Scraper

**Rationale:** Madlan adds a second structured source with minimal auth complexity compared to Facebook. Building it after the full pipeline exists means the scraper only needs to conform to the normalization interface already validated by Yad2.
**Delivers:** Working Madlan scraper (Playwright with `networkidle` wait); Madlan-specific CSS selectors isolated in their own module; integrated into APScheduler and health dashboard.
**Addresses:** Periodic scraping (Madlan), source badge differentiation.
**Avoids:** Madlan JS-rendering pitfall (always wait for `networkidle`, never parse initial DOM immediately); Madlan internal API pitfall (scrape rendered page content, not reverse-engineered API calls that will break on key rotation).

### Phase 7: Notifications (WhatsApp + Web Push)

**Rationale:** Notifications depend on the full pipeline being reliable and the "new listing detection" logic being solid (listings that pass active filters and haven't been seen). WhatsApp template must be submitted at project start as a long-lead item, but the integration code is built here.
**Delivers:** WhatsApp notification via Twilio after each scrape run that finds new matching listings; pre-approved message template ("{{count}} new listings found in Haifa. Open app: {{url}}"); Web Push via PWA service worker as fallback; Twilio Sandbox used during development.
**Addresses:** WhatsApp/push notification requirement.
**Avoids:** WhatsApp 24-hour window pitfall (submit template during Phase 1 infrastructure setup; build Web Push as primary fallback).

### Phase 8: Facebook Scrapers (Groups + Marketplace)

**Rationale:** Facebook is the highest-risk, highest-complexity component. It is built last so that a failure or ongoing maintenance burden does not block the rest of the app. The core value proposition is fully delivered without Facebook; this phase adds landlord-direct listings.
**Delivers:** Facebook Groups scraper (Playwright + stealth + persistent session cookie); Facebook Marketplace scraper (separate scraper class, different DOM); session health-check sentinel (detect login redirect and fire WhatsApp alert); scraper account configured with Haifa as home city; deployment on Israeli VPS or Israeli IP routing.
**Addresses:** Facebook group/Marketplace scraping requirement.
**Avoids:** Session expiry silent failure pitfall (health-check is part of this phase, not an afterthought); Facebook geo-restriction pitfall (Israeli VPS + Haifa account configured before any testing); Facebook Marketplace auth flow pitfall (treat as separate scraper class from day one); pinned post noise pitfall (check for Facebook post ID existence before insert — Level 1 dedup handles this).

### Phase 9: Polish and Hardening

**Rationale:** A cleanup phase after all functional components are live. Addresses UX rough edges, scraper robustness, and configurable settings.
**Delivers:** Favorites view with distinct pin color; scraper status dashboard (last run per source, listing count per run, error count); configurable filters persisted in localStorage; scrape interval configurable via environment variable; hard timeout per scraper source (15 min max); mobile UI final pass; "new today" / "חדש" badge on recent listings; listing age display.
**Addresses:** Scraper health dashboard, favorites view, mobile polish, source badge, new-today indicator.

### Phase Ordering Rationale

- Storage before scrapers: the schema is the contract every other component satisfies; changing it after data exists requires migrations under load.
- First scraper before API: real data validates the normalization pipeline before the frontend depends on it.
- API before frontend: the frontend is a display layer only; it must never contain business logic that duplicates backend filtering.
- Geocoding after basic map: the map can render lists without coordinates; geocoding as async background task does not block the user-facing MVP.
- Madlan before Facebook: Madlan is a structured site that only requires Playwright patience; Facebook requires auth infrastructure, account management, and ongoing maintenance.
- Notifications after pipeline: notification correctness depends on reliable scraping and dedup; building notifications on top of an unstable pipeline produces false positives.
- Facebook last: isolates the highest-risk component; app is fully functional without it.

### Research Flags

Phases likely needing deeper per-phase research during planning:
- **Phase 2 (Yad2 scraper):** Yad2's internal API endpoints must be reverse-engineered from the network tab at build time — training data may be stale. Verify API URL and parameter schema before writing scraper code.
- **Phase 6 (Madlan scraper):** Madlan's API/GraphQL shape is low-confidence and must be discovered at build time. High likelihood of needing a research pass before implementation.
- **Phase 7 (Notifications):** Twilio WhatsApp Sandbox approval flow and current template requirements should be verified against current Twilio documentation. Web Push service worker patterns are well-documented.
- **Phase 8 (Facebook):** Facebook's DOM structure, group access policies, and stealth requirements evolve continuously. A targeted research pass immediately before implementation is strongly recommended.

Phases with standard, well-documented patterns (skip research-phase):
- **Phase 1 (Foundation):** SQLAlchemy + Alembic + SQLite setup is thoroughly documented and stable.
- **Phase 3 (API + Scheduler):** FastAPI + APScheduler lifespan integration is well-documented with official examples.
- **Phase 4 (Map UI):** React-Leaflet + Tailwind RTL is a known, stable pattern.
- **Phase 5 (Geocoding):** Nominatim + async FastAPI background tasks is standard.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core choices (Python, FastAPI, SQLite, React, Tailwind, Leaflet, Twilio) are stable and widely used. Facebook stealth patterns are MEDIUM — they evolve. |
| Features | HIGH | Table stakes and anti-features are clear from Israeli real estate UX conventions and project requirements. Scraper-specific details need verification at build time. |
| Architecture | HIGH | Unidirectional pipeline pattern is well-established for this class of app. APScheduler-in-FastAPI is documented. Component boundaries are clear. |
| Pitfalls | HIGH for most | WhatsApp 24hr window, Facebook session expiry, TLS fingerprinting, and dedup address variation are all well-documented failure modes. Facebook Marketplace geo-restriction and Madlan API specifics are MEDIUM. |

**Overall confidence:** MEDIUM-HIGH — the architecture and stack decisions are solid; the main uncertainty is in scraper-specific implementation details (Yad2 API shape, Madlan API shape, Facebook DOM and anti-bot measures) that require validation at build time.

### Gaps to Address

- **Yad2 API endpoint:** The exact URL and parameter schema for `gw.yad2.co.il` must be verified via browser DevTools Network tab at build time. Training data is from mid-2025 and may be stale.
- **Madlan API/GraphQL shape:** Low-confidence; requires manual network inspection before scraper implementation begins. May require Playwright page scraping rather than API calls if the endpoint is not stable.
- **Facebook stealth requirements:** `playwright-stealth` effectiveness against current Facebook bot detection should be tested early. If it fails, the fallback is `undetected-playwright` or a commercial headless browser service.
- **Twilio WhatsApp template approval process:** Current template approval time, format requirements, and sandbox-to-production migration steps should be verified against current Twilio documentation before Phase 7.
- **Nominatim rate limits:** Verify current Nominatim usage policy (1 req/sec is the historical limit; confirm it still applies and is sufficient for expected listing volumes).
- **Israeli VPS provider:** Deployment on an Israeli IP is required for Facebook Marketplace geo-filtering. Identify a provider (AWS Israel region, DigitalOcean TLV, or Hetzner Israel if available) before Phase 8.

---

## Sources

### Primary (HIGH confidence)
- `.planning/research/STACK.md` — full technology stack with rationale and alternatives
- `.planning/research/FEATURES.md` — table stakes, differentiators, anti-features, MVP recommendations
- `.planning/research/ARCHITECTURE.md` — component boundaries, data flow, schema, build order
- `.planning/research/PITFALLS.md` — critical/moderate/minor pitfalls with phase warnings
- `.planning/PROJECT.md` — validated requirements and constraints

### Secondary (MEDIUM confidence)
- Training knowledge: Yad2/Madlan platform structure and bot detection patterns (accurate as of Aug 2025; verify at build time)
- Training knowledge: Facebook scraping with Playwright + stealth (current best practice; evolves with Facebook updates)
- Training knowledge: WhatsApp Business Platform 24-hour session window policy (stable policy; verify current template approval process)
- Training knowledge: Israeli real estate UX conventions and חדרים room count system (HIGH confidence — stable domain knowledge)

### Tertiary (LOW confidence)
- Madlan GraphQL/REST API shape — must be discovered at build time via network inspection
- Exact Yad2 API endpoint parameters — must be verified at build time

---
*Research completed: 2026-03-28*
*Ready for roadmap: yes*
