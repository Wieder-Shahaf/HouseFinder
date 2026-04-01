"""Test stubs for Yad2 scraper requirements YAD2-01 through YAD2-04.

All tests skip cleanly until Plan 02 creates app.scrapers.yad2.
Each test documents the acceptance criteria for the scraper implementation.
"""

import pytest

# Skip entire module if the scraper module does not yet exist
pytest.importorskip("app.scrapers.yad2")


def test_scraper_returns_haifa_listings_filtered_by_neighborhood_and_price(
    yad2_api_response_fixture,
):
    """YAD2-01: Scraper returns only listings from the three target Haifa
    neighborhoods (כרמל, מרכז העיר, נווה שאנן) with price <= 4500 ILS.

    Neighborhood filtering must be enforced — not just city-level (Haifa).
    Listings outside target neighborhoods or above price cap must be excluded.
    """
    pytest.skip("Implementation in Plan 02")


def test_scraper_extracts_all_required_fields(yad2_api_response_fixture):
    """YAD2-02: Scraper correctly extracts all required listing fields.

    Required fields: title, price (int, ILS), rooms (float), size_sqm (int),
    address (str), contact_info (str), post_date (datetime), url (str).
    All extracted values must match source data types without loss.
    """
    pytest.skip("Implementation in Plan 02")


def test_playwright_fallback_on_httpx_403():
    """YAD2-03: When the httpx direct API call returns HTTP 403, the scraper
    falls back to Playwright browser automation automatically.

    The fallback must be transparent — ScraperResult.source remains 'yad2'
    and the listing data shape is identical regardless of which path was used.
    """
    pytest.skip("Implementation in Plan 02")


def test_scraper_error_isolation_returns_scraper_result():
    """YAD2-04: When the scraper encounters an unexpected error (network
    timeout, parsing failure, etc.), it catches the exception, records the
    error message in ScraperResult.errors, and returns a ScraperResult with
    success=False instead of propagating the exception.

    No unhandled exception must escape run_yad2_scraper().
    """
    pytest.skip("Implementation in Plan 02")
