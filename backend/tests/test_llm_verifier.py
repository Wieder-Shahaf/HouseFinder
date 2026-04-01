"""Test stubs for LLM verifier requirements LLM-01 through LLM-06.

All tests skip cleanly until Plan 02/03 creates app.llm.verifier.
Each test documents the acceptance criteria for the verifier implementation.
"""

import pytest

# Skip entire module if the verifier module does not yet exist
pytest.importorskip("app.llm.verifier")


def test_rejects_looking_for_apartment_post(llm_rejected_response):
    """LLM-01: Posts where the author is looking for an apartment (not offering
    one) must be rejected. The verifier must return is_rental=False for such
    posts, and the listing must not be inserted into the database.
    """
    pytest.skip("Implementation in Plan 02")


def test_extracts_structured_fields_from_hebrew(llm_valid_rental_response):
    """LLM-02: The verifier extracts structured fields from Hebrew free-text:
    price (int, ILS), rooms (float), size_sqm (int), address (str),
    contact_info (str). Extracted values must match fixture expected values.
    """
    pytest.skip("Implementation in Plan 02")


def test_confidence_below_threshold_flagged_not_deleted(
    llm_low_confidence_response,
):
    """LLM-03: When llm_confidence is below settings.llm_confidence_threshold
    (default 0.7), the listing must be saved with is_active=False (flagged)
    rather than deleted. Flagged listings are preserved for manual review.
    """
    pytest.skip("Implementation in Plan 02")


def test_llm_fields_supplement_scraper_fields(
    yad2_api_response_fixture, llm_valid_rental_response
):
    """LLM-04: Structured fields extracted by the scraper (non-null) take
    precedence over LLM-extracted fields. LLM only fills in fields the scraper
    could not extract (null). Both sources must be merged correctly.
    """
    pytest.skip("Implementation in Plan 02")


def test_batch_verify_uses_gather():
    """LLM-05: The batch verification function must issue concurrent Anthropic
    API calls using asyncio.gather (or equivalent), not sequential awaits.
    Concurrent execution is required for acceptable throughput when verifying
    multiple listings per scrape run.
    """
    pytest.skip("Implementation in Plan 02")


def test_model_is_configurable_default_haiku():
    """LLM-06: The Anthropic model used by the verifier must be read from
    settings.llm_model (default: 'claude-haiku-4-5'). Changing the setting
    must change the model used without code modifications.
    """
    pytest.skip("Implementation in Plan 02")
