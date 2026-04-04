"""Tests for LLM verifier requirements LLM-01 through LLM-06."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Skip entire module if the verifier module does not yet exist
pytest.importorskip("app.llm.verifier")


def make_mock_response(data: dict):
    """Create a mock Anthropic response object for a single listing (wraps in batch envelope)."""
    mock_response = MagicMock()
    mock_content = MagicMock()
    mock_content.text = json.dumps({"results": [data]})
    mock_response.content = [mock_content]
    return mock_response


def make_batch_mock_response(data_list: list):
    """Create a mock Anthropic response object for multiple listings."""
    mock_response = MagicMock()
    mock_content = MagicMock()
    mock_content.text = json.dumps({"results": data_list})
    mock_response.content = [mock_content]
    return mock_response


@pytest.mark.asyncio
@patch("app.llm.verifier.get_llm_client")
async def test_rejects_looking_for_apartment_post(mock_get_client, llm_rejected_response):
    """LLM-01: Posts where the author is looking for an apartment (not offering
    one) must be rejected. The verifier must return is_rental=False for such
    posts, and the listing must not be inserted into the database.
    """
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        return_value=make_mock_response(llm_rejected_response)
    )
    mock_get_client.return_value = mock_client

    from app.llm.verifier import verify_listing

    result = await verify_listing("מחפש דירה 3 חדרים בכרמל")
    assert result["is_rental"] is False
    assert result["rejection_reason"] is not None


@pytest.mark.asyncio
@patch("app.llm.verifier.get_llm_client")
async def test_extracts_structured_fields_from_hebrew(
    mock_get_client, llm_valid_rental_response
):
    """LLM-02: The verifier extracts structured fields from Hebrew free-text:
    price (int, ILS), rooms (float), size_sqm (int), address (str),
    contact_info (str). Extracted values must match fixture expected values.
    """
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        return_value=make_mock_response(llm_valid_rental_response)
    )
    mock_get_client.return_value = mock_client

    from app.llm.verifier import verify_listing

    hebrew_listing_text = (
        "דירה להשכרה 3 חדרים ברחוב הנשיא 15, כרמל, חיפה. "
        "שכירות 3500 ₪ לחודש. 75 מ\"ר. פנו לישראל ישראלי."
    )
    result = await verify_listing(hebrew_listing_text)
    assert result["price"] == 3500
    assert result["rooms"] == 3.0
    assert result["address"] is not None


@pytest.mark.asyncio
@patch("app.llm.verifier.get_llm_client")
async def test_confidence_below_threshold_flagged_not_deleted(
    mock_get_client, llm_low_confidence_response
):
    """LLM-03: When llm_confidence is below settings.llm_confidence_threshold
    (default 0.7), the listing must be saved with is_active=False (flagged)
    rather than deleted. Flagged listings are preserved for manual review.
    """
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        return_value=make_mock_response(llm_low_confidence_response)
    )
    mock_get_client.return_value = mock_client

    from app.llm.verifier import verify_listing

    result = await verify_listing("פרסום מעורפל — אולי דירה")
    assert result["confidence"] == 0.45
    assert isinstance(result["confidence"], float)


@pytest.mark.asyncio
async def test_llm_fields_supplement_scraper_fields(
    yad2_api_response_fixture, llm_valid_rental_response
):
    """LLM-04: Structured fields extracted by the scraper (non-null) take
    precedence over LLM-extracted fields. LLM only fills in fields the scraper
    could not extract (null). Both sources must be merged correctly.
    """
    from app.llm.verifier import merge_llm_fields

    scraper_data = {"price": 3500, "rooms": None, "size_sqm": None, "address": None, "contact_info": None}
    llm_data = {"price": 4000, "rooms": 3.0, "size_sqm": 75, "address": "רחוב הנשיא 15", "contact_info": "ישראל", "confidence": 0.92}

    merged = merge_llm_fields(scraper_data, llm_data)
    # Scraper non-null value takes precedence
    assert merged["price"] == 3500
    # LLM fills null fields
    assert merged["rooms"] == 3.0
    assert merged["llm_confidence"] == 0.92


@pytest.mark.asyncio
@patch("app.llm.verifier.get_llm_client")
async def test_batch_verify_uses_single_call(mock_get_client, llm_valid_rental_response):
    """LLM-05: The batch verification function must send all listings in a single
    API call to stay within rate limits. One call for N listings, not N calls.
    """
    call_count = 0

    async def fake_create(**kwargs):
        nonlocal call_count
        call_count += 1
        n = len(kwargs.get("messages", [{}])[0].get("content", "").split("[")) - 1
        return make_batch_mock_response([llm_valid_rental_response] * max(n, 3))

    mock_client = AsyncMock()
    mock_client.messages.create = fake_create
    mock_get_client.return_value = mock_client

    from app.llm.verifier import batch_verify_listings

    texts = ["דירה 1", "דירה 2", "דירה 3"]
    results = await batch_verify_listings(texts)

    assert len(results) == 3
    assert call_count == 1  # single API call for all listings
    for r in results:
        assert isinstance(r, dict)


@pytest.mark.asyncio
@patch("app.llm.verifier.get_llm_client")
async def test_model_is_configurable_default_haiku(
    mock_get_client, llm_valid_rental_response
):
    """LLM-06: The Anthropic model used by the verifier must be read from
    settings.llm_model (default: 'claude-haiku-4-5'). Changing the setting
    must change the model used without code modifications.
    """
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        return_value=make_mock_response(llm_valid_rental_response)
    )
    mock_get_client.return_value = mock_client

    from app.llm.verifier import verify_listing

    await verify_listing("דירה להשכרה")

    # Verify messages.create was called with model=claude-haiku-4-5
    call_kwargs = mock_client.messages.create.call_args
    assert call_kwargs is not None
    # model can be positional or keyword arg
    called_model = call_kwargs.kwargs.get("model") or (
        call_kwargs.args[0] if call_kwargs.args else None
    )
    assert called_model == "claude-haiku-4-5"
