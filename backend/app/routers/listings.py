from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.listing import Listing
from app.schemas.listing import ListingResponse

router = APIRouter(prefix="/api/listings", tags=["listings"])


@router.get("", response_model=List[ListingResponse])
@router.get("/", response_model=List[ListingResponse], include_in_schema=False)
async def get_listings(
    price_min: Optional[int] = Query(None, ge=0),
    price_max: Optional[int] = Query(None, ge=0),
    rooms_min: Optional[float] = Query(None, ge=0),
    rooms_max: Optional[float] = Query(None, ge=0),
    neighborhood: Optional[str] = Query(None),
    is_seen: Optional[bool] = Query(None),
    is_favorited: Optional[bool] = Query(None),
    since_hours: Optional[int] = Query(None, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """Return listings filtered by query params.

    Default behavior (no params): returns all active listings with
    llm_confidence >= threshold (D-03, D-04). is_seen listings are
    included — frontend handles seen visibility (D-03).
    """
    # Base filters — always applied (D-03: is_active=True, D-04: confidence >= threshold)
    filters = [
        Listing.is_active == True,  # noqa: E712
        Listing.llm_confidence >= settings.llm_confidence_threshold,
    ]

    if price_min is not None:
        filters.append(Listing.price >= price_min)
    if price_max is not None:
        filters.append(Listing.price <= price_max)
    if rooms_min is not None:
        filters.append(Listing.rooms >= rooms_min)
    if rooms_max is not None:
        filters.append(Listing.rooms <= rooms_max)
    if neighborhood is not None:
        # D-05: address text matching — provisional until Phase 5 coordinate-based matching
        filters.append(Listing.address.ilike(f"%{neighborhood}%"))
    if is_seen is not None:
        filters.append(Listing.is_seen == is_seen)
    if is_favorited is not None:
        filters.append(Listing.is_favorited == is_favorited)
    if since_hours is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        filters.append(Listing.created_at >= cutoff)

    stmt = select(Listing).where(and_(*filters)).order_by(Listing.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.put("/{listing_id}/seen", response_model=ListingResponse)
async def mark_seen(listing_id: int, db: AsyncSession = Depends(get_db)):
    """Mark listing as seen. Idempotent — calling twice has no extra effect."""
    listing = await db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="מודעה לא נמצאה")
    listing.is_seen = True
    await db.commit()
    await db.refresh(listing)
    return listing


@router.put("/{listing_id}/favorited", response_model=ListingResponse)
async def mark_favorited(listing_id: int, db: AsyncSession = Depends(get_db)):
    """Mark listing as favorited. Idempotent — calling twice has no extra effect."""
    listing = await db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="מודעה לא נמצאה")
    listing.is_favorited = True
    await db.commit()
    await db.refresh(listing)
    return listing
