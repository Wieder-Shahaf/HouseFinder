# Roadmap: ApartmentFinder

## Overview

Eight phases build the pipeline from the ground up: the database schema and dev environment come first because every other component depends on them; the first working scraper (Yad2) and LLM verification pipeline come second to validate the full normalization contract before the API or UI are built; the REST API and scheduler follow to wire scraping to a schedule; the map UI is built fourth against real data; geocoding and cross-source dedup are added fifth to unlock neighborhood filtering; Madlan is added as the second structured source; notifications (WhatsApp + Web Push) round out the alerting story; and Facebook scrapers come last, fully isolated, because they carry the highest fragility risk. The core app is fully functional without Facebook — it adds landlord-direct listings as a differentiator.

**Note:** Submit the Twilio WhatsApp message template for Meta approval during Phase 1 setup. Template approval takes days to weeks and blocks Phase 7.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - DB schema, Alembic migrations, Docker Compose, project skeleton
- [ ] **Phase 2: Yad2 Scraper + LLM Pipeline** - Yad2 Playwright scraper with LLM verification end-to-end
- [ ] **Phase 3: REST API + Scheduler** - FastAPI endpoints, APScheduler with job lock, health checks
- [x] **Phase 4: Map Web UI** - React-Leaflet map, RTL layout, listing cards, seen/favorites, filters (completed 2026-04-02)
- [x] **Phase 5: Geocoding + Dedup + Neighborhoods** - Nominatim geocoding, cross-source dedup, neighborhood tagging (completed 2026-04-02)
- [x] **Phase 6: Madlan Scraper** - Second structured source via Playwright + stealth (completed 2026-04-03)
- [x] **Phase 7: Notifications** - Web Push notifications on new listings (WhatsApp stub deferred) (completed 2026-04-03)
- [ ] **Phase 8: Facebook Scrapers** - Groups and Marketplace with session management

## Phase Details

### Phase 1: Foundation
**Goal**: A reproducible development environment exists with the full database schema, migrations, and project skeleton — ready for scrapers and API to be written against it
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, INFRA-01, INFRA-02, INFRA-03, INFRA-04
**Success Criteria** (what must be TRUE):
  1. `docker compose up` starts backend and frontend containers without errors on a clean machine
  2. Alembic migration runs and produces the listings table with all required columns (source, source_id, lat, lng, is_seen, is_favorited, raw_data, llm_confidence, dedup_fingerprint)
  3. Same-source deduplication constraint (UNIQUE on source + source_id) is enforced at the DB level — inserting a duplicate row raises an integrity error
  4. App is accessible at a public URL (DigitalOcean droplet provisioned via GitHub Student Pack $200 credit — free; Israeli datacenter region selected; DNS configured via free Namecheap .me domain from Student Pack)
  5. `.env` pattern is in place for all secrets (Twilio credentials, LLM API key, scraper config)
**Plans**: 3 plans
Plans:
- [x] 01-01-PLAN.md — Backend skeleton: FastAPI + SQLAlchemy models + Alembic migrations + test scaffold
- [x] 01-02-PLAN.md — Frontend scaffold: React 19 + Vite 8 + Tailwind v4 + Docker Compose files
- [ ] 01-03-PLAN.md — VPS deployment + DNS + SSL + Twilio WhatsApp setup

### Phase 2: Yad2 Scraper + LLM Pipeline
**Goal**: Real Haifa rental listings flow from Yad2 into the database, verified and normalized by the LLM pipeline
**Depends on**: Phase 1
**Requirements**: YAD2-01, YAD2-02, YAD2-03, YAD2-04, LLM-01, LLM-02, LLM-03, LLM-04, LLM-05, LLM-06
**Success Criteria** (what must be TRUE):
  1. Running the Yad2 scraper manually produces listings in the database filtered to Haifa neighborhoods and price ≤ 4,500 ₪
  2. Each listing record contains extracted fields (title, price, rooms, size, address, contact, date, URL) from the scraper or supplemented by the LLM
  3. LLM verification rejects "looking for apartment" posts, sale listings, and spam — they do not appear in the database
  4. Listings below the LLM confidence threshold are excluded from the map view (flagged in the database, not deleted)
  5. A Yad2 scraper failure (network error, selector break) is caught in isolation — the process exits cleanly with an error log entry rather than crashing the pipeline
**Plans**: 4 plans
Plans:
- [~] 02-01-PLAN.md — Config + scraper types + test scaffolds + Yad2 API DevTools verification (Tasks 1+2 done; Task 3 awaiting DevTools findings)
- [x] 02-02-PLAN.md — Yad2 scraper implementation (httpx + Playwright fallback)
- [x] 02-03-PLAN.md — LLM verification pipeline (verify, batch, merge)
- [ ] 02-04-PLAN.md — Integration: wire scraper to LLM pipeline + end-to-end tests
**Research flag**: Yad2 internal API endpoint URL and parameters must be verified via browser DevTools at build time — training data may be stale.

### Phase 3: REST API + Scheduler
**Goal**: The backend exposes a REST API that serves listings with filters, and the Yad2 scraper runs automatically every 2 hours without overlap
**Depends on**: Phase 2
**Requirements**: SCHED-01, SCHED-02, SCHED-03
**Success Criteria** (what must be TRUE):
  1. `GET /listings` returns listings filtered by price, rooms, neighborhood, recency, seen, and favorited query parameters
  2. `PUT /listings/{id}/seen` and `PUT /listings/{id}/favorited` update the listing state and return the updated record
  3. `GET /health` returns last-run timestamps and listing counts per scraper source
  4. Triggering a second scraper run while the first is still in progress does not start a duplicate run (job lock enforced)
**Plans**: 2 plans
Plans:
- [x] 03-01-PLAN.md — Scheduler module + health endpoint + test infrastructure (APScheduler, config, lifespan wiring)
- [x] 03-02-PLAN.md — Listings REST API (GET /listings filters, PUT seen/favorited, comprehensive tests)

### Phase 4: Map Web UI
**Goal**: Users can open the app on their phone and see all active Haifa listings on an interactive map with Hebrew RTL layout, filters, and seen/favorites controls
**Depends on**: Phase 3
**Requirements**: MAP-01, MAP-02, MAP-03, MAP-04, MAP-05, MAP-06, MAP-07, MAP-08
**Success Criteria** (what must be TRUE):
  1. The map loads on a smartphone browser defaulting to the Haifa viewport with listing pins visible
  2. Tapping a pin opens a listing card showing price, rooms, size, contact info, post date, source badge, and a link to the original post
  3. The filter panel controls (price slider, room toggle, neighborhood toggle, "new only" toggle) visibly update the pins shown on the map
  4. Tapping "seen" on a listing fades its pin and hides it from the default view; tapping "favorite" saves it with a distinct icon
  5. The entire UI renders in Hebrew RTL layout — text, buttons, cards, and the filter panel all flow right-to-left
**Plans**: 4 plans
Plans:
- [x] 04-01-PLAN.md — Test infra + Vite config + MapView with listing pins (MAP-01, MAP-03, MAP-07, MAP-08)
- [x] 04-02-PLAN.md — ListingSheet + FilterSheet + seen/favorites mutations (MAP-02, MAP-04, MAP-05)
- [x] 04-03-PLAN.md — FavoritesView + BottomNav + routing (MAP-06)
- [x] 04-04-PLAN.md — Integration verification + visual checkpoint (all MAP requirements)
**UI hint**: yes

### Phase 5: Geocoding + Dedup + Neighborhoods
**Goal**: Every listing with a Hebrew address is geocoded to coordinates, tagged to a Haifa neighborhood, and cross-source duplicates are merged into single records
**Depends on**: Phase 4
**Requirements**: DATA-03, DATA-04, DATA-05
**Success Criteria** (what must be TRUE):
  1. A listing inserted with a Hebrew address gains lat/lng coordinates asynchronously without blocking the scrape transaction
  2. The neighborhood filter on the map correctly separates listings into Carmel, Downtown (Merkaz), and Neve Shanan based on geocoded coordinates
  3. The same apartment posted on both Yad2 and Madlan (matching price, rooms, and coordinates within 100 m) appears as a single pin on the map, not two overlapping pins
**Plans**: 3 plans
Plans:
- [x] 05-01-PLAN.md — Alembic migration + geocoding module (Nominatim + bounding-box tagger + unit tests)
- [x] 05-02-PLAN.md — Google Maps Playwright fallback + dedup pass + APScheduler chain wiring
- [x] 05-03-PLAN.md — Router + schema update (neighborhood filter exact match) + end-to-end verification

### Phase 6: Madlan Scraper
**Goal**: Madlan listings flow into the database alongside Yad2 listings, adding a second structured source with no disruption to the existing pipeline
**Depends on**: Phase 5
**Requirements**: MADL-01, MADL-02, MADL-03
**Success Criteria** (what must be TRUE):
  1. Running the Madlan scraper manually produces listings in the database with source badge "מדלן" and all standard fields populated
  2. Madlan scraper failure is isolated — a broken Madlan run does not prevent the Yad2 scraper from completing its run
  3. Madlan is included in the APScheduler rotation and appears in `GET /health` with its own last-run timestamp and listing count
**Plans**: 1 plan
Plans:
- [x] 06-01-PLAN.md — Madlan scraper: DevTools discovery + Playwright scraper + scheduler integration + tests (MADL-01, MADL-02, MADL-03)
**Research flag**: Madlan's API/GraphQL shape is low-confidence and must be discovered via network inspection at build time.

### Phase 7: Notifications
**Goal**: The user receives a Web Push notification after each scraper run that finds new listings, with a WhatsApp stub ready for future activation
**Depends on**: Phase 6
**Requirements**: NOTF-01, NOTF-02, NOTF-03, NOTF-04
**Success Criteria** (what must be TRUE):
  1. After a scraper run finds new listings, a Web Push notification arrives on the user's phone showing the count and a direct link to the app
  2. At most one notification batch is sent per scraper run — individual listing count does not affect notification frequency
  3. A WhatsApp send_whatsapp() stub exists for future activation after Meta template approval
**Plans**: 2 plans
Plans:
- [x] 07-01-PLAN.md — Backend: Alembic migration + notifier module + push router + scheduler wiring + tests (NOTF-01, NOTF-02, NOTF-03, NOTF-04)
- [x] 07-02-PLAN.md — Frontend: service worker + manifest + push subscription hook + App wiring (NOTF-03)

### Phase 8: Facebook Scrapers
**Goal**: Facebook Groups and Marketplace listings flow into the pipeline as an isolated, best-effort source — with session health monitoring that alerts the user when re-authentication is needed
**Depends on**: Phase 7
**Requirements**: FBGR-01, FBGR-02, FBGR-03, FBGR-04, FBGR-05, FBMP-01, FBMP-02, FBMP-03, FBMP-04
**Success Criteria** (what must be TRUE):
  1. The Facebook Groups scraper extracts posts from user-configured groups using a saved authenticated Playwright session and writes them to the database
  2. The Facebook Marketplace scraper fetches Haifa rental listings independently from the Groups scraper using the same session
  3. A session health check runs before each Facebook scrape; if it detects a login redirect, a WhatsApp alert fires immediately and the scrape is skipped without error propagation
  4. A Facebook scraper failure (any error in Groups or Marketplace) does not block Yad2 or Madlan scrapers from completing their runs
**Plans**: TBD
**Research flag**: Facebook DOM structure, group access policies, and stealth effectiveness evolve continuously. Run a targeted research pass immediately before implementation. Ensure the scraper Facebook account has Haifa set as home city and the server is on an Israeli IP before any testing.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 1/3 | In Progress|  |
| 2. Yad2 Scraper + LLM Pipeline | 0/4 | Planned | - |
| 3. REST API + Scheduler | 1/2 | In Progress|  |
| 4. Map Web UI | 4/4 | Complete   | 2026-04-02 |
| 5. Geocoding + Dedup + Neighborhoods | 3/3 | Complete   | 2026-04-02 |
| 6. Madlan Scraper | 1/1 | Complete   | 2026-04-03 |
| 7. Notifications | 2/2 | Complete   | 2026-04-03 |
| 8. Facebook Scrapers | 0/TBD | Not started | - |
