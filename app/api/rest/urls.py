from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.url_service import UrlService
from app.services.analytics_service import AnalyticsService
from app.services.validate_service import ValidationService

from app.schemas import (
    ShortenUrlRequest,
    ShortenUrlResponse,
    ShortenedUrlResponse,
    ResolveUrlResponse,
    ListUrlsRequest,
    ListUrlsResponse,
    BulkShortenRequest,
    BulkShortenResponse,
    UrlValidationResponse,
    SuccessResponse,
    ErrorResponse
)

from app.api.rest.dependencies import (
    get_url_service,
    get_analytics_service,
    get_validation_service,
    get_client_ip,
    get_user_agent,
    get_referer,
    rate_limiter,
    creation_rate_limiter,
    validate_short_code
)

router = APIRouter(prefix="/urls", tags=["URLs"])

@router.post(
    "/shorten",
    response_model=ShortenedUrlResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Shorten URL",
    description="Create a shortened URL from a long URL",
    dependencies=[Depends(creation_rate_limiter)]
)
async def shorten_url(
    request: ShortenUrlRequest,
    db: AsyncSession = Depends(get_db),
    url_service: UrlService = Depends(get_url_service),
    client_ip: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent)
):
    """
    Create a shortened URL.
    
    - **original_url**: The URL to shorten (required)
    - **custom_code**: Custom short code (optional, 3-50 chars)
    - **expires_in_days**: Expiration in days (optional, 1-3650)
    - **title**: URL title for reference (optional)
    - **description**: URL description (optional)
    """

    try:
        result = await url_service.shorten_url(
            request=request,
            creator_ip=client_ip,
            creator_user_agent=user_agent
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to shorten URL"
        )
    
@router.get(
    "/{short_code}",
    response_class=RedirectResponse,
    summary="Redirect to original URL",
    description="Redirect to the original URL and track the click",
    dependencies=[Depends(rate_limiter)]
)
async def redirect_url(
    short_code: str = Depends(validate_short_code),
    db: AsyncSession = Depends(get_db),
    url_service: UrlService = Depends(get_url_service),
    client_ip: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent),
    referer: Optional[str] = Depends(get_referer)
):
    """
    Redirect to the original URL.
    
    This endpoint:
    1. Resolves the short code to original URL
    2. Tracks the click for analytics
    3. Redirects the user to the original URL
    """

    try:
        result = await url_service.resolve_url(
            db=db,
            short_code=short_code,
            track_click=True,
            visitor_ip=client_ip,
            user_agent=user_agent,
            referer=referer
        )

        if not result.sucess or not result.found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.message or "Short code not found"
            )
        
        if result.expired:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="This short URL has expired"
            )
        
        return RedirectResponse(
            url=result.original_url,
            status_code=status.HTTP_302_FOUND
        )
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve URL"
        )
    
@router.get(
    "/{short_code}/info",
    response_model=ShortenedUrlResponse,
    summary="Get URL information",
    description="Get detailed information about a shortened URL",
    dependencies=[Depends(rate_limiter)]
)
async def get_url_info(
    short_code: str = Depends(validate_short_code),
    include_clicks: bool = False,
    db: AsyncSession = Depends(get_db),
    url_service: UrlService = Depends(get_url_service)
):
    """
    Get URL information without redirecting.
    
    - **short_code**: The short code to look up
    - **include_clicks**: Include recent click data
    """

    try:
        result = await url_service.get_url_info(
            db=db,
            short_code=short_code,
            include_recent_clicks=include_clicks
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Short code not found"
            )
        
        return result
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get URL information"
        )
    
