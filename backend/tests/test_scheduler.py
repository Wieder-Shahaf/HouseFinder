"""Tests for APScheduler integration (SCHED-01, SCHED-02, SCHED-03)."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from app.scheduler import scheduler, get_health_state, run_yad2_scrape_job, _health
from app.scrapers.base import ScraperResult


def test_scheduler_instance_is_asyncio():
    """SCHED-03: Scheduler is AsyncIOScheduler (embedded, not BackgroundScheduler)."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    assert isinstance(scheduler, AsyncIOScheduler)


def test_health_state_initial():
    """D-02: Health dict starts with yad2=None (never run)."""
    state = get_health_state()
    assert "yad2" in state
    # Reset for test isolation
    _health["yad2"] = None


@pytest.mark.asyncio
async def test_scrape_job_updates_health_on_success():
    """Verify run_yad2_scrape_job updates _health dict after successful run."""
    mock_result = ScraperResult(
        source="yad2", listings_found=5, listings_inserted=3, success=True
    )
    _health["yad2"] = None

    with patch("app.database.async_session_factory") as mock_factory, \
         patch("app.scrapers.yad2.run_yad2_scraper", new_callable=AsyncMock, return_value=mock_result):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_ctx
        await run_yad2_scrape_job()

    assert _health["yad2"] is not None
    assert _health["yad2"]["success"] is True
    assert _health["yad2"]["listings_found"] == 5
    assert _health["yad2"]["listings_inserted"] == 3
    assert _health["yad2"]["last_run"] is not None
    # Reset
    _health["yad2"] = None


@pytest.mark.asyncio
async def test_scrape_job_updates_health_on_failure():
    """Verify run_yad2_scrape_job sets success=False on exception."""
    _health["yad2"] = None
    with patch("app.database.async_session_factory") as mock_factory:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("connection failed"))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_ctx
        await run_yad2_scrape_job()

    assert _health["yad2"] is not None
    assert _health["yad2"]["success"] is False
    assert "connection failed" in _health["yad2"]["errors"][0]
    # Reset
    _health["yad2"] = None


def test_job_config_in_lifespan():
    """SCHED-01 + SCHED-02: Verify lifespan registers job with correct config."""
    from app.config import settings
    # Locate main.py relative to this test file's package root
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main_py = os.path.join(backend_dir, "app", "main.py")
    with open(main_py) as f:
        source = f.read()

    assert "max_instances=1" in source, "SCHED-02: max_instances=1 must be set"
    assert "coalesce=True" in source, "Coalesce must be set"
    assert "next_run_time=" in source, "D-01: next_run_time must be set for immediate fire"
    assert "settings.scrape_interval_hours" in source, "SCHED-01: interval must use settings"
