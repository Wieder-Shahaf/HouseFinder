# Deferred Items — Phase 07

## Pre-Existing Test Failures (out of scope for Plan 07-01)

These failures existed before Phase 07 work began. Not introduced by our changes.

| Test | File | Issue |
|------|------|-------|
| test_get_listings_neighborhood_filter | test_api.py | Neighborhood filter returns 0 results (assert 0 == 1) |
| test_listings_table_columns | test_database.py | Schema assertion mismatch |
| test_neighborhood_filter_returns_matching_listings | test_listings_neighborhood.py | Neighborhood filter returns 0 results |
| test_no_neighborhood_filter_returns_all_active | test_listings_neighborhood.py | Active listings count mismatch |
| test_neighborhood_filter_no_match_returns_empty | test_listings_neighborhood.py | Expected behavior not met |
| test_neighborhood_field_present_in_response | test_listings_neighborhood.py | Field not in response |
| test_null_neighborhood_listing_not_returned_when_filtering | test_listings_neighborhood.py | Filter not excluding null neighborhood |
| test_scrape_job_updates_health_on_success | test_scheduler.py | AsyncMock coroutine never awaited |

**Recorded:** 2026-04-03 during 07-01 execution
