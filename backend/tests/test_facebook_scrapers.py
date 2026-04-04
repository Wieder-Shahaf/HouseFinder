"""Tests for Facebook Groups scraper requirements FBGR-01 through FBGR-05
and Facebook Marketplace scraper requirements FBMP-01 through FBMP-04.

Tests use real async DB sessions (in-memory SQLite) and mock Playwright
to verify scraper behavior without hitting live Facebook endpoints.
Mirrors test_madlan_scraper.py structure.
"""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Skip entire module if the scraper module does not yet exist
pytest.importorskip("app.scrapers.facebook_groups")

from app.scrapers.facebook_groups import (
    GROUPS_FILE,
    SOURCE,
    _load_groups,
    check_session_health,
    extract_post_source_id,
    run_facebook_groups_scraper,
)
from app.models.listing import Listing


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_GROUPS = [
    {"url": "https://www.facebook.com/groups/12345", "name": "שכירות חיפה"},
    {"url": "https://www.facebook.com/groups/67890", "name": "דירות כרמל"},
]


# ---------------------------------------------------------------------------
# Task 2 tests — FBGR-01: Group config loading
# ---------------------------------------------------------------------------


def test_groups_config_loaded(tmp_path):
    """FBGR-01: _load_groups() reads a valid JSON file and returns list of dicts."""
    groups_json = tmp_path / "facebook_groups.json"
    groups_json.write_text(
        json.dumps([{"url": "https://www.facebook.com/groups/test", "name": "Test Group"}]),
        encoding="utf-8",
    )
    with patch("app.scrapers.facebook_groups.GROUPS_FILE", groups_json):
        result = _load_groups()
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["url"] == "https://www.facebook.com/groups/test"
    assert result[0]["name"] == "Test Group"


def test_groups_missing_file():
    """FBGR-01: _load_groups() returns empty list when GROUPS_FILE does not exist."""
    with patch("app.scrapers.facebook_groups.GROUPS_FILE", Path("/tmp/nonexistent_groups_abc.json")):
        result = _load_groups()
    assert result == []


def test_groups_empty_file(tmp_path):
    """FBGR-01: _load_groups() returns empty list when file contains []."""
    groups_json = tmp_path / "facebook_groups_empty.json"
    groups_json.write_text("[]", encoding="utf-8")
    with patch("app.scrapers.facebook_groups.GROUPS_FILE", groups_json):
        result = _load_groups()
    assert result == []


# ---------------------------------------------------------------------------
# Tests — FBGR-02: Session loading
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_loaded():
    """FBGR-02: _load_fb_context creates browser and context with storage_state."""
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    mock_stealth = MagicMock()
    mock_stealth.apply_stealth_async = AsyncMock()

    mock_p = MagicMock()
    mock_p.chromium.launch = AsyncMock(return_value=mock_browser)

    with patch("app.scrapers.facebook_groups.Stealth", return_value=mock_stealth):
        from app.scrapers.facebook_groups import _load_fb_context
        browser, context = await _load_fb_context(mock_p, "/data/test_session.json")

    # Verify browser was launched
    mock_p.chromium.launch.assert_awaited_once()

    # Verify context was created with storage_state
    call_kwargs = mock_browser.new_context.call_args.kwargs
    assert call_kwargs["storage_state"] == "/data/test_session.json"
    assert call_kwargs["locale"] == "he-IL"

    # Verify stealth was applied
    mock_stealth.apply_stealth_async.assert_awaited_once_with(mock_context)

    assert browser is mock_browser
    assert context is mock_context


# ---------------------------------------------------------------------------
# Tests — FBGR-03: Session health check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_health_expired():
    """FBGR-03: check_session_health returns False when page.url contains 'login'."""
    mock_page = AsyncMock()
    mock_page.url = "https://www.facebook.com/login/?next=..."
    mock_page.goto = AsyncMock()
    mock_page.close = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await check_session_health(mock_context)

    assert result is False


@pytest.mark.asyncio
async def test_session_health_checkpoint():
    """FBGR-03: check_session_health returns False when page.url contains 'checkpoint'."""
    mock_page = AsyncMock()
    mock_page.url = "https://www.facebook.com/checkpoint/?next=..."
    mock_page.goto = AsyncMock()
    mock_page.close = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await check_session_health(mock_context)

    assert result is False


@pytest.mark.asyncio
async def test_session_health_valid():
    """FBGR-03: check_session_health returns True when URL is clean and LeftRail present."""
    mock_locator = AsyncMock()
    mock_locator.count = AsyncMock(return_value=1)

    mock_page = AsyncMock()
    mock_page.url = "https://www.facebook.com/"
    mock_page.goto = AsyncMock()
    mock_page.close = AsyncMock()
    mock_page.locator = MagicMock(return_value=mock_locator)

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await check_session_health(mock_context)

    assert result is True


# ---------------------------------------------------------------------------
# Tests — FBGR-04 + FBGR-05: Post URL parsing
# ---------------------------------------------------------------------------


def test_parse_fb_post():
    """FBGR-04: extract_post_source_id extracts numeric ID from permalink URL."""
    result = extract_post_source_id("https://www.facebook.com/groups/123/permalink/456789/")
    assert result == "456789"


def test_parse_fb_post_posts_pattern():
    """FBGR-04: extract_post_source_id extracts numeric ID from /posts/ URL."""
    result = extract_post_source_id("https://www.facebook.com/groups/12345/posts/987654321/")
    assert result == "987654321"


def test_parse_fb_post_fallback():
    """FBGR-04: extract_post_source_id returns 32-char hex string when URL has no ID."""
    result = extract_post_source_id("https://www.facebook.com/groups/123/")
    assert isinstance(result, str)
    assert len(result) == 32
    # Must be hex only
    int(result, 16)


def test_parse_fb_post_fallback_uses_text():
    """FBGR-04: extract_post_source_id hash is deterministic for the same fallback text."""
    text = "דירה 3 חדרים בכרמל חיפה"
    r1 = extract_post_source_id("", text)
    r2 = extract_post_source_id("", text)
    assert r1 == r2
    assert len(r1) == 32


# ---------------------------------------------------------------------------
# Tests — FBGR-03: Session expiry clean return path (D-09)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_expiry_returns_clean(db_session, tmp_path):
    """FBGR-03 / D-09: run_facebook_groups_scraper returns success=True with session_expired
    error when session health check fails. send_session_expiry_alert must be called."""
    # Write valid groups file
    groups_json = tmp_path / "facebook_groups.json"
    groups_json.write_text(json.dumps(SAMPLE_GROUPS), encoding="utf-8")

    # Write a dummy session file so the existence check passes
    session_file = tmp_path / "facebook_session.json"
    session_file.write_text("{}", encoding="utf-8")

    mock_browser = AsyncMock()
    mock_browser.close = AsyncMock()
    mock_context = AsyncMock()
    mock_context.close = AsyncMock()
    mock_playwright = AsyncMock()
    mock_playwright.__aenter__ = AsyncMock(return_value=mock_playwright)
    mock_playwright.__aexit__ = AsyncMock(return_value=False)

    mock_send_alert = AsyncMock()

    with (
        patch("app.scrapers.facebook_groups.GROUPS_FILE", groups_json),
        patch("app.scrapers.facebook_groups.settings") as mock_settings,
        patch("app.scrapers.facebook_groups._load_fb_context", new_callable=AsyncMock, return_value=(mock_browser, mock_context)),
        patch("app.scrapers.facebook_groups.check_session_health", new_callable=AsyncMock, return_value=False),
        patch("app.scrapers.facebook_groups.send_session_expiry_alert", mock_send_alert),
        patch("app.scrapers.facebook_groups.async_playwright", return_value=mock_playwright),
    ):
        mock_settings.facebook_session_path = str(session_file)
        mock_settings.llm_confidence_threshold = 0.7
        result = await run_facebook_groups_scraper(db_session)

    assert result.success is True, f"Expected success=True, got success={result.success}"
    assert any("session_expired" in e for e in result.errors), (
        f"Expected 'session_expired' in errors, got: {result.errors}"
    )
    mock_send_alert.assert_awaited_once()


# ---------------------------------------------------------------------------
# Tests — session file missing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_file_missing(db_session, tmp_path):
    """run_facebook_groups_scraper returns ScraperResult(success=True) with error
    when session file doesn't exist (never raises, never alerts)."""
    groups_json = tmp_path / "facebook_groups.json"
    groups_json.write_text(json.dumps(SAMPLE_GROUPS), encoding="utf-8")

    with (
        patch("app.scrapers.facebook_groups.GROUPS_FILE", groups_json),
        patch("app.scrapers.facebook_groups.settings") as mock_settings,
    ):
        mock_settings.facebook_session_path = str(tmp_path / "nonexistent_session.json")
        result = await run_facebook_groups_scraper(db_session)

    assert result.success is True
    assert len(result.errors) > 0
    assert "session file not found" in result.errors[0]


# ---------------------------------------------------------------------------
# Tests — FBGR-05: Failure isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_groups_failure_isolation(db_session, tmp_path):
    """FBGR-05: run_facebook_groups_scraper catches exceptions and returns ScraperResult
    without raising. success=False on unhandled error, errors list non-empty."""
    groups_json = tmp_path / "facebook_groups.json"
    groups_json.write_text(json.dumps(SAMPLE_GROUPS), encoding="utf-8")

    session_file = tmp_path / "session.json"
    session_file.write_text("{}", encoding="utf-8")

    mock_playwright = AsyncMock()
    mock_playwright.__aenter__ = AsyncMock(return_value=mock_playwright)
    mock_playwright.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.scrapers.facebook_groups.GROUPS_FILE", groups_json),
        patch("app.scrapers.facebook_groups.settings") as mock_settings,
        patch("app.scrapers.facebook_groups._load_fb_context", new_callable=AsyncMock, side_effect=RuntimeError("Playwright launch failed")),
        patch("app.scrapers.facebook_groups.async_playwright", return_value=mock_playwright),
    ):
        mock_settings.facebook_session_path = str(session_file)
        mock_settings.llm_confidence_threshold = 0.7
        result = await run_facebook_groups_scraper(db_session)

    assert result.success is False, f"Expected success=False, got {result.success}"
    assert len(result.errors) > 0, "Expected errors list to be non-empty"
    assert result.source == SOURCE


# ---------------------------------------------------------------------------
# Tests — D-03: Empty groups graceful handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_groups_scraper_empty_groups(db_session, tmp_path):
    """D-03: run_facebook_groups_scraper returns success=True with 0 counts
    when groups list is empty (no session check, no Playwright launch)."""
    empty_groups_json = tmp_path / "facebook_groups_empty.json"
    empty_groups_json.write_text("[]", encoding="utf-8")

    with patch("app.scrapers.facebook_groups.GROUPS_FILE", empty_groups_json):
        result = await run_facebook_groups_scraper(db_session)

    assert result.success is True
    assert result.listings_found == 0
    assert result.listings_inserted == 0
    assert result.source == SOURCE


# ---------------------------------------------------------------------------
# Tests — source and source_badge
# ---------------------------------------------------------------------------


def test_source_constant():
    """SOURCE constant is 'facebook_groups'."""
    assert SOURCE == "facebook_groups"


# ===========================================================================
# Facebook Marketplace scraper tests — FBMP-01 through FBMP-04
# ===========================================================================

pytest.importorskip("app.scrapers.facebook_marketplace")

from app.scrapers.facebook_marketplace import (  # noqa: E402
    MARKETPLACE_URL,
    SOURCE as MARKETPLACE_SOURCE,
    run_facebook_marketplace_scraper,
)


# ---------------------------------------------------------------------------
# FBMP-01: Constants
# ---------------------------------------------------------------------------


def test_marketplace_url():
    """FBMP-01: MARKETPLACE_URL constant is the Haifa rental Marketplace page."""
    assert MARKETPLACE_URL == "https://www.facebook.com/marketplace/haifa/propertyrentals/"


def test_marketplace_source():
    """FBMP-01: SOURCE constant equals 'facebook_marketplace'."""
    assert MARKETPLACE_SOURCE == "facebook_marketplace"


# ---------------------------------------------------------------------------
# FBMP-02: Session reuse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_marketplace_session_reuse(db_session, tmp_path):
    """FBMP-02: run_facebook_marketplace_scraper calls _load_fb_context with
    settings.facebook_session_path as the second argument."""
    session_file = tmp_path / "facebook_session.json"
    session_file.write_text("{}", encoding="utf-8")

    mock_browser = AsyncMock()
    mock_browser.close = AsyncMock()
    mock_context = AsyncMock()
    mock_context.close = AsyncMock()

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.evaluate = AsyncMock()
    mock_page.locator = MagicMock(return_value=AsyncMock(all=AsyncMock(return_value=[])))
    mock_page.inner_text = AsyncMock(return_value="")
    mock_page.close = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_load_fb_context = AsyncMock(return_value=(mock_browser, mock_context))
    mock_playwright = AsyncMock()
    mock_playwright.__aenter__ = AsyncMock(return_value=mock_playwright)
    mock_playwright.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.scrapers.facebook_marketplace.settings") as mock_settings,
        patch("app.scrapers.facebook_marketplace._load_fb_context", mock_load_fb_context),
        patch("app.scrapers.facebook_marketplace.check_session_health", new_callable=AsyncMock, return_value=True),
        patch("app.scrapers.facebook_marketplace.async_playwright", return_value=mock_playwright),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_settings.facebook_session_path = str(session_file)
        mock_settings.llm_confidence_threshold = 0.7
        await run_facebook_marketplace_scraper(db_session)

    # Verify _load_fb_context was called with the session path as second arg
    mock_load_fb_context.assert_awaited_once()
    call_args = mock_load_fb_context.call_args
    assert str(session_file) in (call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("session_path", ""))


# ---------------------------------------------------------------------------
# FBMP-03: Session expiry handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_marketplace_session_expired(db_session, tmp_path):
    """FBMP-03: run_facebook_marketplace_scraper returns success=True with
    session_expired error and calls send_session_expiry_alert when session is expired."""
    session_file = tmp_path / "facebook_session.json"
    session_file.write_text("{}", encoding="utf-8")

    mock_browser = AsyncMock()
    mock_browser.close = AsyncMock()
    mock_context = AsyncMock()
    mock_context.close = AsyncMock()
    mock_send_alert = AsyncMock()

    mock_playwright = AsyncMock()
    mock_playwright.__aenter__ = AsyncMock(return_value=mock_playwright)
    mock_playwright.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.scrapers.facebook_marketplace.settings") as mock_settings,
        patch("app.scrapers.facebook_marketplace._load_fb_context", new_callable=AsyncMock, return_value=(mock_browser, mock_context)),
        patch("app.scrapers.facebook_marketplace.check_session_health", new_callable=AsyncMock, return_value=False),
        patch("app.scrapers.facebook_marketplace.send_session_expiry_alert", mock_send_alert),
        patch("app.scrapers.facebook_marketplace.async_playwright", return_value=mock_playwright),
    ):
        mock_settings.facebook_session_path = str(session_file)
        mock_settings.llm_confidence_threshold = 0.7
        result = await run_facebook_marketplace_scraper(db_session)

    assert result.success is True, f"Expected success=True, got {result.success}"
    assert any("session_expired" in e for e in result.errors), (
        f"Expected 'session_expired' in errors, got: {result.errors}"
    )
    mock_send_alert.assert_awaited_once()


# ---------------------------------------------------------------------------
# Session file missing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_marketplace_session_file_missing(db_session, tmp_path):
    """run_facebook_marketplace_scraper returns success=True with error when
    session file does not exist (never raises, Playwright never launched)."""
    with (
        patch("app.scrapers.facebook_marketplace.settings") as mock_settings,
    ):
        mock_settings.facebook_session_path = str(tmp_path / "nonexistent_session.json")
        result = await run_facebook_marketplace_scraper(db_session)

    assert result.success is True
    assert len(result.errors) > 0
    assert "session file not found" in result.errors[0]


# ---------------------------------------------------------------------------
# Item URL parsing
# ---------------------------------------------------------------------------


def test_parse_marketplace_item_url():
    """Regex r'/item/(\\d+)' extracts numeric ID from a Marketplace item URL."""
    url_path = "/marketplace/item/123456789/"
    match = re.search(r"/item/(\d+)", url_path)
    assert match is not None
    assert match.group(1) == "123456789"


# ---------------------------------------------------------------------------
# FBMP-04: Failure isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_marketplace_failure_isolation(db_session, tmp_path):
    """FBMP-04: run_facebook_marketplace_scraper catches exceptions and returns
    ScraperResult without raising. success=False when unhandled error occurs."""
    session_file = tmp_path / "session.json"
    session_file.write_text("{}", encoding="utf-8")

    mock_playwright = AsyncMock()
    mock_playwright.__aenter__ = AsyncMock(return_value=mock_playwright)
    mock_playwright.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.scrapers.facebook_marketplace.settings") as mock_settings,
        patch("app.scrapers.facebook_marketplace._load_fb_context", new_callable=AsyncMock, side_effect=RuntimeError("browser crash")),
        patch("app.scrapers.facebook_marketplace.async_playwright", return_value=mock_playwright),
    ):
        mock_settings.facebook_session_path = str(session_file)
        mock_settings.llm_confidence_threshold = 0.7
        result = await run_facebook_marketplace_scraper(db_session)

    assert result.success is False, f"Expected success=False, got {result.success}"
    assert len(result.errors) > 0, "Expected errors list to be non-empty"
    assert result.source == MARKETPLACE_SOURCE
