"""Integration tests: Yad2 scraper + LLM verification pipeline end-to-end.

Tests verify the full pipeline:
  scrape -> LLM verify -> merge fields -> DB insert -> ScraperResult counts

All external I/O (httpx, LLM API) is mocked. DB uses in-memory SQLite.
"""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from sqlalchemy import select
from app.models.listing import Listing
from app.scrapers.yad2 import run_yad2_scraper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_yad2_item(id_val: str, title: str, price_str: str, city: str = "חיפה") -> dict:
    """Helper to create a mock Yad2 feed item in target neighborhood."""
    return {
        "id": id_val,
        "title_1": title,
        "price": price_str,
        "row_4": [{"value": "3"}],
        "row_3": [{"value": '75 מ"ר'}],
        "city": city,
        "neighborhood": "כרמל",
        "street": "רחוב הנשיא 15",
        "contact_name": "ישראל ישראלי",
        "date": "2026-04-01",
        "link_token": id_val,
    }


def _make_httpx_mock(feed_items: list[dict]):
    """Return a patched httpx.AsyncClient that returns the given feed items."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"feed": {"feed_items": feed_items}}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)
    return mock_client


# LLM responses for the 3-item pipeline tests
_VALID_LLM = {
    "is_rental": True,
    "rejection_reason": None,
    "confidence": 0.92,
    "price": 3500,
    "rooms": 3.0,
    "size_sqm": 75,
    "address": "רחוב הנשיא 15, כרמל, חיפה",
    "contact_info": "ישראל ישראלי",
}

_REJECTED_LLM = {
    "is_rental": False,
    "rejection_reason": "מחפש דירה - not a rental listing",
    "confidence": 0.95,
    "price": None,
    "rooms": None,
    "size_sqm": None,
    "address": None,
    "contact_info": None,
}

_LOW_CONF_LLM = {
    "is_rental": True,
    "rejection_reason": None,
    "confidence": 0.45,
    "price": 3000,
    "rooms": None,
    "size_sqm": None,
    "address": "חיפה",
    "contact_info": None,
}


# ---------------------------------------------------------------------------
# Test 1: Full pipeline — correct rows inserted into DB
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_pipeline_inserts_verified_listings(db_session):
    """Full pipeline: 3 scraped -> 1 rejected by LLM -> 2 inserted (valid + low-conf).

    The rejected listing (is_rental=False) must NOT appear in the database.
    The low-confidence listing MUST be inserted with llm_confidence=0.45.
    The valid listing MUST be inserted with llm_confidence=0.92.
    """
    items = [
        _make_yad2_item("id001", "דירה להשכרה בכרמל", "3,500 ₪"),       # valid rental
        _make_yad2_item("id002", "מחפש שותף לדירה", "3,000 ₪"),           # non-rental
        _make_yad2_item("id003", "דירה פנויה לשכירות", "3,000 ₪"),        # low confidence
    ]
    mock_client = _make_httpx_mock(items)

    with patch("app.scrapers.yad2.httpx.AsyncClient", return_value=mock_client):
        with patch(
            "app.scrapers.yad2.batch_verify_listings",
            new_callable=AsyncMock,
            return_value=[_VALID_LLM, _REJECTED_LLM, _LOW_CONF_LLM],
        ):
            await run_yad2_scraper(db_session)

    rows = (await db_session.execute(select(Listing))).scalars().all()

    # 2 rows inserted: valid + low-confidence. Rejected not in DB.
    assert len(rows) == 2, f"Expected 2 rows in DB, got {len(rows)}"

    by_id = {r.source_id: r for r in rows}
    assert "id001" in by_id, "Valid rental (id001) should be in DB"
    assert "id002" not in by_id, "Rejected listing (id002) must NOT be in DB"
    assert "id003" in by_id, "Low-confidence listing (id003) should be in DB"

    assert by_id["id001"].llm_confidence == pytest.approx(0.92)
    assert by_id["id003"].llm_confidence == pytest.approx(0.45)


# ---------------------------------------------------------------------------
# Test 2: ScraperResult counts are accurate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_pipeline_scraper_result_counts(db_session):
    """ScraperResult counters must accurately reflect each pipeline stage.

    listings_found=3, listings_rejected=1, listings_flagged=1, listings_inserted=2.
    """
    items = [
        _make_yad2_item("id011", "דירה להשכרה בכרמל", "3,500 ₪"),
        _make_yad2_item("id012", "מחפש דירה", "3,000 ₪"),
        _make_yad2_item("id013", "דירה פנויה", "3,000 ₪"),
    ]
    mock_client = _make_httpx_mock(items)

    with patch("app.scrapers.yad2.httpx.AsyncClient", return_value=mock_client):
        with patch(
            "app.scrapers.yad2.batch_verify_listings",
            new_callable=AsyncMock,
            return_value=[_VALID_LLM, _REJECTED_LLM, _LOW_CONF_LLM],
        ):
            result = await run_yad2_scraper(db_session)

    assert result.listings_found == 3, f"Expected listings_found=3, got {result.listings_found}"
    assert result.listings_rejected == 1, (
        f"Expected listings_rejected=1, got {result.listings_rejected}"
    )
    assert result.listings_flagged == 1, (
        f"Expected listings_flagged=1, got {result.listings_flagged}"
    )
    assert result.listings_inserted == 2, (
        f"Expected listings_inserted=2, got {result.listings_inserted}"
    )


# ---------------------------------------------------------------------------
# Test 3: LLM fills null fields, scraper values preserved
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_fields_merged_in_db(db_session):
    """merge_llm_fields: scraper non-null fields win; LLM fills null fields.

    Feed item has price=3500 (from scraper parse) but no rooms in raw data.
    LLM returns rooms=3.0 and price=4000.
    DB row must have price=3500 (scraper) and rooms=3.0 (LLM filled null).
    """
    # Item has no row_4 (rooms) field — scraper will parse rooms=None
    item = {
        "id": "id021",
        "title_1": "דירה להשכרה",
        "price": "3,500 ₪",
        "city": "חיפה",
        "neighborhood": "כרמל",
        "street": "רחוב הרצל 1",
        "contact_name": "אביב לוי",
        "date": "2026-04-01",
        "link_token": "id021",
        # Note: no row_4 — rooms will be None after parse_listing
    }
    mock_client = _make_httpx_mock([item])

    llm_response = {
        "is_rental": True,
        "rejection_reason": None,
        "confidence": 0.90,
        "price": 4000,   # LLM extracted different price — scraper's 3500 must win
        "rooms": 3.0,    # LLM fills the null scraper value
        "size_sqm": 80,
        "address": "רחוב הרצל 1, כרמל, חיפה",
        "contact_info": "אביב לוי",
    }

    with patch("app.scrapers.yad2.httpx.AsyncClient", return_value=mock_client):
        with patch(
            "app.scrapers.yad2.batch_verify_listings",
            new_callable=AsyncMock,
            return_value=[llm_response],
        ):
            await run_yad2_scraper(db_session)

    row = (await db_session.execute(select(Listing))).scalars().first()
    assert row is not None, "Expected 1 row in DB"

    # Scraper value preserved (3500, not LLM's 4000)
    assert row.price == 3500, (
        f"Expected price=3500 (scraper wins), got {row.price}"
    )
    # LLM filled the null — rooms was None from scraper, now 3.0
    assert row.rooms == pytest.approx(3.0), (
        f"Expected rooms=3.0 (LLM filled null), got {row.rooms}"
    )
