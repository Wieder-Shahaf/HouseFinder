from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ListingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    source_id: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    is_seen: bool
    is_favorited: bool
    raw_data: Optional[str] = None
    llm_confidence: Optional[float] = None
    dedup_fingerprint: Optional[str] = None
    title: Optional[str] = None
    price: Optional[int] = None
    rooms: Optional[float] = None
    size_sqm: Optional[int] = None
    address: Optional[str] = None
    neighborhood: Optional[str] = None  # D-03: added in Phase 5
    contact_info: Optional[str] = None
    post_date: Optional[datetime] = None
    url: Optional[str] = None
    source_badge: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool
