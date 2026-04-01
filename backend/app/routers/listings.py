from typing import List

from fastapi import APIRouter

from app.schemas.listing import ListingResponse

router = APIRouter(prefix="/api/listings", tags=["listings"])


@router.get("/", response_model=List[ListingResponse])
async def get_listings():
    """Return all listings. Stub — full implementation in Phase 3."""
    return []
