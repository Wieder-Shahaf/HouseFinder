# Requirements: ApartmentFinder

**Defined:** 2026-03-28
**Core Value:** New Haifa rental listings from all sources appear on a single live map every morning — no manual searching required.

## v1 Requirements

### Scraping — Yad2

- [ ] **YAD2-01**: Scraper fetches active rental listings in Haifa filtered by neighborhoods (Carmel, Downtown, Neve Shanan) and price ≤ 4,500 ₪
- [ ] **YAD2-02**: Scraper extracts: title, price, rooms, size (sqm), address, contact info, post date, listing URL
- [ ] **YAD2-03**: Scraper runs via Playwright (stealth) to bypass bot detection
- [ ] **YAD2-04**: Scraper failure is isolated — Yad2 error does not block other scrapers

### Scraping — Madlan

- [ ] **MADL-01**: Scraper fetches active rental listings in Haifa filtered by neighborhoods and price ≤ 4,500 ₪
- [ ] **MADL-02**: Scraper extracts same fields as Yad2 (title, price, rooms, size, address, contact, date, URL)
- [ ] **MADL-03**: Scraper runs via Playwright with stealth; Madlan failure is isolated

### Scraping — Facebook Groups

- [ ] **FBGR-01**: Scraper monitors user-configured Facebook group list for rental posts
- [ ] **FBGR-02**: Scraper uses saved authenticated Playwright session (manual login once)
- [ ] **FBGR-03**: Session health is checked before each run; alert sent when session expires and re-auth is needed
- [ ] **FBGR-04**: Scraper extracts: post text, poster name/link, post date, group name, post URL
- [ ] **FBGR-05**: Facebook Groups failure is isolated — does not block other scrapers

### Scraping — Facebook Marketplace

- [ ] **FBMP-01**: Scraper fetches rental listings in Haifa from Facebook Marketplace
- [ ] **FBMP-02**: Scraper uses same authenticated session as Facebook Groups
- [ ] **FBMP-03**: Scraper extracts: title, price, address or neighborhood, post date, listing URL
- [ ] **FBMP-04**: Facebook Marketplace failure is isolated

### LLM Verification

- [ ] **LLM-01**: Each scraped post is passed through an LLM to verify it is an actual rental listing (not a "looking for apartment" post, not a sale, not spam)
- [ ] **LLM-02**: LLM extracts and normalizes structured fields from free-form Hebrew text: price, rooms, size, address, contact info, availability date
- [ ] **LLM-03**: LLM assigns a confidence score to each extraction; listings below threshold are flagged and excluded from the map
- [ ] **LLM-04**: LLM-extracted fields override or supplement scraper-extracted fields when the scraper returns incomplete data (especially for Facebook free-form posts)
- [ ] **LLM-05**: LLM verification runs asynchronously after scraping — does not block the scraper pipeline
- [ ] **LLM-06**: Model used is configurable (default: Claude claude-haiku-4-5 for cost efficiency at high volume)

### Scheduler

- [ ] **SCHED-01**: All scrapers run automatically on a configurable interval (default: every 2 hours)
- [ ] **SCHED-02**: Overlapping runs are prevented (job lock — a new run does not start if previous is still running)
- [ ] **SCHED-03**: Scheduler is embedded in the backend process (APScheduler — no separate service needed)

### Storage & Data

- [ ] **DATA-01**: All listings stored in SQLite database with normalized schema
- [ ] **DATA-02**: Same-source deduplication: a listing already stored by its source ID is not inserted again
- [ ] **DATA-03**: Cross-source deduplication: listings from different sources that share price + room count + similar coordinates are merged into one record
- [ ] **DATA-04**: Each listing is geocoded (Hebrew address → lat/lng) via Nominatim; geocoding is done asynchronously and does not block scraper runs
- [ ] **DATA-05**: Listings are tagged with neighborhood (Carmel, Downtown, Neve Shanan) based on geocoded coordinates

### Map UI

- [ ] **MAP-01**: Interactive map (React-Leaflet + OpenStreetMap) shows all listings as pins
- [ ] **MAP-02**: Clicking a pin opens a listing card showing: price, rooms, size, contact info, post date, source, link to original post
- [ ] **MAP-03**: Map defaults to Haifa viewport (Carmel, Downtown, Neve Shanan)
- [ ] **MAP-04**: Filter panel: price range slider (max 4,500 ₪), room count toggle (2.5 / 3 / 3.5+), neighborhood toggle, "new only" toggle (last 24h / 48h)
- [ ] **MAP-05**: User can mark a listing as "seen" — pin fades and is hidden from the default view
- [ ] **MAP-06**: User can save a listing as a favorite — pinned with a distinct icon, accessible in a favorites list
- [ ] **MAP-07**: Full Hebrew RTL layout throughout the UI (dir="rtl" on html element from day one)
- [ ] **MAP-08**: UI is mobile-responsive and usable on a smartphone browser (primary device)

### Notifications

- [ ] **NOTF-01**: WhatsApp message sent to user when a new listing is found (Twilio WhatsApp API)
- [ ] **NOTF-02**: WhatsApp message includes: price, rooms, neighborhood, link to listing
- [ ] **NOTF-03**: Web Push notification sent as fallback (or simultaneously) for new listings
- [ ] **NOTF-04**: Notifications are rate-limited — no more than one batch per scraper run (not per individual listing)

### Infrastructure

- [ ] **INFRA-01**: App is deployed to a public URL accessible via smartphone browser
- [ ] **INFRA-02**: Server is hosted in Israel (required for Facebook Marketplace geo-filtering)
- [ ] **INFRA-03**: Backend and frontend run via Docker Compose for simple deployment
- [ ] **INFRA-04**: No authentication required — single user, direct access to the app URL

## v2 Requirements

### Enhanced Deduplication

- **DEDUP-01**: Fuzzy text matching on listing description to catch duplicates with slightly different addresses
- **DEDUP-02**: Admin view showing merged/duplicate pairs for manual review

### Scraper Dashboard

- **DASH-01**: Status page showing last run time, listings found per source, and error counts per scraper
- **DASH-02**: Manual "run now" trigger for any individual scraper

### Advanced Filters

- **FILT-01**: Filter by floor number
- **FILT-02**: Filter by apartment size (sqm)
- **FILT-03**: Filter by balcony / parking / elevator (from listings that include this data)

### Configurable Sources

- **CONF-01**: UI to add/remove Facebook groups without code changes
- **CONF-02**: UI to adjust scraping interval

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-user support / authentication | Personal use only — adds complexity with no benefit |
| Native mobile app (iOS/Android) | Responsive web is sufficient for the use case |
| Listings outside Haifa | Not relevant to current search |
| Automated rent negotiations or outreach | Out of scope — the app surfaces listings, contact is manual |
| Historical price analytics | v2+ — not needed for active apartment hunting |
| Listing photos display | Adds storage complexity; link to original post is sufficient |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| YAD2-01 | Phase 2 | Pending |
| YAD2-02 | Phase 2 | Pending |
| YAD2-03 | Phase 2 | Pending |
| YAD2-04 | Phase 2 | Pending |
| MADL-01 | Phase 6 | Pending |
| MADL-02 | Phase 6 | Pending |
| MADL-03 | Phase 6 | Pending |
| FBGR-01 | Phase 8 | Pending |
| FBGR-02 | Phase 8 | Pending |
| FBGR-03 | Phase 8 | Pending |
| FBGR-04 | Phase 8 | Pending |
| FBGR-05 | Phase 8 | Pending |
| FBMP-01 | Phase 8 | Pending |
| FBMP-02 | Phase 8 | Pending |
| FBMP-03 | Phase 8 | Pending |
| FBMP-04 | Phase 8 | Pending |
| LLM-01 | Phase 2 | Pending |
| LLM-02 | Phase 2 | Pending |
| LLM-03 | Phase 2 | Pending |
| LLM-04 | Phase 2 | Pending |
| LLM-05 | Phase 2 | Pending |
| LLM-06 | Phase 2 | Pending |
| SCHED-01 | Phase 3 | Pending |
| SCHED-02 | Phase 3 | Pending |
| SCHED-03 | Phase 3 | Pending |
| DATA-01 | Phase 1 | Pending |
| DATA-02 | Phase 1 | Pending |
| DATA-03 | Phase 5 | Pending |
| DATA-04 | Phase 5 | Pending |
| DATA-05 | Phase 5 | Pending |
| MAP-01 | Phase 4 | Pending |
| MAP-02 | Phase 4 | Pending |
| MAP-03 | Phase 4 | Pending |
| MAP-04 | Phase 4 | Pending |
| MAP-05 | Phase 4 | Pending |
| MAP-06 | Phase 4 | Pending |
| MAP-07 | Phase 4 | Pending |
| MAP-08 | Phase 4 | Pending |
| NOTF-01 | Phase 7 | Pending |
| NOTF-02 | Phase 7 | Pending |
| NOTF-03 | Phase 7 | Pending |
| NOTF-04 | Phase 7 | Pending |
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Pending |

**Coverage:**
- v1 requirements: 44 total
- Mapped to phases: 38
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-28*
*Last updated: 2026-03-28 after initial definition*
