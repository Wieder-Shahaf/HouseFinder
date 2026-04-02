# Phase 5: Discussion Log

**Session:** 2026-04-02
**Areas discussed:** Neighborhood boundaries, Dedup merge behavior, Geocoding trigger & rate limiting, Dedup timing

---

## Neighborhood Boundaries

**Q: How should neighborhoods be defined spatially?**
Options: Hand-drawn bounding boxes / Nominatim reverse geocoding / GeoJSON polygons
→ **Selected: Hand-drawn bounding boxes**

**Q: What happens to listings outside all 3 bounding boxes?**
Options: Unassigned (null, still visible) / "Other" catch-all tag / Discard
→ **Selected: Unassigned — show on map, no neighborhood tag**

**Q: Where should bounding boxes live?**
Options: Hardcoded in Python / In .env / settings.py
→ **Selected: Hardcoded in Python (geocoding.py)**

---

## Dedup Merge Behavior

**Q: What does 'merge' mean for the data model?**
Options: Deactivate the duplicate / Add canonical_id FK
→ **Selected: Deactivate the duplicate (is_active=False)**

**Q: What's the matching fingerprint?**
Options: Price + rooms + 100m / Price + rooms + 150m / Price tolerance + rooms + 100m
→ **Selected: Price + rooms + 100m (exact match)**

**Q: How should is_seen/is_favorited be handled on merge?**
Options: Keep canonical's state / OR-merge (promote if either is set)
→ **Selected: Keep canonical's state only**

---

## Geocoding Trigger & Rate Limiting

**Q: Should Yad2 listings (already have lat/lng) be skipped?**
Options: Only geocode NULL lat/lng / Always geocode (overwrite with Nominatim)
→ **Selected: Yes — only geocode NULL lat/lng**

**Q: What happens when geocoding fails?**
Options: Keep listing, retry later / Keep listing, no retry
→ **Selected: Keep listing, retry later**
User note: *"try google search or google maps for lat lng"*

**Q: What geocoding strategy should be used?**
Options: Nominatim primary + Google Maps API fallback / Nominatim only / Google Maps only
→ **Selected: Nominatim primary + Playwright/Web Unlocker Google Maps fallback**
User note: *"use playwright for google search with headless browser and the web unlocker to get search results for the address in hebrew and the google display usually the details lat lng in the results or search in google maps via the browser"*

---

## Dedup Timing & Trigger

**Q: When does cross-source dedup run?**
Options: After each scraper run (APScheduler chain) / Inline on insert / On-demand API
→ **Selected: After each scraper run as chained APScheduler jobs (scrape → geocode → dedup)**

**Q: Should geocoding pass run synchronously or async?**
Options: Synchronous in scheduler job / Async background task
→ **Selected: Synchronous in scheduler job**

**Q: Should neighborhood be stored as a DB column or computed at query time?**
Options: Add neighborhood column via Alembic migration / Compute at query time
→ **Selected: Add neighborhood column via Alembic migration**

---

*Log generated: 2026-04-02*
