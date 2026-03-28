# Architecture Patterns

**Domain:** Scraping + Aggregation + Map Display (Apartment Listing Aggregator)
**Researched:** 2026-03-28
**Confidence:** HIGH for structural patterns (well-established); MEDIUM for specific library choices

---

## Recommended Architecture

The system has five clearly bounded components that form a unidirectional pipeline:

```
[Scrapers] --> [Job Queue / Scheduler] --> [Storage + Dedup Layer]
                                                   |
                                         [REST API / Backend]
                                                   |
                       [Map Web UI] <---------+    +--------> [Notification Service]
```

Data flows in one direction: raw listings are scraped, normalized, stored, deduplicated, then served to the UI and notification channel. There is no bidirectional coupling between the scraper layer and the frontend.

---

## Component Boundaries

### 1. Scraper Workers

**Responsibility:** Fetch raw listing data from a single source, parse HTML/JSON into a normalized schema, and push the result to a queue or directly to the DB.

**Boundary rule:** One scraper per source. Each scraper only knows about its own source. Scrapers do NOT touch the database directly in advanced designs; they emit raw/normalized records to a queue. For a single-user system, direct DB writes from scrapers are acceptable and reduce complexity.

**Sources to scrape:**
- Yad2 — structured API or HTML (most accessible; has unofficial API endpoints)
- Madlan — HTML scraping, site loads via JS; requires headless browser (Playwright)
- Facebook Marketplace — requires authenticated browser session; Playwright with stored cookies
- Facebook Groups — same as Marketplace; requires session

**Communicate with:** Storage layer (direct write or queue)

### 2. Scheduler / Job Runner

**Responsibility:** Trigger scraper runs on a schedule (every 1–3 hours), retry failed runs, and prevent concurrent overlapping runs for the same source.

**Boundary rule:** The scheduler does NOT know anything about scraping logic. It only invokes scrapers by name/target and passes a run ID.

**Implementation options (ordered by simplicity for single-user):**
- **APScheduler (Python)** — in-process scheduler embedded in the backend server. Simplest for self-hosted single-user. No external service needed.
- **Celery + Redis** — distributed task queue. Production-grade but overengineered for one user.
- **Cron + subprocess** — OS-level cron calling scraper scripts. Simple but no retry logic and harder to monitor.

**Recommended:** APScheduler embedded in the backend process. If the backend is FastAPI, APScheduler runs alongside it. Zero external dependencies.

**Communicate with:** Scraper Workers (invokes them), Storage layer (marks run timestamps)

### 3. Storage + Deduplication Layer

**Responsibility:** Persist normalized listings, enforce deduplication, track "seen" and "favorited" state per listing.

**Boundary rule:** This layer owns the canonical listing record. It is the single source of truth. The API layer reads from here; scrapers write to here.

**Database:** PostgreSQL (or SQLite for local-only dev). PostgreSQL recommended for deployment because it handles concurrent writes from multiple scrapers and supports PostGIS for geospatial queries natively.

**Schema (core):**

```
listings
  id            UUID PRIMARY KEY
  source        TEXT  (yad2 | madlan | facebook_marketplace | facebook_group)
  source_id     TEXT  (the external ID on that platform)
  url           TEXT
  title         TEXT
  price         INTEGER  (ILS/month)
  rooms         NUMERIC
  size_m2       INTEGER  (nullable)
  address       TEXT
  neighborhood  TEXT
  lat           NUMERIC  (nullable until geocoded)
  lng           NUMERIC  (nullable until geocoded)
  contact_info  TEXT
  posted_at     TIMESTAMPTZ
  scraped_at    TIMESTAMPTZ
  raw_data      JSONB    (full original record, for re-parsing)
  is_seen       BOOLEAN DEFAULT FALSE
  is_favorited  BOOLEAN DEFAULT FALSE
  is_active     BOOLEAN DEFAULT TRUE  (set false when listing disappears)

UNIQUE INDEX on (source, source_id)
```

**Deduplication strategy (see full section below)**

**Communicate with:** Scraper Workers (write), API layer (read/write for seen/favorited)

### 4. REST API / Backend

**Responsibility:** Serve listing data to the frontend, expose mutation endpoints (mark seen, toggle favorite), and host the scheduler.

**Boundary rule:** The API does NOT contain scraping logic. It reads from the DB and exposes clean endpoints. Business logic (filtering by neighborhood, filtering by price/rooms) lives here, not in the frontend.

**Framework:** FastAPI (Python). Chosen because:
- Scrapers will be in Python (Playwright, httpx, BeautifulSoup are Python-native)
- Collocating API and scraper scheduler in one Python process simplifies deployment
- FastAPI async support works well with APScheduler
- Auto-generates OpenAPI docs

**Key endpoints:**
```
GET  /listings          query params: min_price, max_price, min_rooms, max_rooms, neighborhood, since, seen, favorited
GET  /listings/{id}     single listing detail
PUT  /listings/{id}/seen      mark seen
PUT  /listings/{id}/favorited toggle favorite
GET  /health            scheduler status, last run timestamps per source
```

**Communicate with:** Storage layer (read/write), serves Map Web UI (HTTP), triggers Notification Service (internal call or event)

### 5. Map Web UI (Frontend)

**Responsibility:** Display listings as pins on an interactive map. Provide filter controls. Show listing cards. Allow marking seen/favorited.

**Boundary rule:** The frontend is a dumb display layer. It does NOT compute filters, deduplicate, or know about scraping. All data comes from the API.

**Framework:** React (or Next.js for SSR convenience). Chosen for:
- Rich ecosystem for map components (Leaflet via react-leaflet, or Mapbox GL JS)
- RTL support via CSS direction + libraries like i18next or plain CSS
- Mobile-first responsive design achievable with Tailwind CSS

**Map library:** Leaflet (via react-leaflet) — open source, no API key required for OpenStreetMap tiles, well-supported. Mapbox GL is an alternative with better visual quality but requires API key and has usage costs.

**Communicate with:** REST API (fetch listings, send mutations)

### 6. Notification Service

**Responsibility:** Send WhatsApp messages when new listings are found that match the user's criteria.

**Boundary rule:** Triggered by the backend after a scrape run completes and new listings are detected. Does NOT query the DB directly — it receives a payload of new listing summaries from the backend.

**Implementation:** Twilio WhatsApp API (MEDIUM confidence — other options exist but Twilio is the most documented for programmatic WhatsApp). Send a summary message after each scrape run that found new results.

**Alternative:** WhatsApp Business Cloud API (Meta direct) — free tier exists, more complex setup.

**Communicate with:** Backend (triggered by scheduler post-run hook), external WhatsApp API

---

## Data Flow: Raw Listing to Map Pin

```
1. Scheduler fires (e.g., every 2 hours)
   |
2. Scraper Worker runs for each source (parallel or sequential)
   - Fetches raw HTML or API response
   - Parses into normalized dict: {source, source_id, title, price, rooms, address, url, ...}
   |
3. Storage layer receives normalized record
   - Check: does (source, source_id) already exist? → Skip (idempotent write)
   - If new: INSERT into listings
   - If existing but price/availability changed: UPDATE (optional for v1)
   |
4. Geocoding (if address present but no lat/lng)
   - Nominatim (OpenStreetMap geocoder, free) or Google Maps Geocoding API
   - Updates lat/lng on the listing record
   - Can be async/deferred (listing visible on map once geocoded)
   |
5. Notification check
   - Backend counts listings inserted in this run that match filter criteria
   - If count > 0: call Notification Service with summary
   |
6. Frontend polls or requests listings
   - GET /listings?since=<last_load_time>&neighborhood=carmel,downtown,neve_shanan
   - Renders pins on map
   - User clicks pin → listing card shows price, rooms, contact, source link
```

---

## Deduplication Strategy

**Level 1 — Same source, same listing (primary key dedup)**
Use a UNIQUE constraint on `(source, source_id)`. The `source_id` is the platform's own ID for the listing (e.g., Yad2 listing number, Facebook post ID). An `INSERT ... ON CONFLICT DO NOTHING` handles this transparently. This is the most reliable dedup method.

Confidence: HIGH. This is standard practice.

**Level 2 — Cross-source dedup (same apartment posted on Yad2 AND Facebook)**
This is inherently fuzzy. A listing is probably a duplicate if it shares: same approximate address, same price, same room count, posted within a short window.

Implementation: After inserting a new listing, run a similarity query:
```sql
SELECT id FROM listings
WHERE price = $price
  AND rooms = $rooms
  AND earth_distance(ll_to_earth(lat, lng), ll_to_earth($lat, $lng)) < 100 -- within 100m
  AND posted_at BETWEEN $posted_at - interval '3 days' AND $posted_at + interval '3 days'
  AND id != $new_id
LIMIT 1;
```
If a match is found, mark the new listing with a `duplicate_of` foreign key and hide it from default queries.

**Level 3 — Title/description similarity**
Fuzzy text matching (trigram similarity via PostgreSQL `pg_trgm` extension). Use only as a tiebreaker — address + price + rooms matching is more reliable for Hebrew text where OCR or transliteration may vary.

**For v1 MVP:** Implement Level 1 (mandatory) and Level 2 (address+price+rooms proximity). Level 3 is a nice-to-have.

---

## Scheduler / Cron Approach

**Recommended: APScheduler (in-process)**

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
scheduler.add_job(run_all_scrapers, "interval", hours=2, id="scrape_all")
scheduler.start()
```

Run within the FastAPI process using the lifespan context manager (FastAPI `@asynccontextmanager lifespan`). The scheduler starts when the server starts and shuts down cleanly.

**Why not cron:**
- No built-in retry on failure
- No visibility into last run time or success/failure via the API
- Harder to change schedule without SSH access

**Why not Celery:**
- Requires Redis or RabbitMQ as a broker
- Overkill for single-user, single-machine
- Adds operational complexity

**Run cadence:** Every 2 hours is a reasonable default. Make it configurable via environment variable to avoid hardcoding.

**Overlap prevention:** APScheduler's `misfire_grace_time` and `coalesce=True` settings prevent multiple simultaneous runs of the same job. Set `max_instances=1` per job.

---

## Suggested Build Order

**Rationale:** Build in the order that delivers a working slice of the pipeline first, then layer on complexity. The storage layer and API are the central hub — both scrapers and frontend depend on them.

### Phase 1: Storage Foundation
- Define DB schema (listings table with all columns)
- Set up PostgreSQL (local Docker or Railway/Supabase for cloud)
- Write migration scripts (Alembic for Python)
- Verify UNIQUE constraint on (source, source_id)

**Must exist before:** Everything else. The schema drives all downstream work.

### Phase 2: First Scraper (Yad2)
- Yad2 is the most accessible source (structured site, unofficial API patterns well-documented)
- Build the scraper, normalize output to DB schema, write to DB
- Validate data quality: are prices, rooms, addresses parsing correctly?
- Implement Level 1 dedup (idempotent inserts)

**Must exist before:** Cross-source dedup patterns are established; Yad2 data validates schema.

### Phase 3: REST API (minimal)
- FastAPI with GET /listings (with filter params)
- No auth (single user, internal use)
- Embed APScheduler, wire Yad2 scraper to schedule

**Must exist before:** Frontend development.

### Phase 4: Map Web UI (MVP)
- React + Leaflet map
- Fetch from GET /listings, render pins
- Listing card on click
- Basic filters (price, rooms)
- RTL/Hebrew layout

**Must exist before:** Geocoding matters (geocoding serves the map).

### Phase 5: Geocoding
- Integrate Nominatim or Google Maps Geocoding for listings without lat/lng
- Run geocoding async after insert (background task in FastAPI)

### Phase 6: Additional Scrapers
- Madlan (requires Playwright — headless browser adds complexity)
- Facebook Marketplace (requires authenticated Playwright session — highest complexity)
- Facebook Groups (same as Marketplace)

**Order within this phase:** Madlan before Facebook (less auth complexity).

### Phase 7: User State + Notifications
- Mark seen / favorited endpoints + UI controls
- Cross-source dedup (Level 2)
- WhatsApp notification via Twilio after scrape run

### Phase 8: Polish
- Mobile responsive refinement
- Error handling and scraper health dashboard
- Configurable filters persisted in localStorage or a simple config table

---

## Scalability Considerations

| Concern | Single User (current) | If Multi-User Later |
|---------|----------------------|---------------------|
| DB load | SQLite sufficient; PostgreSQL comfortable | PostgreSQL required; add connection pool |
| Scraper concurrency | Sequential per source is fine | Move to Celery + Redis worker pool |
| Geocoding rate limits | Nominatim: 1 req/sec (free); fine for ~50 listings/run | Cache geocodes by address; use paid API |
| Map rendering | Client-side Leaflet handles hundreds of pins | Cluster pins; paginate API response |
| Notifications | Direct Twilio call | Push to notification queue |

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Scraper Logic in the Frontend
**What:** Calling scraping or geocoding from the browser.
**Why bad:** Exposes credentials, blocked by CORS, unreliable in a browser context.
**Instead:** All scraping is server-side only.

### Anti-Pattern 2: Polling the DB from the Frontend
**What:** Frontend connecting directly to PostgreSQL.
**Why bad:** Security exposure, no query control, schema changes break UI directly.
**Instead:** All frontend data access goes through the REST API.

### Anti-Pattern 3: Single Monolithic Scraper Function
**What:** One function that scrapes all sources sequentially and fails silently if one source errors.
**Why bad:** A Facebook login failure kills the entire run including Yad2.
**Instead:** Each source is an independent function with its own try/except. Failed sources are logged but don't prevent successful sources from completing.

### Anti-Pattern 4: Geocoding on Every Insert
**What:** Calling the geocoding API inline during the scrape INSERT transaction.
**Why bad:** Geocoding is slow (100–500ms/call), rate-limited, and can fail. Blocks the scrape run.
**Instead:** Insert listings with null lat/lng, geocode asynchronously in a background task.

### Anti-Pattern 5: Storing Session Tokens in Code
**What:** Hardcoding Facebook session cookies or API keys in source files.
**Why bad:** Security risk; breaks on rotation.
**Instead:** Use environment variables and a `.env` file excluded from version control.

---

## Technology Summary

| Component | Technology | Notes |
|-----------|-----------|-------|
| Scrapers (static) | Python + httpx + BeautifulSoup | Yad2 and potentially Madlan static pages |
| Scrapers (dynamic) | Python + Playwright | Madlan JS-rendered, Facebook sessions |
| Scheduler | APScheduler (asyncio) | Embedded in FastAPI process |
| Database | PostgreSQL | Docker locally; Railway/Supabase for cloud |
| Migrations | Alembic | Python-native; works with FastAPI |
| Backend API | FastAPI (Python) | Async; collocates with scheduler |
| Geocoding | Nominatim (free) or Google Maps API | Nominatim first; upgrade if rate limits hit |
| Map UI | React + react-leaflet + OpenStreetMap | No API key required |
| Frontend styling | Tailwind CSS | RTL support via `dir="rtl"` + Tailwind |
| Notifications | Twilio WhatsApp API | Industry standard for programmatic WhatsApp |
| Deployment | Docker Compose | Single container or two: API + DB |

---

## Sources

- APScheduler documentation (apscheduler.readthedocs.io) — HIGH confidence, well-established library
- FastAPI lifespan documentation — HIGH confidence
- PostgreSQL UNIQUE constraints and ON CONFLICT — HIGH confidence
- Leaflet / react-leaflet — HIGH confidence, widely used
- Nominatim usage policy (1 req/sec rate limit) — MEDIUM confidence, verify current limits
- Twilio WhatsApp API — MEDIUM confidence, verify current pricing/sandbox setup requirements
- Facebook scraping with Playwright — MEDIUM confidence; Facebook actively changes its DOM structure and anti-bot measures; this component carries the most implementation risk
