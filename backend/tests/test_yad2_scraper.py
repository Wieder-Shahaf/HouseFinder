"""Tests for Yad2 scraper requirements YAD2-01 through YAD2-04.

Tests use real async DB sessions (in-memory SQLite) and mock httpx/Playwright
to verify scraper behavior without hitting live Yad2 endpoints.

After Plan 04 integration, batch_verify_listings is also mocked so tests
remain deterministic regardless of LLM availability.
"""

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock

# Skip entire module if the scraper module does not yet exist
pytest.importorskip("app.scrapers.yad2")

from app.scrapers.yad2 import run_yad2_scraper
from app.models.listing import Listing


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_yad2_response(items: list[dict]) -> dict:
    """Wrap listing items in Yad2 feed API response envelope."""
    return {"feed": {"feed_items": items}}


CARMEL_LISTING = {
    "id": "abc123",
    "title_1": "דירה 3 חדרים בכרמל",
    "price": "3,500 ₪",
    "row_4": [{"value": "3"}],        # rooms
    "row_3": [{"value": '75 מ"ר'}],   # size
    "city": "חיפה",
    "neighborhood": "כרמל",
    "street": "רחוב הנשיא 15",
    "contact_name": "ישראל ישראלי",
    "date": "2026-04-01",
    "link_token": "abc123",
}

NON_TARGET_LISTING = {
    "id": "xyz999",
    "title_1": "דירה בקריית חיים",
    "price": "3,000 ₪",
    "row_4": [{"value": "2"}],
    "row_3": [{"value": '60 מ"ר'}],
    "city": "חיפה",
    "neighborhood": "קריית חיים",
    "street": "רחוב אחר 5",
    "contact_name": "שמואל כהן",
    "date": "2026-04-01",
    "link_token": "xyz999",
}

EXPENSIVE_LISTING = {
    "id": "exp111",
    "title_1": "דירת יוקרה בכרמל",
    "price": "6,000 ₪",
    "row_4": [{"value": "4"}],
    "row_3": [{"value": '100 מ"ר'}],
    "city": "חיפה",
    "neighborhood": "כרמל",
    "street": "רחוב הגפן 3",
    "contact_name": "אביב לוי",
    "date": "2026-04-01",
    "link_token": "exp111",
}


# ---------------------------------------------------------------------------
# Task 1 tests — httpx API path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scraper_returns_haifa_listings_filtered_by_neighborhood_and_price(
    db_session, llm_valid_rental_response,
):
    """YAD2-01: Only target-neighborhood listings (כרמל) are inserted; non-target (קריית חיים)
    and over-budget listings are discarded."""
    mock_response = make_yad2_response([CARMEL_LISTING, NON_TARGET_LISTING, EXPENSIVE_LISTING])

    mock_http_response = MagicMock()
    mock_http_response.raise_for_status = MagicMock()
    mock_http_response.json.return_value = mock_response

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_http_response)

    with patch("app.scrapers.yad2.httpx.AsyncClient", return_value=mock_client):
        with patch("app.scrapers.yad2.batch_verify_listings",
                   new_callable=AsyncMock,
                   return_value=[llm_valid_rental_response]) as mock_batch:
            result = await run_yad2_scraper(db_session)

    # Only the CARMEL listing passes both filters
    assert result.listings_found == 1, f"Expected 1 found, got {result.listings_found}"
    assert result.listings_inserted == 1, f"Expected 1 inserted, got {result.listings_inserted}"

    # Verify DB state
    from sqlalchemy import select
    rows = (await db_session.execute(select(Listing))).scalars().all()
    assert len(rows) == 1
    inserted = rows[0]
    assert "כרמל" in (inserted.address or "")
    assert inserted.price is not None
    assert inserted.price <= 4500


@pytest.mark.asyncio
async def test_scraper_extracts_all_required_fields(db_session, llm_valid_rental_response):
    """YAD2-02: All required listing fields are extracted and persisted correctly."""
    mock_response = make_yad2_response([CARMEL_LISTING])

    mock_http_response = MagicMock()
    mock_http_response.raise_for_status = MagicMock()
    mock_http_response.json.return_value = mock_response

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_http_response)

    with patch("app.scrapers.yad2.httpx.AsyncClient", return_value=mock_client):
        with patch("app.scrapers.yad2.batch_verify_listings",
                   new_callable=AsyncMock,
                   return_value=[llm_valid_rental_response]):
            result = await run_yad2_scraper(db_session)

    assert result.success is True

    from sqlalchemy import select
    row = (await db_session.execute(select(Listing))).scalars().first()
    assert row is not None

    # Required fields must be non-null
    assert row.title is not None and row.title != ""
    assert row.price is not None
    assert row.rooms is not None
    assert row.address is not None and row.address != ""
    assert row.url is not None and row.url != ""
    assert row.source_id is not None and row.source_id != ""

    # Correct values
    assert row.source == "yad2"
    assert row.source_badge == "יד2"
    assert row.price == 3500
    assert row.rooms == 3.0
    assert row.size_sqm == 75
    assert "כרמל" in row.address
    assert row.contact_info == "ישראל ישראלי"
    assert row.url == "https://www.yad2.co.il/item/abc123"


@pytest.mark.asyncio
async def test_scraper_error_isolation_returns_scraper_result(db_session):
    """YAD2-04: ConnectionError is caught; ScraperResult.success=False, errors populated, no exception raised."""
    import httpx

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

    with patch("app.scrapers.yad2.httpx.AsyncClient", return_value=mock_client):
        # Also patch Playwright fallback to also raise so we test full error isolation
        with patch("app.scrapers.yad2.fetch_yad2_browser", new_callable=AsyncMock,
                   side_effect=Exception("Playwright also failed")):
            # batch_verify_listings should not be called if fetch fails,
            # but patch it in case error path changes
            with patch("app.scrapers.yad2.batch_verify_listings",
                       new_callable=AsyncMock, return_value=[]):
                result = await run_yad2_scraper(db_session)

    assert result.success is False
    assert len(result.errors) > 0
    assert result.source == "yad2"


# ---------------------------------------------------------------------------
# Task 2 test — Playwright fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_playwright_fallback_on_httpx_403(db_session, llm_valid_rental_response):
    """YAD2-03: When httpx returns 403, Playwright fallback is invoked and listings are returned."""
    import httpx

    # Mock httpx to raise HTTPStatusError with 403
    mock_response_obj = MagicMock()
    mock_response_obj.status_code = 403
    mock_response_obj.request = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(
        side_effect=httpx.HTTPStatusError("403 Forbidden", request=mock_response_obj.request, response=mock_response_obj)
    )

    # Mock the Playwright fallback to return a valid listing
    browser_listings = [CARMEL_LISTING]

    with patch("app.scrapers.yad2.httpx.AsyncClient", return_value=mock_client):
        with patch("app.scrapers.yad2.fetch_yad2_browser", new_callable=AsyncMock,
                   return_value=browser_listings):
            with patch("app.scrapers.yad2.batch_verify_listings",
                       new_callable=AsyncMock,
                       return_value=[llm_valid_rental_response]):
                result = await run_yad2_scraper(db_session)

    assert result.success is True
    assert result.listings_found >= 1, f"Expected listings_found >= 1, got {result.listings_found}"
    assert result.source == "yad2"
