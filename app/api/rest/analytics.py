from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.analytics_service import AnalyticsService
from app.schemas import UrlStatsRequest, UrlStatsResponse
from app.api.rest.dependencies import(
    get_analytics_service,
    rate_limiter,
    validate_short_code
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get(
    "/{short_code}",
    response_model=UrlStatsResponse,
    summary="Get URL analytics",
    description="Get compregensive analytics for a specific URL",
    dependencies=[Depends(rate_limiter)]
)
async def get_url_analytics(
    short_code: str = Depends(validate_short_code),
    include_clicks: bool = False,
    click_limit: int = 100,
    db: AsyncSession = Depends(get_db),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """
    Get detailed analytics for a URL.
    
    - **short_code**: The short code to analyze
    - **include_clicks**: Include detailed click data
    - **click_limit**: Maximum number of clicks to return (1-100)
    
    Returns comprehensive analytics including:
    - Basic statistics (clicks, unique visitors, etc.)
    - Geographic distribution
    - Referrer analysis
    - User agent breakdown
    - Daily activity trends
    """

    try:
        if click_limit > 100:
            click_limit = 100
        if click_limit < 1:
            click_limit = 1

        result = await analytics_service.get_url_stats(
            db=db,
            short_code=short_code,
            include_detailed_clicks=include_clicks,
            click_limit=click_limit
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
            detail="Failed to get URL analytics"
        )
    
@router.get(
    "/global/overview",
    summary="Global statistics",
    description="Get platform-wide statistics and overview",
    dependencies=[Depends(rate_limiter)]
)
async def get_global_stats(
    db: AsyncSession = Depends(get_db),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
) -> Dict[str, Any]:
    """
    Get global platform statistics.
    
    Returns:
    - Total URLs created
    - Total clicks
    - Active URLs
    - Recent activity
    - Popular URLs
    """

    try:
        result = await analytics_service.get_global_stats(db=db)
        return result
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get global statistics"
        )
    
@router.get(
    "/trends/daily",
    summary="Daily trends",
    description="Get daily activity trends",
    dependencies=[Depends(rate_limiter)]
)
async def get_daily_trends(
    short_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
) -> Dict[str, Any]:
    """
    Get user agent breakdown (browsers, operating systems, devices).
    
    - **short_code**: Specific URL to analyze (optional, global if not provided)
    
    Returns breakdown of browsers, operating systems, and device types.
    """

    try:
        if short_code:
            short_code = await validate_short_code(short_code)

            result = await analytics_service.get_user_agent_stats(
                db=db,
                short_code=short_code
            )

            return {
                "short_code": short_code,
                "user_agent_data": result
            }
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user agent statistics"
        )
    
@router.get(
    "/performance/summary",
    summary="Performance summary",
    description="Get performance metrics summary",
    dependencies=[Depends(rate_limiter)]
)
async def get_performance_summary(
    short_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
) -> Dict[str, Any]:
    """
    Get performance metrics summary.
    
    - **short_code**: Specific URL to analyze (optional, global if not provided)
    
    Returns key performance indicators and metrics.
    """

    # Validate short_code if provided
    try:
        if short_code:
            short_code = await validate_short_code(short_code)

        if short_code:
            url_stats = await analytics_service.get_url_stats(
                db=db,
                short_code=short_code,
                include_detailed_clicks=False
            )

            if not url_stats:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Short code not found"
                )
            
            # Extract performance metrics from analytics
            analytics = url_stats.analytics
            click_stats = analytics.get("click_statistics", {})
            performance_metrics = analytics.get("performance_metrics", {})

            return {
                "short_code": short_code,
                "url": url_stats.url_info.original_url,
                "performance": {
                    "total_clicks": click_stats.get("total_clicks", 0),
                    "unique_visitors": click_stats.get("unique_visitors", 0),
                    "clicks_per_day": performance_metrics.get("clicks_per_day", 0),
                    "unique_visitor_ratio": performance_metrics.get("unique_visitor_ratio", 0),
                    "days_active": click_stats.get("active_days", 0),
                    "last_activity": click_stats.get("last_click"),
                    "conversion_rate": performance_metrics.get("unique_visitor_ratio", 0)
                }
            }
        
        else:
            # Global performance
            global_stats = await analytics_service.get_global_stats(db=db)

            return {
                "short_code": None,
                "performance": global_stats.get("overview", {}),
                "popular_urls": global_stats.get("global_urls", [])
            }
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get performance summary"
        )

@router.post(
    "/cache/invalidate",
    summary="Invalidate analytics cache",
    description="Clear analytics cache for better performance",
    dependencies=[Depends(rate_limiter)]
)
async def invalidate_analytics_cache(
    pattern: Optional[str] = None,
    analytics_service: AnalyticsService = Depends(get_analytics_service)
) -> Dict[str, Any]:
    """
    Invalidate analytics cache.
    
    - **pattern**: Cache pattern to invalidate (optional, all if not provided)
    
    Use with caution - this will force recalculation of analytics data.
    """

    try:
        deleted_count = await analytics_service.invalidate_cache(pattern)

        return {
            "success": True,
            "message": f"Invalidated {deleted_count} cache entries",
            "pattern": pattern or "all",
            "deleted_count": deleted_count
        }
    
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invalidate cache"
        )
    


@router.get(
    "/export/{short_code}",
    summary="Export analytics data",
    description="Export analytics data in JSON format",
    dependencies=[Depends(rate_limiter)]
)
async def export_analytics_data(
    short_code: str = Depends(validate_short_code),
    include_detailed_clicks: bool = True,
    db: AsyncSession = Depends(get_db),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
) -> Dict[str, Any]:
    """
    Export comprehensive analytics data for a URL.
    
    - **short_code**: The short code to export data for
    - **include_detailed_clicks**: Include individual click records
    
    Returns complete analytics dataset for external analysis.
    """

    try:

        # Get comprehensice stats
        url_stats = await analytics_service.get_url_stats(
            db=db,
            short_code=short_code,
            include_detailed_clicks=include_detailed_clicks,
            click_limit=100
        )

        if not url_stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Short code not found"
            )
        
        # Get additional data
        daily_stats = await analytics_service.get_daily_stats(
            db=db,
            short_code=short_code,
            days=365
        )

        geo_stats = await analytics_service.get_geographic_stats(
            db=db,
            short_code=short_code,
            limit=100 
        )
        
        referrer_stats = await analytics_service.get_referrer_stats(
            db=db,
            short_code=short_code,
            limit=100
        )
        
        ua_stats = await analytics_service.get_user_agent_stats(
            db=db,
            short_code=short_code
        )

        # combine all data

        export_data = {
            "export_info": {
                "short_code": short_code,
                "export_date": url_stats.analytics.get("generated_at"),
                "data_types": [
                    "url_info",
                    "basic_analytics",
                    "daily_trends",
                    "geographic_distribution",
                    "referrer_analysis",
                    "user_agent_breakdown"
                ]
            },
            "url_info": url_stats.url_info.dict(),
            "analytics": url_stats.analytics,
            "daily_trends": daily_stats,
            "geographic_data": geo_stats,
            "referrer_data": referrer_stats,
            "user_agent_data": ua_stats
        }

        return export_data
    
    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export analytics data"
        )


@router.get(
    "/geographic/distribution",
    summary="Geographic distribution",
    description="Get geographic distribution of clicks",
    dependencies=[Depends(rate_limiter)]
)
async def get_geographic_stats(
    short_code: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
) -> Dict[str, Any]:
    """
    Get geographic distribution of clicks.
    
    - **short_code**: Specific URL to analyze (optional, global if not provided)
    - **limit**: Maximum countries to return (1-50)
    
    Returns country and city breakdown of clicks.
    """
    try:
        if limit > 50:
            limit = 50
        if limit < 1:
            limit = 1
        
        # Validate short_code if provided
        if short_code:
            short_code = await validate_short_code(short_code)
        
        result = await analytics_service.get_geographic_stats(
            db=db,
            short_code=short_code,
            limit=limit
        )
        
        return {
            "short_code": short_code,
            "geographic_data": result
        }
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get geographic statistics"
        )

@router.get(
    "/referrers/top",
    summary="Top referrers",
    description="Get top referrer sources",
    dependencies=[Depends(rate_limiter)]
)
async def get_top_referrers(
    short_code: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
) -> Dict[str, Any]:
    """
    Get top referrer sources.
    
    - **short_code**: Specific URL to analyze (optional, global if not provided)
    - **limit**: Maximum referrers to return (1-50)
    
    Returns breakdown of traffic sources.
    """
    try:
        if limit > 50:
            limit = 50
        if limit < 1:
            limit = 1
        
        # Validate short_code if provided
        if short_code:
            short_code = await validate_short_code(short_code)
        
        result = await analytics_service.get_referrer_stats(
            db=db,
            short_code=short_code,
            limit=limit
        )
        
        return {
            "short_code": short_code,
            "referrers": result
        }
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get referrer statistics"
        )