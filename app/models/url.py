from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from typing import Optional

from .base import BaseModel

class ShortenedUrl(BaseModel):
    __tablename__ = "shortened_urls"

    short_code = Column(
        String(50),
        primary_key=True,
        index=True,
        doc="Unique short code for the URL"
    )

    original_url = Column(
        Text,
        nullable=False,
        doc="The original long URL"
    )

    # Metadata

    title = Column(
        String(500),
        nullable=True,
        doc="URL title"
    )

    description = Column(
        Text,
        nullable=True,
        doc="URL description"
    )

    # Statistics

    click_count = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Number of times the short URL has been clicked"
    )

    # Expiration
    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Expiration date of the short URL"
    )

    # Status

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        doc="Indicates if the short URL is active"
    )

    is_custom = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Indicates if the short code is custom"
    )

    # Creator info

    creator_ip = Column(
        String(45),
        nullable=True,
        doc="IP address of the creator"
    )

    creator_user_agent = Column(
        Text,
        nullable=True,
        doc="User agent of the creator"
    )

    # Relationships
    
    clicks = relationship(
        "UrlClick",
        back_populates="url",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    # Indexes
    __table_args__ = (
        Index("ix_shortened_urls_created_at", "created_at"),
        Index("ix_shortened_urls_expires_at", "expires_at"),
        Index("ix_shortened_urls_active", "is_active"),
        Index("ix_shortened_urls_creator_ip", "creator_ip"),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if not self.expires_at and kwargs.get("expiration_days"):
            days = kwargs.get("expiration_days", 30)
            self.expires_at = datetime.utcnow() + timedelta(days=days)

    @property
    def is_expired(self) -> bool:
        # Check if the URL is expired
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at.replace(tzinfo=None)
    
    @property
    def is_accessible(self) -> bool:
        return self.is_active and not self.is_expired
    
    @property
    def days_until_expiry(self) -> Optional[int]:
        if not self.expires_at:
            return None
        
        delta = self.expires_at.replace(tzinfo=None) - datetime.utcnow()
        return max(0, delta.days)
    
    def increment_clicks(self) -> None:
        self.click_count += 1

    def deactivate(self) -> None:
        self.is_active = False

    def reactivate(self) -> None:
        self.is_active = True

    def extend_expiry(self, days: int) -> None:
        if self.expires_at:
            self.expires_at += timedelta(days=days)
        else:
            self.expires_at = datetime.utcnow() + timedelta(days=days)

class UrlClick(BaseModel):
    __tablename__ = "url_clicks"

    id = Column(Integer, primary_key=True, autoincrement=True)

    short_code = Column(
        String(50),
        nullable=False,
        index=True,
        doc="Short code of the clicked URL"
    )

    ip_address = Column(
        String(50),
        nullable=True,
        doc="IP address of the clicker"
    )

    user_agent = Column(
        Text,
        nullable=True,
        doc="User agent of the clicker"
    )
    
    referer = Column(
        Text,
        nullable=True,
        doc="Referrer URL"
    )

    # Geographic info
    country = Column(
        String(2), # ISO country code
        nullable=True,
        doc="Country code of the clicker"
    )

    city = Column(
        String(100),
        nullable=True,
        doc="City of the clicker"
    )

    # Relationship
    url = relationship("ShortenedUrl", back_populates="clicks")

    # Indexes
    __table_args__ = (
        Index("ix_url_clicks_short_code_created", "short_code", "created_at"),
        Index("ix_url_clicks_ip", "ip_address"),
        Index("ix_url_clicks_country", "country"),
    )
    
    def __init__(self, short_code: str, **kwargs):
        super().__init__(**kwargs)
        self.short_code = short_code


