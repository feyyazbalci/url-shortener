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


    