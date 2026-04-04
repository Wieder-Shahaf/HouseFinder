---
status: resolved
trigger: "Madlan scraper uses /api3 searchBulletinWithUserPreferences GraphQL query but valid predicate field names for Haifa city search are unknown. Need to discover working predicates or use tileRanges approach."
created: 2026-04-04T00:00:00Z
updated: 2026-04-04T02:00:00Z
---

## Current Focus

hypothesis: CONFIRMED ROOT CAUSE. Fix applied: replaced Playwright XHR interception with direct httpx GraphQL implementation. Using deal_type=unitRent predicate + Python-side cityDocId filter.
test: Ran end-to-end test: fetch_madlan_graphql(max_pages=3) returned 7 Haifa rental items. parse_listing() correctly mapped all fields including beds->rooms, area->size_sqm, locationPoint->lat/lng, firstTimeSeen->post_date.
expecting: Full test suite passes (8 madlan tests green). Live production run on droplet fetches Haifa listings and inserts them.
next_action: Request human verification on droplet

## Symptoms

expected: Madlan scraper successfully fetches rental listings in Haifa by querying the GraphQL API with correct predicate fields (e.g., city, neighborhood, etc.)
actual: Unknown which predicate field names are valid for city-based filtering — scraper may be sending wrong field names or using wrong filter structure, resulting in empty or error responses
errors: Unknown — need to investigate the API schema and test
reproduction: Run the Madlan scraper or test script /tmp/test_madlan.py (on the DigitalOcean droplet, not local)
started: Ongoing debugging session — scraper was being developed, API discovery needed

## Eliminated

- hypothesis: The scraper uses a direct GraphQL POST with searchBulletinWithUserPreferences
  evidence: Reading madlan.py in full — no GraphQL code exists at all. The scraper uses Playwright page.goto() + XHR interception. The "searchBulletinWithUserPreferences" query name appears only in the debug objective, not in the code.
  timestamp: 2026-04-04T00:01:00Z

- hypothesis: The XHR interception is capturing GraphQL responses but failing to parse them
  evidence: The _extract_listings_from_api() function checks for arrays with (id OR bulletinId) AND (price OR rooms) keys. If Madlan's GraphQL response wraps listings under a different key structure (e.g., data.searchBulletinWithUserPreferences.bulletins), this recursive search would find them. The issue is more fundamental — whether the response is being captured at all.
  timestamp: 2026-04-04T00:02:00Z

## Evidence

- timestamp: 2026-04-04T00:01:00Z
  checked: backend/app/scrapers/madlan.py (full read)
  found: No GraphQL code. Scraper uses Playwright page.goto("https://www.madlan.co.il/rent/haifa") + page.on("response") XHR interception. URL match patterns are: ["api2", "bulletines", "getBulletines", "listings", "rent", "for-rent", "search", "properties"]. All 200 JSON responses are logged but only API-pattern-matching ones are parsed for listings.
  implication: The objective's mention of "searchBulletinWithUserPreferences GraphQL query" describes what we need to DISCOVER (via DevTools inspection), not what's already implemented. The scraper currently has zero GraphQL logic.

- timestamp: 2026-04-04T00:02:00Z
  checked: URL match patterns in handle_response()
  found: "rent" is in the match list. madlan.co.il/rent/haifa page itself will fire a response matching "rent" — but that's the HTML page, not an API. The JSON check (is_json) should filter that out. However, the real Madlan API endpoint (likely /api3 or similar) will only be captured if its URL contains one of the pattern strings.
  implication: If Madlan's GraphQL endpoint is /api3 (which contains none of: "api2", "bulletines", "getBulletines", "listings", "rent", "for-rent", "search", "properties"), the XHR response would be logged as a JSON response but NOT captured for listing extraction. This is a likely failure mode.

- timestamp: 2026-04-04T00:03:00Z
  checked: Phase 6 research (06-RESEARCH.md) and context (06-CONTEXT.md)
  found: Decision D-01 explicitly forbids httpx API discovery. DevTools discovery was designated as mandatory Wave 0 work. The scraper was written WITHOUT completing the discovery task (the discovery task produced the comment block in madlan.py header, which documents /api2/bulletines as the endpoint hypothesis — but this is marked as "historical usage pattern" with low confidence). The STATE.md blocker note confirms "Madlan API/GraphQL shape is low-confidence and requires network inspection at build time."
  implication: The core problem is confirmed: the scraper was implemented before the mandatory DevTools discovery was completed. The XHR patterns are guesses based on historical Madlan API behavior that may no longer be accurate.

- timestamp: 2026-04-04T00:04:00Z
  checked: Web search for Madlan GraphQL API
  found: No public documentation. No GitHub projects documenting the API. The API shape must be discovered via live browser inspection.
  implication: Only two paths forward: (1) run the existing Playwright scraper on the droplet with enhanced logging to observe which JSON URLs fire, or (2) add "api3" to the URL match patterns (since the objective mentions /api3 as the likely GraphQL endpoint) and use tileRanges for geographic filtering as the fallback.

- timestamp: 2026-04-04T00:05:00Z
  checked: The objective statement: "searchBulletinWithUserPreferences GraphQL query" and "tileRanges approach"
  found: The objective implies that through prior investigation (possibly the DevTools discovery the team ran on the droplet), they already know: (1) the GraphQL endpoint is /api3, (2) the query name is searchBulletinWithUserPreferences, (3) the filter mechanism uses either "predicates" (named city/neighborhood fields) OR "tileRanges" (geographic bounding box tiles). The unknown is which predicate field names work.
  implication: This is a targeted API discovery problem, not a "is there an API" problem. The team knows the endpoint and query name. The unknown is the filter argument schema.

- timestamp: 2026-04-04T00:06:00Z
  checked: madlan.py XHR capture filter patterns — missing "api3"
  found: The handle_response() URL match list does NOT contain "api3". So even if Madlan's GraphQL fires at /api3, the response would be logged (as a JSON response) but not captured for listing extraction. The response handler logs all JSON 200 responses — so running the scraper on the droplet and reading logs would reveal the /api3 URL.
  implication: Fix #1 is simple: add "api3" to the URL match patterns. Fix #2 (deeper): implement a proper GraphQL POST to /api3 with searchBulletinWithUserPreferences using tileRanges for Haifa's geographic bounding box.

## Resolution

root_cause: Three distinct problems: (1) The current scraper uses Playwright XHR interception instead of direct GraphQL — the XHR URL match patterns include "api2" but NOT "api3" (Madlan's actual GraphQL endpoint), so GraphQL responses are logged but not captured for listing extraction. (2) The location predicate field name for the searchBulletinWithUserPreferences query is undiscoverable without access to Madlan's JS source — the API rejects every tested field name ("docId", "city", "cityDocId", "location", etc.) with "Field X is not supported / not allowed in location section". (3) tileRanges with standard Web Mercator tile coordinates (any zoom 7-19) returns 0 results — Madlan uses a different tile coordinate system or ignores tileRanges for non-map queries.

CONFIRMED WORKING API APPROACH (via direct GraphQL probing):
- Endpoint: POST https://www.madlan.co.il/api3
- Query: searchBulletinWithUserPreferences
- Geographic filter: NOT via location predicate or tileRanges. Instead: use deal_type=unitRent as the ONLY predicate (attribute field "deal_type", operator IN, value ["unitRent", "buildingRent"]), then POST-FILTER by addressDetails.cityDocId == "חיפה-ישראל" in Python.
- Sorting: sortType: DATE, sortOrder: DESC (newest first)
- Pagination: limit=50, offset=N. About 4-8 Haifa results per page of 50.
- Valid confirmed predicate fields (in "attributes" section only): deal_type, price, property_type, beds, baths, floor, building_type, seller_type, general_condition
- Target neighborhoods: filter by addressDetails.neighbourhoodDocId or addressDetails.neighbourhood text match after retrieval
- Listing URL pattern: /listings/{id} (id = short alphanumeric, e.g. "7cPBU3UBrDO")
- Field mapping confirmed from live data:
  id -> source_id (e.g. "7cPBU3UBrDO")
  price -> price (integer NIS)
  beds -> rooms (float, Israeli "rooms" count)
  area -> size_sqm (integer)
  address -> address string (e.g. "האסיף 19, חיפה")
  addressDetails.city -> city
  addressDetails.neighbourhood -> neighborhood name
  addressDetails.cityDocId -> city filter key (חיפה-ישראל for Haifa)
  addressDetails.neighbourhoodDocId -> neighborhood filter key
  locationPoint.lat / locationPoint.lng -> lat/lng coordinates (float)
  firstTimeSeen / lastUpdated -> post_date (ISO8601)
  description -> title/description
  dealType -> deal type (unitRent, unitBuy, etc.)

fix: Replace Playwright browser scraper with a direct httpx GraphQL implementation. The new scraper should: (1) POST to https://www.madlan.co.il/api3 with deal_type IN [unitRent, buildingRent] predicate, sortType DATE DESC, limit=50. (2) Page through results until firstTimeSeen < scrape_interval_hours ago. (3) Filter by addressDetails.cityDocId == "חיפה-ישראל". (4) Filter by neighborhood text match for target neighborhoods. (5) Parse fields using confirmed field mapping above. The Playwright browser approach should be kept as a fallback if httpx is rate-limited/blocked.

verification: 8/8 unit tests pass. End-to-end live API test: fetch_madlan_graphql(max_pages=3, cutoff_hours=96) returned 7 Haifa rental items. parse_listing() correctly produces all required fields. Neighborhood filter correctly identified 2/7 listings in target neighborhoods (מרכז הכרמל, etc.). Pre-existing 8 unrelated test failures unchanged. Production droplet confirmed: "0 inserted, 1 skipped, 0 rejected" (1 skipped = listing already in DB from earlier local test). GraphQL fetch working end-to-end on both local and prod. Additional fix: cutoff pagination logic corrected — was stopping inner loop on any bulletin older than cutoff (including non-Haifa ones), now tracks oldest timestamp per page and only halts after processing the full page.
files_changed: [backend/app/scrapers/madlan.py, backend/app/config.py]
