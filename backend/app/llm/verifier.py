"""LLM verification pipeline for apartment rental listings.

Verifies listings are genuine rentals using Claude Haiku, extracts and
normalizes structured fields from Hebrew text, and assigns confidence scores.

All listings are sent in a single API call (batch prompt) to avoid rate limits.

Exports:
    verify_listing        — single listing verification (wraps batch)
    batch_verify_listings — single-call batch verification
    merge_llm_fields      — merge LLM-extracted fields with scraper fields
    LISTING_SCHEMA        — JSON Schema for a single listing result
    VERIFY_PROMPT         — Hebrew-aware prompt template
"""

import json
import logging
from typing import Any

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON Schema for structured output
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

_BATCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": LISTING_SCHEMA,
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

VERIFY_PROMPT = """You are analyzing Hebrew real estate listings. For each numbered listing below, determine if it is a genuine RENTAL listing and extract structured fields.

Reject a listing if it is:
- A "looking for apartment" post (מחפש/ה דירה)
- A sale listing (למכירה / מכירה)
- Spam, advertising, or unrelated content
- A roommate search (שותף/ה)

For each listing extract:
- price: Monthly rent in ILS (integer, no currency symbol)
- rooms: Number of rooms (float, e.g., 2.5, 3, 3.5)
- size_sqm: Apartment size in square meters (integer)
- address: Full address in Hebrew (street, neighborhood, city)
- contact_info: Contact name and/or phone number

Set confidence (0.0-1.0) per listing based on how clearly it identifies as a rental and how many fields you could extract.

Return a JSON object with a "results" array containing one object per listing in the same order.

Listings:
{listings}"""

# ---------------------------------------------------------------------------
# Client factory — extracted for easy mocking in tests
# ---------------------------------------------------------------------------


def get_llm_client() -> anthropic.AsyncAnthropic:
    """Return an async Anthropic client configured from settings."""
    return anthropic.AsyncAnthropic(api_key=settings.llm_api_key)


# ---------------------------------------------------------------------------
# Token budget constants — prevent exceeding model context window
# ---------------------------------------------------------------------------

_MODEL_CONTEXT_TOKENS = 200_000  # claude-haiku-4-5 context window
_INPUT_TOKEN_BUDGET = _MODEL_CONTEXT_TOKENS // 2  # use at most 50% for input
_MAX_OUTPUT_TOKENS = 8_192  # Haiku max output tokens
_PROMPT_OVERHEAD_TOKENS = 400  # prompt template + formatting overhead
_CHARS_PER_TOKEN = 4  # rough approximation (Hebrew text ~3-5 chars/token)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _chunk_listings(texts: list[str]) -> list[list[str]]:
    """Split listings into chunks that each fit within the input token budget.

    Listings are never split across chunks. Each chunk uses at most
    _INPUT_TOKEN_BUDGET - _PROMPT_OVERHEAD_TOKENS tokens.
    """
    available = _INPUT_TOKEN_BUDGET - _PROMPT_OVERHEAD_TOKENS
    chunks: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0

    for text in texts:
        tokens = _estimate_tokens(text)
        if current and current_tokens + tokens > available:
            chunks.append(current)
            current = []
            current_tokens = 0
        current.append(text)
        current_tokens += tokens

    if current:
        chunks.append(current)

    return chunks


# ---------------------------------------------------------------------------
# Rejection template
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


async def _call_llm_batch(client: anthropic.AsyncAnthropic, texts: list[str]) -> list[dict[str, Any]]:
    """Make a single LLM API call for a chunk of listings."""
    n = len(texts)
    numbered = "\n\n".join(f"[{i + 1}]\n{text}" for i, text in enumerate(texts))

    try:
        response = await client.messages.create(
            model=settings.llm_model,
            max_tokens=min(512 * n, _MAX_OUTPUT_TOKENS),
            messages=[{"role": "user", "content": VERIFY_PROMPT.format(listings=numbered)}],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": _BATCH_SCHEMA,
                }
            },
        )
        batch = json.loads(response.content[0].text)
        raw: list[Any] = batch.get("results", [])
        while len(raw) < n:
            raw.append({**_REJECTION_TEMPLATE, "rejection_reason": "missing from LLM batch response"})
        return raw[:n]
    except Exception as e:
        logger.error("[llm] _call_llm_batch error: %s", e)
        return [{**_REJECTION_TEMPLATE, "rejection_reason": f"LLM error: {e}"} for _ in texts]


# ---------------------------------------------------------------------------
# Batch verification — chunked API calls, listings never split
# ---------------------------------------------------------------------------


async def batch_verify_listings(raw_texts: list[str]) -> list[dict[str, Any]]:
    """Verify all listings, chunked to stay within 50% of the model context window.

    Each chunk is a single API call. Listings are never split across chunks.
    Falls back to rejecting the chunk on error without affecting other chunks.

    Args:
        raw_texts: List of Hebrew listing texts to verify.

    Returns:
        List of result dicts (same length as input).
    """
    n = len(raw_texts)
    if n == 0:
        return []

    chunks = _chunk_listings(raw_texts)
    logger.info(
        "[llm] Verifying %d listings in %d chunk(s) (%s)",
        n, len(chunks), settings.llm_model,
    )

    client = get_llm_client()
    all_results: list[dict[str, Any]] = []
    for chunk in chunks:
        all_results.extend(await _call_llm_batch(client, chunk))

    accepted = rejected = flagged = 0
    for item in all_results:
        if not item.get("is_rental", False):
            rejected += 1
        elif item.get("confidence", 0.0) < settings.llm_confidence_threshold:
            flagged += 1
        else:
            accepted += 1

    logger.info("[llm] %d accepted, %d rejected, %d flagged", accepted, rejected, flagged)
    return all_results


async def verify_listing(raw_text: str) -> dict[str, Any]:
    """Verify a single listing. Wraps batch_verify_listings for convenience."""
    results = await batch_verify_listings([raw_text])
    return results[0]


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
