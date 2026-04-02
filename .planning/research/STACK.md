# Technology Stack

**Project:** ApartmentFinder — Personal apartment listing aggregator
**Researched:** 2026-03-28
**Confidence note:** WebSearch and WebFetch are unavailable in this environment. All findings are from training data (cutoff August 2025). Confidence levels reflect that constraint. Version numbers are accurate as of mid-2025 but should be verified at install time.

---

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
| Playwright (Python) | 1.44+ | Browser automation — Facebook only | Keep for Facebook scraping: session persistence, headed mode + Xvfb, playwright-stealth. Do NOT replace with a higher-level wrapper for Facebook. |
| Crawl4AI | latest | JS-rendering scraper — Yad2 + Madlan | Open source (Apache 2.0), free forever, async Python API, built on Playwright under the hood. Outputs LLM-ready markdown directly — pairs perfectly with the Phase 2 LLM verification pipeline. Replaces raw Playwright+BS4 for structured sources. Session IDs enable authentication flows. |
| httpx | 0.27+ | HTTP client for static pages | Async HTTP; use for Yad2/Madlan direct API endpoints when a full browser is not needed |
| BeautifulSoup4 | 4.12+ | HTML parsing fallback | Use only if Crawl4AI output needs post-processing; may be unnecessary with Crawl4AI's built-in extraction strategies |
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

No separate RTL library (e.g., `stylis-plugin-rtl`) is needed when using Tailwind's native `rtl:` variants.

### WhatsApp Notifications

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Twilio WhatsApp API (via `twilio` Python SDK) | 9.x | WhatsApp message delivery | Most reliable, production-grade option; pay-per-message; Twilio Sandbox for development is free; no dedicated business number required for personal use |
| `twilio` Python SDK | 9.0+ | API client | Official SDK; straightforward `send_message` call |

**WhatsApp alternative: `whatsapp-web.js` (node) / `pywhatkit`:** Do NOT use these. They use unofficial, reverse-engineered protocols and are routinely broken by WhatsApp updates. Twilio is the only reliably stable option for a production personal bot. Confidence: HIGH.

**WhatsApp alternative: Meta Cloud API (direct):** Requires a verified Meta Business account and a dedicated phone number. Twilio abstracts all of that. For a personal tool, Twilio's sandbox is faster to set up. Can be migrated to Meta direct later if cost matters.

### Infrastructure / Deployment

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Docker + Docker Compose | Compose v2 | Container packaging | One `docker compose up` deploys the full stack (FastAPI + Vite build + SQLite volume mount); reproducible across machines |
| Nginx (inside Docker) | 1.26+ | Reverse proxy + static file serving | Serves the Vite-built frontend, proxies `/api` to FastAPI, handles SSL termination if deploying to a VPS |
| DigitalOcean (VPS) | — | **Primary** cloud deployment — **FREE via GitHub Student Pack** | $200 credits covers ~33 months on a $6/mo droplet; best fit for Playwright `headless=False` + Xvfb which requires a real Linux VM; not possible on serverless/container platforms |
| Railway | — | Alternative deployment — **FREE via GitHub Student Pack** | Simpler PaaS; use if VPS management feels like overhead, but test Playwright Xvfb support first |
| GitHub Actions | — | CI/CD — **FREE via GitHub Pro (Student Pack)** | Automate Docker build + SSH deploy on push; no extra cost |
| Namecheap .me domain | — | Custom domain — **FREE 1 year via GitHub Student Pack** | Access the app by name; register via GitHub Pack |
| Volumes (Docker) | — | SQLite persistence | Mount a host volume so the SQLite file survives container restarts |

> **Student note:** DigitalOcean is the primary recommendation because Playwright in headed mode (`headless=False` + Xvfb virtual display) is required for Facebook scraping and works only on a real Linux VM — not on Railway's managed container environment. The $200 Student Pack credit covers the full development lifetime of this project at no cost.

**Why not PostgreSQL:** For a single user with hundreds of listings, SQLite is faster to operate (no separate container, no connection pool, no credentials), and SQLAlchemy means migrating to Postgres later is a one-line change. Do not add Postgres complexity until you need it.

**Why not Redis/Celery:** APScheduler embedded in FastAPI is sufficient for cron-style scraping at 1–3 hour intervals. Adding Celery and a Redis broker is unnecessary complexity for this scale.

---

## Facebook Scraping — Special Section

Facebook is the hardest source in this project. It deserves explicit guidance.

### The Core Problem

Facebook renders almost all content via JavaScript after a logged-in session. There is no public API for group posts or Marketplace listings. The Graph API does not expose group post content. Any working approach requires a real browser session.

### Recommended Approach: Playwright with Persistent Session (MEDIUM confidence)

```
1. First run: launch Playwright in headed mode, manually log in to Facebook.
2. Save the browser context (cookies + localStorage) to a file using
   context.storage_state(path="fb_session.json").
3. Subsequent runs: load that session file — Playwright restores the
   logged-in state without re-entering credentials.
4. Navigate to each group's /posts/ URL and scrape the rendered DOM.
```

This is the most reliable approach as of 2025. Key considerations:

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

**Confidence: MEDIUM** — Facebook's bot detection evolves continuously. The Playwright + stealth approach is the current best practice but may require maintenance as Facebook updates. This is the highest-risk technical component in the project.

---

## Yad2 and Madlan Scraping

### Yad2

Yad2 (yad2.co.il) is an Israeli real estate classifieds site. It renders listings via a React/Vue frontend that calls internal REST APIs. As of 2025:

- The page at `yad2.co.il/realestate/rent` loads listing data via XHR calls to `gw.yad2.co.il/feed/realestate/rent`.
- These API endpoints accept query parameters for city, rooms, price range, etc.
- The response is JSON — meaning you can call the API directly with `httpx` rather than running a full browser.
- Recommended: reverse-engineer the API call from DevTools Network tab, replicate with `httpx`. Add a realistic `User-Agent` header.
- Confidence: MEDIUM (internal APIs change without notice; verify at build time).

### Madlan

Madlan (madlan.co.il) is owned by Fiverr's Homeless (or similar; it's Israel's primary price-history/listing site). It also uses a JSON API backend:

- Inspect network calls on `madlan.co.il/rent` to identify the GraphQL or REST endpoint.
- GraphQL is likely; use `httpx` to POST queries.
- Confidence: LOW — Madlan is less well-documented than Yad2; requires manual API discovery at build time.

Both Yad2 and Madlan are far easier to scrape than Facebook because they do not require browser login state. `httpx` + `beautifulsoup4` is sufficient unless the API discovery approach fails, in which case fall back to Playwright.

---

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

**Use React-Leaflet 4.2+ with Leaflet 1.9+.** For marker clustering when many listings overlap, add `react-leaflet-cluster` (wraps `leaflet.markercluster`).

**OpenStreetMap tiles** include Hebrew labels for Israeli cities and streets — no extra configuration needed.

**Do not use Google Maps:** Requires an API key and billing setup. For a personal tool, free OSM is better.

---

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
| Scraping: Yad2 + Madlan | Crawl4AI | raw Playwright + BS4 | Crawl4AI is free/open-source, async Python, outputs LLM-ready markdown, and reduces boilerplate vs writing Playwright + BS4 manually |
| Scraping service | (none / self-built) | Firecrawl (self-hosted) | Firecrawl self-hosting requires PostgreSQL + Redis + Playwright microservice — significant ops overhead for a personal tool. Hosted Firecrawl is paid. Crawl4AI gives 80% of the benefit with zero infrastructure cost. |
| Cloud deployment | DigitalOcean (Student $200 credit) | Render / Fly.io (paid) | DigitalOcean is free via GitHub Student Pack; also required for Playwright Xvfb headed mode on a real Linux VM |

---

## Installation Snapshot

```bash
# Python dependencies (requirements.txt)
fastapi>=0.111
uvicorn[standard]>=0.30
sqlalchemy[asyncio]>=2.0
alembic>=1.13
aiosqlite>=0.20          # Async SQLite driver for SQLAlchemy
playwright>=1.44
playwright-stealth>=1.0
httpx>=0.27
beautifulsoup4>=4.12
apscheduler>=3.10
pydantic>=2.7
twilio>=9.0
python-dotenv>=1.0

# Install Playwright browsers
playwright install chromium

# Node/frontend (package.json)
react@^18
react-dom@^18
vite@^5
@vitejs/plugin-react@^4
tailwindcss@^3.4
postcss@^8
autoprefixer@^3
leaflet@^1.9
react-leaflet@^4.2
react-leaflet-cluster@^2        # Marker clustering
@tanstack/react-query@^5
react-router-dom@^6
```

---

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

---

## Sources

All findings are from training knowledge (cutoff August 2025). No live web sources were accessible in this session.

Authoritative references to verify at build time:
- Playwright Python docs: https://playwright.dev/python/docs/intro
- FastAPI docs: https://fastapi.tiangolo.com/
- React-Leaflet docs: https://react-leaflet.js.org/
- Twilio WhatsApp Sandbox: https://www.twilio.com/docs/whatsapp/sandbox
- APScheduler docs: https://apscheduler.readthedocs.io/
- SQLAlchemy async docs: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- Tailwind RTL docs: https://tailwindcss.com/docs/hover-focus-and-other-states#rtl-support
