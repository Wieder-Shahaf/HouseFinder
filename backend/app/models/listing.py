from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Listing(Base):
    __tablename__ = "listings"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Infrastructure columns (D-02)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_seen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_favorited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dedup_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Listing data columns (D-03)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    price: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rooms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    size_sqm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    contact_info: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    post_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    source_badge: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Metadata columns (D-04)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # D-05: Same-source deduplication constraint
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_listing_source_source_id"),
    )
