"""Tests for Madlan scraper requirements MADL-01 through MADL-03.

Tests use real async DB sessions (in-memory SQLite) and mock Playwright
to verify scraper behavior without hitting live Madlan endpoints.
Mirrors test_yad2_scraper.py structure exactly.
"""

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock

# Skip entire module if the scraper module does not yet exist
pytest.importorskip("app.scrapers.madlan")

from app.scrapers.madlan import run_madlan_scraper, parse_listing
from app.models.listing import Listing


# ---------------------------------------------------------------------------
# Test fixtures — Madlan listing dicts using the field structure from discovery
# ---------------------------------------------------------------------------

CARMEL_LISTING_MADLAN = {
    "id": "madlan_carmel_001",
    "description": "דירה 3 חדרים בכרמל חיפה",
    "price": 3500,
    "rooms": 3.0,
    "squareMeter": 75,
    "address": {
        "city": {"text": "חיפה"},
        "neighborhood": {"text": "כרמל"},
        "street": {"text": "רחוב הנשיא"},
        "houseNum": "15",
    },
    "coordinates": {"lat": 32.8, "lng": 35.0},
    "contactName": "ישראל ישראלי",
    "publishedAt": "2026-04-01T10:00:00",
}

NON_TARGET_LISTING_MADLAN = {
    "id": "madlan_kiriat_001",
    "description": "דירה בקריית חיים",
    "price": 3000,
    "rooms": 2.0,
    "squareMeter": 60,
    "address": {
        "city": {"text": "חיפה"},
        "neighborhood": {"text": "קריית חיים"},
        "street": {"text": "רחוב אחר"},
        "houseNum": "5",
    },
    "coordinates": {"lat": 32.83, "lng": 35.07},
    "contactName": "שמואל כהן",
    "publishedAt": "2026-04-01T10:00:00",
}

EXPENSIVE_LISTING_MADLAN = {
    "id": "madlan_expensive_001",
    "description": "דירת יוקרה בכרמל",
    "price": 6000,
    "rooms": 4.0,
    "squareMeter": 100,
    "address": {
        "city": {"text": "חיפה"},
        "neighborhood": {"text": "כרמל"},
        "street": {"text": "רחוב הגפן"},
        "houseNum": "3",
    },
    "coordinates": {"lat": 32.8, "lng": 35.0},
    "contactName": "אביב לוי",
    "publishedAt": "2026-04-01T10:00:00",
}


# ---------------------------------------------------------------------------
# Task 1 test — Neighborhood and price filtering (MADL-01)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_madlan_scraper_returns_haifa_listings_filtered(
    db_session, llm_valid_rental_response
):
    """MADL-01: Only target-neighborhood listings (כרמל) within budget are inserted.
    Non-target (קריית חיים) and over-budget listings are discarded."""
    mock_listings = [
        CARMEL_LISTING_MADLAN,
        NON_TARGET_LISTING_MADLAN,
        EXPENSIVE_LISTING_MADLAN,
    ]

    with patch(
        "app.scrapers.madlan.fetch_madlan_browser",
        new_callable=AsyncMock,
        return_value=mock_listings,
    ):
        with patch(
            "app.scrapers.madlan.batch_verify_listings",
            new_callable=AsyncMock,
            return_value=[llm_valid_rental_response],
        ):
            result = await run_madlan_scraper(db_session)

    # Only the CARMEL listing passes both neighborhood and price filters
    assert result.listings_found == 1, (
        f"Expected 1 found, got {result.listings_found}"
    )
    assert result.listings_inserted == 1, (
        f"Expected 1 inserted, got {result.listings_inserted}"
    )

    # Verify DB state
    from sqlalchemy import select
    rows = (await db_session.execute(select(Listing))).scalars().all()
    assert len(rows) == 1
    inserted = rows[0]
    assert "כרמל" in (inserted.address or ""), (
        f"Expected כרמל in address, got {inserted.address}"
    )
    assert inserted.price is not None
    assert inserted.price <= 4500


# ---------------------------------------------------------------------------
# Task 2 test — Required fields extraction (MADL-02)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_madlan_scraper_extracts_all_required_fields(
    db_session, llm_valid_rental_response
):
    """MADL-02: All required listing fields are extracted and persisted correctly."""
    with patch(
        "app.scrapers.madlan.fetch_madlan_browser",
        new_callable=AsyncMock,
        return_value=[CARMEL_LISTING_MADLAN],
    ):
        with patch(
            "app.scrapers.madlan.batch_verify_listings",
            new_callable=AsyncMock,
            return_value=[llm_valid_rental_response],
        ):
            result = await run_madlan_scraper(db_session)

    assert result.success is True

    from sqlalchemy import select
    row = (await db_session.execute(select(Listing))).scalars().first()
    assert row is not None

    # Required fields must be non-null
    assert row.title is not None and row.title != "", f"title is empty: {row.title!r}"
    assert row.price is not None, "price is None"
    assert row.rooms is not None, "rooms is None"
    assert row.address is not None and row.address != "", f"address is empty: {row.address!r}"
    assert row.url is not None and row.url != "", f"url is empty: {row.url!r}"
    assert row.source_id is not None and row.source_id != "", f"source_id is empty"

    # Correct source metadata
    assert row.source == "madlan", f"Expected source=madlan, got {row.source}"
    assert row.source_badge == "מדלן", f"Expected source_badge=מדלן, got {row.source_badge}"

    # Correct field values
    assert row.price == 3500, f"Expected price=3500, got {row.price}"
    assert row.rooms == 3.0, f"Expected rooms=3.0, got {row.rooms}"
    assert row.size_sqm == 75, f"Expected size_sqm=75, got {row.size_sqm}"
    assert "כרמל" in (row.address or ""), f"Expected כרמל in address, got {row.address}"
    assert row.source_id == "madlan_carmel_001", f"source_id mismatch: {row.source_id}"
    assert row.url == "https://www.madlan.co.il/listings/madlan_carmel_001", (
        f"url mismatch: {row.url}"
    )


# ---------------------------------------------------------------------------
# Task 3 test — Error isolation (MADL-03)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_madlan_scraper_error_isolation(db_session):
    """MADL-03: Playwright failure is caught; ScraperResult.success=False,
    errors populated, no exception propagated to caller."""
    with patch(
        "app.scrapers.madlan.fetch_madlan_browser",
        new_callable=AsyncMock,
        side_effect=Exception("Playwright launch failed — PerimeterX blocked"),
    ):
        # Should NOT raise — error must be caught internally
        result = await run_madlan_scraper(db_session)

    assert result.success is False, "Expected success=False on scraper failure"
    assert len(result.errors) > 0, "Expected errors to be populated"
    assert result.source == "madlan", f"Expected source=madlan, got {result.source}"

    # DB should be empty — no listings were inserted
    from sqlalchemy import select
    rows = (await db_session.execute(select(Listing))).scalars().all()
    assert len(rows) == 0, f"Expected 0 rows in DB after failure, got {len(rows)}"


# ---------------------------------------------------------------------------
# Task 4 test — Health dict initialization (D-05)
# ---------------------------------------------------------------------------


def test_madlan_health_dict_initialized():
    """D-05: 'madlan' key exists in scheduler _health dict from startup."""
    from app.scheduler import _health
    assert "madlan" in _health, (
        f"'madlan' key missing from _health. Found: {list(_health.keys())}"
    )
    # yad2 must still be present
    assert "yad2" in _health, (
        f"'yad2' key missing from _health. Found: {list(_health.keys())}"
    )


# ---------------------------------------------------------------------------
# Additional tests — parse_listing correctness
# ---------------------------------------------------------------------------


def test_parse_listing_sets_madlan_fields():
    """parse_listing() correctly sets source, source_badge, and URL for Madlan."""
    item = {
        "id": "EaW4wX1L38K",
        "description": "דירה מרהיבה בכרמל",
        "price": 4000,
        "rooms": 3.5,
        "squareMeter": 85,
        "address": {
            "city": {"text": "חיפה"},
            "neighborhood": {"text": "כרמל"},
            "street": {"text": "שדרות הנשיא"},
        },
        "contactName": "מוכרת",
        "publishedAt": "2026-04-02T12:00:00",
    }

    result = parse_listing(item)

    assert result is not None
    assert result["source"] == "madlan"
    assert result["source_badge"] == "מדלן"
    assert result["source_id"] == "EaW4wX1L38K"
    assert result["url"] == "https://www.madlan.co.il/listings/EaW4wX1L38K"
    assert result["price"] == 4000
    assert result["rooms"] == 3.5
    assert result["size_sqm"] == 85
    assert result["contact_info"] == "מוכרת"


def test_parse_listing_returns_none_for_missing_id():
    """parse_listing() returns None when source_id is missing."""
    item = {
        "price": 3000,
        "rooms": 2.5,
    }
    assert parse_listing(item) is None


def test_parse_listing_handles_nested_address():
    """parse_listing() correctly flattens Madlan nested address object."""
    item = {
        "id": "test_addr_001",
        "address": {
            "city": {"text": "חיפה"},
            "neighborhood": {"text": "מרכז העיר"},
            "street": {"text": "רחוב הרצל"},
            "houseNum": "42",
        },
    }
    result = parse_listing(item)
    assert result is not None
    assert "מרכז העיר" in (result["address"] or "")
    assert "חיפה" in (result["address"] or "")
    assert "42" in (result["address"] or "")


def test_parse_listing_handles_flat_fields():
    """parse_listing() handles flat (non-nested) field structure as fallback."""
    item = {
        "id": "flat_001",
        "price": "3,200 ₪",  # string price with ₪ symbol
        "rooms": "2.5",       # string rooms
        "neighborhood": "נווה שאנן",
        "street": "רחוב בר יהודה",
        "city": "חיפה",
    }
    result = parse_listing(item)
    assert result is not None
    assert result["price"] == 3200
    assert result["rooms"] == 2.5
    assert "נווה שאנן" in (result["address"] or "")
