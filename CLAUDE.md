<!-- GSD:project-start source:PROJECT.md -->
## Project

**ApartmentFinder**

A personal mobile-first web app that automatically scrapes Facebook groups, Facebook Marketplace, Yad2, and Madlan for apartment rental listings in Haifa, Israel. All listings are aggregated into an interactive live map, deduplicated, and filterable — so the user can open the app each morning and see all new listings without manually searching anywhere. The app is in Hebrew with full RTL support.

**Core Value:** New Haifa rental listings from all sources appear on a single live map every morning — no manual searching required.

### Constraints

- **Language**: Full Hebrew/RTL support required throughout the UI
- **Accessibility**: Must be usable on a smartphone browser (no native app)
- **Data freshness**: Listings must reflect posts within a few hours
- **Legal**: Scraping must respect rate limits and ToS boundaries where possible
- **Scale**: Single-user — no need to optimize for high concurrency
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Backend / Scraping Runtime
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.12 | Primary runtime | Dominant scraping/automation language; best ecosystem for Playwright, async workers, and data wrangling |
| FastAPI | 0.111+ | REST API server | Async-native, auto OpenAPI docs, thin overhead; ideal for a single-user app with a handful of endpoints |
| SQLite | 3.45+ (bundled) | Primary database | Zero-ops, file-based, more than sufficient for a single-user app with hundreds of listings |
| SQLAlchemy | 2.0+ | ORM / query layer | Async-capable, well-typed, straightforward migrations via Alembic |
| Alembic | 1.13+ | Schema migrations | Standard SQLAlchemy migration tool; keeps schema changes reproducible |
| APScheduler | 3.10+ | Periodic scraping scheduler | Pure-Python, embeds directly into FastAPI process, cron-style triggers; no separate worker infra needed for single-user scale |
| Playwright (Python) | 1.44+ | Browser automation for scraping | Best-in-class headless browser control; handles JS-heavy SPAs; critical for Facebook and Yad2 |
| httpx | 0.27+ | HTTP client for static pages | Async HTTP; use for Madlan/Yad2 API endpoints or RSS feeds when a full browser is not required |
| BeautifulSoup4 | 4.12+ | HTML parsing | Reliable, well-maintained; use after Playwright renders the DOM |
| pydantic | 2.7+ | Data validation | FastAPI-native, fast Rust-based validation in v2 |
### Frontend
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| React | 18.x | UI framework | Largest ecosystem, best RTL and Hebrew community; strong Tailwind and map library support |
| Vite | 5.x | Build tool | Fastest dev server, modern ESM output; replaced Create React App |
| Tailwind CSS | 3.4+ | Utility-first styling | RTL support via `dir="rtl"` on `<html>`; easy to flip layouts without writing custom CSS |
| React-Leaflet | 4.2+ | Map component | Thin React wrapper over Leaflet.js, mobile-first, works with free OpenStreetMap tiles, MIT licensed |
| Leaflet.js | 1.9+ | Underlying map library | Lightweight (42KB), excellent mobile touch support, free tile layers |
| TanStack Query | 5.x | Server-state management | Auto-refetch, background sync, loading/error states — keeps listing data fresh without manual polling code |
| React Router | 6.x | Client-side routing | Standard; needed if adding detail views or separate pages |
### RTL / Hebrew UI
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Tailwind CSS `dir` utilities | 3.4+ | Logical RTL properties | Tailwind v3 has `rtl:` variant; set `dir="rtl"` on `<html>`, use `ms-`/`me-` logical margin utilities |
| Noto Sans Hebrew | latest (Google Fonts) | Hebrew typeface | Excellent coverage of Hebrew Unicode block; loads via Google Fonts CDN |
| `lang="he"` on `<html>` | HTML standard | Browser-native RTL | Combined with `dir="rtl"` gives correct bidi text, punctuation, and form layout for free |
### WhatsApp Notifications
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Twilio WhatsApp API (via `twilio` Python SDK) | 9.x | WhatsApp message delivery | Most reliable, production-grade option; pay-per-message; Twilio Sandbox for development is free; no dedicated business number required for personal use |
| `twilio` Python SDK | 9.0+ | API client | Official SDK; straightforward `send_message` call |
### Infrastructure / Deployment
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Docker + Docker Compose | Compose v2 | Container packaging | One `docker compose up` deploys the full stack (FastAPI + Vite build + SQLite volume mount); reproducible across machines |
| Nginx (inside Docker) | 1.26+ | Reverse proxy + static file serving | Serves the Vite-built frontend, proxies `/api` to FastAPI, handles SSL termination if deploying to a VPS |
| Render / Railway / Fly.io | — | Cloud deployment | Any of these runs a single Docker container for ~$5–7/month with a public URL; no Kubernetes overhead |
| Volumes (Docker) | — | SQLite persistence | Mount a host volume so the SQLite file survives container restarts |
## Facebook Scraping — Special Section
### The Core Problem
### Recommended Approach: Playwright with Persistent Session (MEDIUM confidence)
- **Session expiry:** Facebook sessions expire. Build a health-check that detects the login redirect and alerts you via WhatsApp to re-authenticate. Do not attempt fully automated login (email+password bot) — Facebook actively detects and blocks it.
- **Rate limiting:** Wait 5–15 seconds between page navigations. Scraping too fast triggers temporary IP bans.
- **Stealth mode:** Use `playwright-stealth` (Python port) or `undetected-playwright` to mask headless browser fingerprints. Facebook's bot detection is aggressive.
- **Headless vs headed:** Headless mode is increasingly detectable. Run Playwright with `headless=False` in a virtual display (Xvfb on Linux) when deploying to a VPS.
- **Facebook Marketplace:** Same approach, but the DOM structure is different from groups. Treat as a separate scraper class.
### Libraries for Facebook Scraping
| Library | Purpose | Confidence |
|---------|---------|------------|
| `playwright` (Python) 1.44+ | Browser automation core | HIGH |
| `playwright-stealth` 1.0.x | Mask headless fingerprints | MEDIUM |
| `beautifulsoup4` 4.12+ | Parse rendered HTML | HIGH |
### What NOT to Use for Facebook
- **`facebook-scraper`**: Uses unofficial mobile endpoints. Was functional in 2023, actively broken by 2024 Facebook changes. Do not use.
- **`mechanicalsoup`**: Cannot execute JavaScript. Facebook is SPA-only.
- **`requests` + `lxml`**: Same problem — no JS execution.
- **Selenium**: Playwright supersedes it; slower, worse async support, harder to stealth.
## Yad2 and Madlan Scraping
### Yad2
- The page at `yad2.co.il/realestate/rent` loads listing data via XHR calls to `gw.yad2.co.il/feed/realestate/rent`.
- These API endpoints accept query parameters for city, rooms, price range, etc.
- The response is JSON — meaning you can call the API directly with `httpx` rather than running a full browser.
- Recommended: reverse-engineer the API call from DevTools Network tab, replicate with `httpx`. Add a realistic `User-Agent` header.
- Confidence: MEDIUM (internal APIs change without notice; verify at build time).
### Madlan
- Inspect network calls on `madlan.co.il/rent` to identify the GraphQL or REST endpoint.
- GraphQL is likely; use `httpx` to POST queries.
- Confidence: LOW — Madlan is less well-documented than Yad2; requires manual API discovery at build time.
## Map Display
### Recommended: React-Leaflet + OpenStreetMap
| Criterion | Leaflet (React-Leaflet) | Google Maps JS API | Mapbox GL JS |
|-----------|------------------------|-------------------|--------------|
| Cost | Free (OSM tiles) | Free tier then paid | Free tier then paid |
| Mobile touch | Excellent | Excellent | Excellent |
| Bundle size | ~42KB | Large | ~250KB |
| Hebrew tile labels | OSM Hebrew labels available | Yes | Yes |
| Cluster support | `leaflet.markercluster` | Requires premium | `supercluster` |
| Complexity | Low | Medium | Medium |
## Alternatives Considered
| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Backend language | Python | Node.js | Python has far better scraping/automation ecosystem (Playwright Python, BeautifulSoup, pandas) |
| Browser automation | Playwright | Selenium | Playwright is faster, async-native, has better stealth support |
| Database | SQLite | PostgreSQL | Single user; Postgres adds ops overhead for no benefit |
| Task scheduling | APScheduler (in-process) | Celery + Redis | Celery requires a separate broker; overkill for cron-style hourly scraping |
| Frontend framework | React + Vite | Next.js | No SSR needed for a personal tool; Next.js adds build complexity |
| Map library | Leaflet (OSM) | Google Maps | Google requires billing; OSM is free and has Hebrew tiles |
| WhatsApp API | Twilio | Meta Cloud API direct | Twilio sandbox is faster to set up; Meta direct requires business verification |
| CSS framework | Tailwind CSS | Chakra UI / MUI | Tailwind's `rtl:` variants are simpler for RTL than component libraries with mixed RTL support |
| Scraping: Facebook | Playwright + stealth | facebook-scraper library | `facebook-scraper` is broken as of 2024; Playwright is the only working approach |
## Installation Snapshot
# Python dependencies (requirements.txt)
# Install Playwright browsers
# Node/frontend (package.json)
## Confidence Assessment
| Area | Confidence | Reason |
|------|------------|--------|
| Python + FastAPI + SQLite | HIGH | Stable, widely used pattern; no major changes expected |
| Playwright for scraping | HIGH | Current best-practice browser automation as of Aug 2025 |
| Facebook scraping (Playwright + stealth) | MEDIUM | Works but fragile; Facebook actively fights it; requires ongoing maintenance |
| Yad2 API (httpx direct) | MEDIUM | API endpoint must be verified by inspecting network tab at build time |
| Madlan API (httpx/GraphQL) | LOW | Less documented; API shape needs discovery at build time |
| Twilio WhatsApp | HIGH | Official API, stable, well-documented |
| React-Leaflet + OSM | HIGH | Stable, widely used, no cost surprises |
| RTL with Tailwind `rtl:` | HIGH | Tailwind v3 native RTL support is solid |
| APScheduler for cron tasks | HIGH | Embedded scheduler is well-established pattern at this scale |
## Sources
- Playwright Python docs: https://playwright.dev/python/docs/intro
- FastAPI docs: https://fastapi.tiangolo.com/
- React-Leaflet docs: https://react-leaflet.js.org/
- Twilio WhatsApp Sandbox: https://www.twilio.com/docs/whatsapp/sandbox
- APScheduler docs: https://apscheduler.readthedocs.io/
- SQLAlchemy async docs: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- Tailwind RTL docs: https://tailwindcss.com/docs/hover-focus-and-other-states#rtl-support
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
