"""Geocoding, neighborhood assignment, and dedup fingerprint utilities.

Public API:
  run_geocoding_pass(session)  — geocode NULL-lat listings, assign neighborhoods,
                                  write fingerprints. Called from APScheduler job.
  run_dedup_pass(session)      — fingerprint-based dedup (implemented in Plan 05-02).
  assign_neighborhood(lat, lng) — return Hebrew neighborhood name or None.
  make_dedup_fingerprint(...)  — return SHA-256 hex digest string.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from math import atan2, cos, radians, sin, sqrt
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Neighborhood bounding boxes (D-01, locked)
# ---------------------------------------------------------------------------
NEIGHBORHOODS: dict[str, dict] = {
    "כרמל":       {"lat": (32.78, 32.83), "lng": (34.97, 35.02)},
    "מרכז העיר": {"lat": (32.81, 32.84), "lng": (35.00, 35.03)},
    "נווה שאנן":  {"lat": (32.80, 32.83), "lng": (35.02, 35.05)},
}

# Nominatim ToS: must include app name + contact
NOMINATIM_USER_AGENT = "ApartmentFinder/1.0 (haifa-apartments-bot@example.com)"
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"


# ---------------------------------------------------------------------------
# Pure helpers (no I/O)
# ---------------------------------------------------------------------------

def assign_neighborhood(lat: float, lng: float) -> Optional[str]:
    """Return Hebrew neighborhood name if (lat, lng) falls in a bounding box.

    Returns None if outside all three boxes (D-02).
    """
    for name, bounds in NEIGHBORHOODS.items():
        if (
            bounds["lat"][0] <= lat <= bounds["lat"][1]
            and bounds["lng"][0] <= lng <= bounds["lng"][1]
        ):
            return name
    return None


def make_dedup_fingerprint(price: int, rooms: float, lat: float, lng: float) -> str:
    """Return 64-character SHA-256 hex digest (D-11).

    Format: sha256("{price}:{rooms}:{round(lat,4)}:{round(lng,4)}")
    Fits VARCHAR(64) exactly.
    """
    key = f"{price}:{rooms}:{round(lat, 4)}:{round(lng, 4)}"
    return hashlib.sha256(key.encode()).hexdigest()


def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in meters between two points (stdlib math only)."""
    R = 6_371_000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lng2 - lng1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


# ---------------------------------------------------------------------------
# Geocoding providers
# ---------------------------------------------------------------------------

async def _geocode_nominatim(address: str) -> Optional[tuple[float, float]]:
    """Return (lat, lng) from Nominatim or None on failure.

    IMPORTANT: Nominatim returns "lon" (not "lng") as JSON strings — cast to float.
    Rate-limited to 1 req/sec via asyncio.sleep(1) after each request (ToS).
    """
    params = {
        "q": address,
        "format": "json",
        "countrycodes": "il",
        "limit": 1,
    }
    headers = {"User-Agent": NOMINATIM_USER_AGENT}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=10) as client:
            resp = await client.get(NOMINATIM_SEARCH_URL, params=params)
            resp.raise_for_status()
            results = resp.json()
        await asyncio.sleep(1)  # ToS: 1 req/sec
        if not results:
            return None
        # Nominatim "lat" and "lon" are strings, not numbers — cast explicitly
        return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as exc:
        logger.warning("Nominatim geocoding failed for %r: %s", address, exc)
        await asyncio.sleep(1)  # still rate-limit on failure
        return None


async def _geocode_google_maps_fallback(address: str) -> Optional[tuple[float, float]]:
    """Playwright + Bright Data Web Unlocker fallback geocoder.

    Navigates to Google Maps search for the address, waits for the URL to
    contain the @lat,lng pattern, then extracts coordinates via regex.

    When Bright Data proxy is active, uses http:// target (proxy handles SSL).
    Returns None on any failure — listing will be retried next geocoding pass.
    """
    from app.scrapers.proxy import get_proxy_launch_args, is_proxy_enabled
    from playwright.async_api import async_playwright

    query = f"{address} חיפה"
    # When proxy is active, use http:// — Bright Data Web Unlocker handles SSL (per proxy.py)
    protocol = "http" if is_proxy_enabled() else "https"
    search_url = f"{protocol}://www.google.com/maps/search/?api=1&query={query}"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, **get_proxy_launch_args())
            try:
                page = await browser.new_page()
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                # Google Maps rewrites URL to include @lat,lng after navigation
                await page.wait_for_url(
                    re.compile(r"@-?\d+\.\d+,-?\d+\.\d+"), timeout=15000
                )
                current_url = page.url
                match = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", current_url)
                if match:
                    lat = float(match.group(1))
                    lng = float(match.group(2))
                    logger.info(
                        "Google Maps fallback geocoded %r → (%f, %f)", address, lat, lng
                    )
                    return lat, lng
                return None
            except Exception as exc:
                logger.warning(
                    "Google Maps fallback failed for %r: %s", address, exc
                )
                return None
            finally:
                await browser.close()
    except Exception as exc:
        logger.warning("Playwright launch failed in geocoding fallback: %s", exc)
        return None


async def _geocode_address(address: str) -> Optional[tuple[float, float]]:
    """Geocode cascade: Nominatim (primary) → Google Maps Playwright (fallback).

    Returns (lat, lng) or None. None means both providers failed; leave lat=NULL
    and the listing will be retried on the next pass (D-06).
    """
    result = await _geocode_nominatim(address)
    if result is not None:
        return result

    logger.info(
        "Nominatim returned no result for %r — trying Google Maps fallback", address
    )
    result = await _geocode_google_maps_fallback(address)
    if result is not None:
        return result

    logger.info("All geocoding providers failed for %r — will retry next pass", address)
    return None


# ---------------------------------------------------------------------------
# Scheduler pass functions
# ---------------------------------------------------------------------------

async def run_geocoding_pass(session: AsyncSession) -> None:
    """Geocode all listings where lat IS NULL AND address IS NOT NULL (D-04).

    For each listing:
      1. Call _geocode_address() → (lat, lng) or None
      2. If result: assign neighborhood (D-07), compute dedup fingerprint (D-11)
      3. Write lat, lng, neighborhood, dedup_fingerprint to DB
      4. Commit once at end of pass

    Listings that return None are left with lat=NULL and retried next pass (D-06).
    """
    stmt = select(Listing).where(
        Listing.lat.is_(None),
        Listing.address.isnot(None),
    )
    result = await session.execute(stmt)
    listings = result.scalars().all()

    if not listings:
        logger.info("Geocoding pass: no listings to geocode")
        return

    logger.info("Geocoding pass: %d listings to geocode", len(listings))
    geocoded = 0

    for listing in listings:
        coords = await _geocode_address(listing.address)
        if coords is None:
            continue

        lat, lng = coords
        listing.lat = lat
        listing.lng = lng
        listing.neighborhood = assign_neighborhood(lat, lng)

        # Only compute fingerprint if price and rooms are populated
        if listing.price is not None and listing.rooms is not None:
            listing.dedup_fingerprint = make_dedup_fingerprint(
                listing.price, listing.rooms, lat, lng
            )

        geocoded += 1

    await session.commit()
    logger.info("Geocoding pass complete: %d/%d geocoded", geocoded, len(listings))


async def run_dedup_pass(session: AsyncSession) -> None:
    """Deactivate cross-source duplicate listings by fingerprint (D-08, D-09, D-11).

    Implemented in Plan 05-02.
    """
    pass  # placeholder — full implementation in Plan 05-02
