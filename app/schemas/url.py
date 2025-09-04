from pydantic import Field, validator, HttpUrl
from typing import Optional, List
from datetime import datetime

from .base import BaseSchema, TimestampSchema, PaginationResponse


# Request Schemas
class ShortenUrlRequest(BaseSchema):
    # Request schema for shortening a URL

    original_url: HttpUrl = Field(
        ...,
        description="The original URL to be shortened",
        examples=["https://www.example.com/some/long/path"]
    )

    custom_code: Optional[str] = Field(
        None,
        min_length=3,
        max_length=50,
        pattern="^[a-zA-Z0-9_-]+$",
        description="Optional custom short code for the URL",
        examples=["my-link"]
    )

    expires_in_days: Optional[int] = Field(
        None,
        ge=1,
        le=3650, # up to 10 years
        description="Optional expiration time in days",
        examples=[30, 365]
    )

    title: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional title for the URL",
        examples=["This is a link to my awesome website"]
    )

    @validator('original_url', pre=True)
    def validate_url(cls, v):
        """URL validation."""
        if isinstance(v, str):
            # Ensure URL has scheme
            if not v.startswith(('http://', 'https://')):
                v = 'https://' + v
        return v
    
class UrlStatsRequest(BaseSchema):
    """Request schema for URL statistics."""

    short_code: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="The short code of the URL to get statistics for",
        examples=["my-link"]
    )

    include_clicks: bool = Field(
        False,
        description="Whether to include click statistics",
    )

    click_limit: int = Field(
        10,
        ge=1,
        le=100,
        description="Number of recent clicks to include if include_clicks is True",
    )

class ListUrlsRequest(BaseSchema):
    """Request schema for listing URLs with pagination."""

    limit: int = Field(20, ge=1, le=100, description="Number of URLs to return")
    offset: int = Field(0, ge=0, description="Starting point for listing URLs")

    # Filtering
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    is_expired: Optional[bool] = Field(None, description="Filter by expiration status")

    # Sorting
    sort_by: str = Field(
        "created_at",
        pattern=r"^(created_at|click_count|expires_at)$",
        description="Field to sort by",
    )

    sort_order: str = Field(
        "desc",
        pattern=r"^(asc|desc)$",
        description="Sort order (asc or desc)"
    )

# Response Schemas
class UrlClickResponse(BaseSchema):
    """URL click statistics."""

    id: int
    timestamp: datetime = Field(alias="created_at")
    ip_address: Optional[str]
    user_agent: Optional[str]
    referer: Optional[str]
    country: Optional[str]
    city: Optional[str]

class ShortenedUrlResponse(BaseSchema, TimestampSchema):
    """Response schema for a shortened URL"""

    short_code: str = Field(description="The short code for the URL")
    short_url: str = Field(description="The full shortened URL")
    original_url: str = Field(description="The original URL")

    title: Optional[str] = Field(None, description="The title of the URL")
    description: Optional[str] = Field(None, description="The description of the URL")

    click_count: int = Field(description="Total number of clicks")
    is_active: bool = Field("Whether the URL is active")
    is_custom: bool = Field("Whether the short code is custom")
    is_expired: bool = Field("Whether the URL has expired")

    expires_at: Optional[datetime] = Field(None, description="Expiration datetime if set")
    days_until_expiry: Optional[int] = Field(None, description="Days until expiration if set")

    # Optional analytics
    recent_clicks: Optional[List[UrlClickResponse]] = Field(
        None,
        description="List of recent clicks if requested",
    )

class ShortenUrlResponse(BaseSchema):

    success: bool = True
    short_code: str
    short_url: str
    original_url: str
    expires_at: Optional[datetime] = None
    created_at: datetime

class ResolveUrlResponse(BaseSchema):
    """Response schema for resolving a short URL"""

    success: bool
    original_url: Optional[str] = None
    found: bool
    expired: bool = False
    message: Optional[str] = None

class UrlStatsResponse(BaseSchema):
    """URL statistics response schema"""

    url_info: ShortenedUrlResponse
    analytics: dict = Field(
        description="Detailed analytics data",
        examples=[{
            "total_clicks": 150,
            "unique_ips": 75,
            "top_countries": [{"country": "TR", "count": 32}],
            "daily_clicks": [{"date": "2025-09-04", "clicks": 10}],
            "top_referers": [{"referer": "google.com", "count": 20}]
        }]
    )

class ListUrlsResponse(PaginationResponse):
    """URL listing response schema with pagination"""

    urls: List[ShortenedUrlResponse]

    def __init__(self, urls: List, total: int, limit: int, offset: int):
        super().__init__(
            items=urls,
            total=total,
            limit=limit,
            offset=offset,
            urls=urls
        )

# Utility Schemas
class BulkShortenRequest(BaseSchema):
    """Total URLs to shorten in bulk"""
    urls: List[ShortenUrlRequest] = Field(
        ...,
        min_items=1,
        max_items=50,
        description="Shortening requests"
    )

    default_expires_in_days: Optional[int] = Field(
        None,
        description="Default expiration in days for URLs without specific expiry"
    )

class BulkShortenResponse(BaseSchema):
    success: bool = True
    results: List[ShortenUrlResponse]
    failed_count: int = 0
    success_count: int
    errors: Optional[List[dict]] = None

class UrlValidationResponse(BaseSchema):    
    is_valid: bool
    is_accessible: bool = False
    status_code: Optional[int] = None
    title: Optional[str] = None
    message: Optional[str] = None