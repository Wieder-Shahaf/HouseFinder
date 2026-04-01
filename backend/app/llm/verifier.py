"""LLM verification pipeline for apartment rental listings.

Verifies each listing is a genuine rental using Claude Haiku, extracts and
normalizes structured fields from Hebrew text, and assigns confidence scores.

Exports:
    verify_listing        — single listing verification
    batch_verify_listings — concurrent batch verification via asyncio.gather
    merge_llm_fields      — merge LLM-extracted fields with scraper fields
    LISTING_SCHEMA        — JSON Schema for structured output
    VERIFY_PROMPT         — Hebrew-aware prompt template
"""

import asyncio
import json
import logging
from typing import Any

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON Schema for structured output — Anthropic output_config.format
# ---------------------------------------------------------------------------

LISTING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "is_rental": {"type": "boolean"},
        "rejection_reason": {"type": ["string", "null"]},
        "confidence": {"type": "number"},
        "price": {"type": ["integer", "null"]},
        "rooms": {"type": ["number", "null"]},
        "size_sqm": {"type": ["integer", "null"]},
        "address": {"type": ["string", "null"]},
        "contact_info": {"type": ["string", "null"]},
    },
    "required": [
        "is_rental",
        "rejection_reason",
        "confidence",
        "price",
        "rooms",
        "size_sqm",
        "address",
        "contact_info",
    ],
    "additionalProperties": False,
}

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

VERIFY_PROMPT = """You are analyzing a Hebrew real estate listing from Yad2 (יד2).

Determine if this is a genuine RENTAL listing. Reject if it is:
- A "looking for apartment" post (מחפש/ה דירה)
- A sale listing (למכירה / מכירה)
- Spam, advertising, or unrelated content
- A roommate search (שותף/ה)

If it IS a rental listing, extract these fields:
- price: Monthly rent in ILS (integer, no currency symbol)
- rooms: Number of rooms (float, e.g., 2.5, 3, 3.5)
- size_sqm: Apartment size in square meters (integer)
- address: Full address in Hebrew (street, neighborhood, city)
- contact_info: Contact name and/or phone number

Set confidence (0.0-1.0) based on how clearly the text identifies as a rental \
and how many fields you could extract. High confidence (>0.8) means clear rental \
with most fields extractable. Low confidence (<0.5) means ambiguous text or very \
few fields found.

Listing text:
{text}"""

# ---------------------------------------------------------------------------
# Client factory — extracted for easy mocking in tests
# ---------------------------------------------------------------------------


def get_llm_client() -> anthropic.AsyncAnthropic:
    """Return an async Anthropic client configured from settings."""
    return anthropic.AsyncAnthropic(api_key=settings.llm_api_key)


# ---------------------------------------------------------------------------
# Core verification function
# ---------------------------------------------------------------------------

_REJECTION_TEMPLATE: dict[str, Any] = {
    "is_rental": False,
    "rejection_reason": None,
    "confidence": 0.0,
    "price": None,
    "rooms": None,
    "size_sqm": None,
    "address": None,
    "contact_info": None,
}


async def verify_listing(raw_text: str) -> dict[str, Any]:
    """Verify a single listing via Claude and extract structured fields.

    Args:
        raw_text: Hebrew-language listing text to verify and extract from.

    Returns:
        Dict with keys: is_rental, rejection_reason, confidence, price,
        rooms, size_sqm, address, contact_info.
        On LLM error, returns a rejection dict with is_rental=False and an
        error message in rejection_reason.
    """
    try:
        client = get_llm_client()
        response = await client.messages.create(
            model=settings.llm_model,
            max_tokens=512,
            messages=[
                {"role": "user", "content": VERIFY_PROMPT.format(text=raw_text)}
            ],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": LISTING_SCHEMA,
                }
            },
        )
        return json.loads(response.content[0].text)
    except Exception as e:
        logger.error("[llm] verify_listing error: %s", e)
        return {
            **_REJECTION_TEMPLATE,
            "rejection_reason": f"LLM error: {e}",
        }


# ---------------------------------------------------------------------------
# Batch verification
# ---------------------------------------------------------------------------


async def batch_verify_listings(raw_texts: list[str]) -> list[dict[str, Any]]:
    """Verify a batch of listings concurrently using asyncio.gather.

    Per D-03: runs after the full scrape batch, not per-listing during scrape.
    Uses return_exceptions=True so a single failure does not abort the batch.

    Args:
        raw_texts: List of Hebrew listing texts to verify.

    Returns:
        List of result dicts (same length as input). Exceptions are converted
        to rejection dicts with the error message in rejection_reason.
    """
    n = len(raw_texts)
    logger.info("[llm] Verifying %d listings with %s", n, settings.llm_model)

    raw_results = await asyncio.gather(
        *[verify_listing(t) for t in raw_texts],
        return_exceptions=True,
    )

    results: list[dict[str, Any]] = []
    accepted = rejected = flagged = 0

    for item in raw_results:
        if isinstance(item, Exception):
            results.append(
                {
                    **_REJECTION_TEMPLATE,
                    "rejection_reason": f"LLM error: {item}",
                }
            )
            rejected += 1
        else:
            results.append(item)
            if not item.get("is_rental", False):
                rejected += 1
            elif item.get("confidence", 0.0) < settings.llm_confidence_threshold:
                flagged += 1
            else:
                accepted += 1

    logger.info(
        "[llm] %d accepted, %d rejected, %d flagged", accepted, rejected, flagged
    )
    return results


# ---------------------------------------------------------------------------
# Field merge
# ---------------------------------------------------------------------------


def merge_llm_fields(
    scraper_data: dict[str, Any], llm_data: dict[str, Any]
) -> dict[str, Any]:
    """Merge LLM-extracted fields into scraper data.

    Per LLM-04: scraper non-null fields take precedence; LLM fills nulls.

    Args:
        scraper_data: Fields extracted by the scraper (may have nulls).
        llm_data:     Fields extracted by the LLM verifier.

    Returns:
        Merged dict with llm_confidence added.
    """
    merged: dict[str, Any] = dict(scraper_data)

    for field in ("price", "rooms", "size_sqm", "address", "contact_info"):
        if scraper_data.get(field) is None:
            merged[field] = llm_data.get(field)

    merged["llm_confidence"] = llm_data.get("confidence", 0.0)
    return merged
