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
    
@router.get(
    "/",
    response_model=ListUrlsResponse,
    summary="List URLs",
    description="List shortened URLs with filtering and pagination",
    dependencies=[Depends(rate_limiter)]
)
async def list_urls(
    limit: int = 20,
    offset: int = 0,
    is_active: Optional[bool] = None,
    is_expired: Optional[bool] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: AsyncSession = Depends(get_db),
    url_service: UrlService = Depends(get_url_service)
):
    """
    List shortened URLs.
    
    - **limit**: Number of URLs to return (1-100)
    - **offset**: Number of URLs to skip
    - **is_active**: Filter by active status
    - **is_expired**: Filter by expiration status
    - **sort_by**: Sort field (created_at, click_count, expires_at)
    - **sort_order**: Sort direction (asc, desc)
    """

    try:
        # Validate parameters
        if limit > 100:
            limit = 100
        if limit < 1:
            limit = 1
        if offset < 0:
            offset = 0

        request = ListUrlsRequest(
            limit=limit,
            offset=offset,
            is_active=is_active,
            is_expired=is_expired,
            sort_by=sort_by,
            sort_order=sort_order
        )

        urls, total = await url_service.list_urls(
            db=db,
            request=request
        )

        # Convert to response format
        url_responses = []
        for url in urls:
            url_response = ShortenedUrlResponse(
                short_code=url.short_code,
                short_url=f"{url_service.base_url}/{url.short_code}",
                original_url=url.original_url,
                title=url.title,
                description=url.description,
                click_count=url.click_count,
                is_active=url.is_active,
                is_custom=url.is_custom,
                is_expired=url.is_expired,
                expires_at=url.expires_at,
                days_until_expiry=url.days_until_expiry,
                created_at=url.created_at,
                updated_at=url.updated_at
            )
            url_responses.append(url_response)

        return ListUrlsResponse(
            urls=url_responses,
            total=total,
            limit=limit,
            offset=offset
        )
    
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list URLs"
        )
    
@router.put(
    "/{short_code}",
    response_model=ShortenedUrlResponse,
    summary="Update URL",
    description="Update URL metadata and settings",
    dependencies=[Depends(creation_rate_limiter)]
)
async def update_url(
    short_code: str = Depends(validate_short_code),
    title: Optional[str] = None,
    description: Optional[str] = None,
    expires_in_days: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    url_service: UrlService = Depends(get_url_service)
):
    """
    Update URL metadata.
    
    - **title**: New title (optional)
    - **description**: New description (optional)
    - **expires_in_days**: New expiration (optional)
    - **is_active**: Active status (optional)
    """

    try:
        result = await url_service.update_url(
            db=db,
            short_code=short_code,
            title=title,
            description=description,
            expires_in_days=expires_in_days,
            is_active=is_active
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
            detail="Failed to update URL"
        )
    
@router.delete(
    "/{short_code}",
    response_model=SuccessResponse,
    summary="Delete URL",
    description="Delete a shortened URL permanently",
    dependencies=[Depends(creation_rate_limiter)]
)
async def delete_url(
    short_code: str = Depends(validate_short_code),
    db: AsyncSession = Depends(get_db),
    url_service: UrlService = Depends(get_url_service)
):
    """
    Delete a shortened URL.
    
    This action is irreversible and will:
    1. Remove the URL from the database
    2. Clear it from cache
    3. Make the short code available for reuse
    """
    try:
        success = await url_service.delete_url(db=db, short_code=short_code)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Short code not found"
            )
        
        return SuccessResponse(
            message=f"URL {short_code} deleted successfully"
        )
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete URL"
        )
    
@router.post(
    "/bulk/shorten",
    response_model=BulkShortenResponse,
    summary="Bulk shorten URLs",
    description="Shorten multiple URLs at once",
    dependencies=[Depends(creation_rate_limiter)]
)
async def bulk_shorten_urls(
    request: BulkShortenRequest,
    db: AsyncSession = Depends(get_db),
    url_service: UrlService = Depends(get_url_service),
    client_ip: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent)
):
    """
    Bulk shorten URLs.
    
    - **urls**: List of URLs to shorten (max 50)
    - **default_expires_in_days**: Default expiration for all URLs
    """
    results = []
    errors = []

    for i, url_request in enumerate(request.urls):
        try:
            if not url_request.expires_in_days and request.default_expires_in_days:
                url_request.expires_in_days = request.default_expires_in_days

                result = await url_service.shorten_url(
                    db=db,
                    request=url_request,
                    creator_ip=client_ip,
                    creator_user_agent=user_agent
                )

                results.append(result)

        except Exception as e:
            errors.append({
                "index": i,
                "url": str(url_request.original_url),
                "error": str(e)
            })

    return BulkShortenResponse(
        results=results,
        success_count=len(results),
        failed_count=len(errors),
        errors=errors if errors else None
    )

@router.post(
    "/validate",
    response_model=UrlValidationResponse,
    summary="Validate URL",
    description="Validate URL accessibility and safety",
    dependencies=[Depends(rate_limiter)]
)
async def validate_url(
    url: str,
    check_accessibility: bool = True,
    check_count: bool = False,
    validation_service: ValidationService = Depends(get_validation_service)
):
    """
    Validate a URL.
    
    - **url**: URL to validate
    - **check_accessibility**: Check if URL is accessible
    - **check_content**: Perform content analysis
    """

    try:
        result = await validation_service.validate_url(
            url=url,
            check_accessibility=check_accessibility,
            check_content=check_count,
            check_safety=True
        )
        
        return UrlValidationResponse(
            is_valid=result["is_valid"],
            is_accessible=result["is_accessible"],
            status_code=result.get("status_code"),
            title=result.get("title"),
            message="; ".join(result.get("errors", []) + result.get("warnings", []))
        )
    
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate URL"
        )