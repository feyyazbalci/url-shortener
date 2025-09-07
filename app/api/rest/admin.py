from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.cache_service import cache_service
from app.services.validate_service import validation_service
from app.schemas import SuccessResponse, HealthCheckResponse
from app.api.rest.dependencies import (
    check_services_health,
    require_admin,
    rate_limiter
)
from app.core.config import settings
from datetime import datetime

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="System health check",
    description="Check the health status of all system components",
    dependencies=[Depends(rate_limiter)]
)
async def health_check(
    services_health: Dict[str, bool] = Depends(check_services_health)
):
    """
    Comprehensive system health check.
    
    Checks:
    - Database connectivity
    - Redis connectivity
    - Cache service status
    - Validation service status
    """
    try:
        overall_status = "healthy" if all(services_health.values()) else "unhealthy"
        
        return HealthCheckResponse(
            status=overall_status,
            timestamp=datetime.utcnow(),
            services=services_health,
            version=settings.app_version
        )
    
    except Exception:
        return HealthCheckResponse(
            status="error",
            timestamp=datetime.utcnow(),
            services={"error": True},
            version=settings.app_version
        )

@router.get(
    "/stats/system",
    summary="System statistics",
    description="Get comprehensive system statistics",
    dependencies=[Depends(rate_limiter), Depends(require_admin)]
)
async def get_system_stats() -> Dict[str, Any]:
    """
    Get system-wide statistics.
    
    Returns performance metrics, cache statistics, and system info.
    """
    try:
        # Cache statistics
        cache_stats = await cache_service.get_stats()
        
        # Validation service statistics
        validation_stats = await validation_service.get_validation_stats()
        
        # System configuration
        system_info = {
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "environment": "production" if not settings.debug else "development",
            "configuration": {
                "rate_limit_per_minute": settings.rate_limit_per_minute,
                "cache_ttl": settings.cache_ttl,
                "short_code_length": settings.short_code_length,
                "max_url_length": settings.max_url_length,
                "default_expiry_days": settings.default_expiry_days
            }
        }
        
        return {
            "system_info": system_info,
            "cache_stats": cache_stats,
            "validation_stats": validation_stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system statistics"
        )

@router.post(
    "/cache/flush",
    response_model=SuccessResponse,
    summary="Flush all cache",
    description="Clear all cached data (use with caution)",
    dependencies=[Depends(rate_limiter), Depends(require_admin)]
)
async def flush_cache():
    """
    Flush all cache data.
    
    WARNING: This will clear all cached data and may impact performance
    until the cache is rebuilt.
    """
    try:
        success = await cache_service.flush_all()
        
        if success:
            return SuccessResponse(
                message="All cache data has been flushed successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to flush cache"
            )
    
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to flush cache"
        )

@router.get(
    "/cache/keys",
    summary="List cache keys",
    description="List all cache keys (for debugging)",
    dependencies=[Depends(rate_limiter), Depends(require_admin)]
)
async def list_cache_keys(
    pattern: str = "*",
    limit: int = 100
) -> Dict[str, Any]:
    """
    List cache keys matching a pattern.
    
    - **pattern**: Key pattern to match (default: all keys)
    - **limit**: Maximum keys to return
    """
    try:
        keys = await cache_service.keys(pattern)
        
        # Limit results
        if len(keys) > limit:
            keys = keys[:limit]
            truncated = True
        else:
            truncated = False
        
        return {
            "pattern": pattern,
            "total_found": len(keys),
            "returned": len(keys),
            "truncated": truncated,
            "keys": keys
        }
    
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list cache keys"
        )

@router.delete(
    "/cache/keys",
    response_model=SuccessResponse,
    summary="Delete cache keys",
    description="Delete cache keys matching a pattern",
    dependencies=[Depends(rate_limiter), Depends(require_admin)]
)
async def delete_cache_keys(pattern: str):
    """
    Delete cache keys matching a pattern.
    
    - **pattern**: Key pattern to match and delete
    """
    try:
        deleted_count = await cache_service.delete_pattern(pattern)
        
        return SuccessResponse(
            message=f"Deleted {deleted_count} cache keys matching pattern '{pattern}'"
        )
    
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete cache keys"
        )

@router.get(
    "/validation/blacklist",
    summary="Get blacklisted domains",
    description="List all blacklisted domains",
    dependencies=[Depends(rate_limiter), Depends(require_admin)]
)
async def get_blacklisted_domains() -> Dict[str, Any]:
    """
    Get all blacklisted domains.
    """
    try:
        domains = validation_service.get_blacklisted_domains()
        
        return {
            "blacklisted_domains": domains,
            "total_count": len(domains)
        }
    
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get blacklisted domains"
        )

@router.post(
    "/validation/blacklist",
    response_model=SuccessResponse,
    summary="Add domain to blacklist",
    description="Add a domain to the blacklist",
    dependencies=[Depends(rate_limiter), Depends(require_admin)]
)
async def add_blacklisted_domain(domain: str):
    """
    Add a domain to the blacklist.
    
    - **domain**: Domain to blacklist (e.g., example.com)
    """
    try:
        success = validation_service.add_blacklisted_domain(domain)
        
        if success:
            return SuccessResponse(
                message=f"Domain '{domain}' added to blacklist"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to add domain to blacklist"
            )
    
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add domain to blacklist"
        )

@router.delete(
    "/validation/blacklist/{domain}",
    response_model=SuccessResponse,
    summary="Remove domain from blacklist",
    description="Remove a domain from the blacklist",
    dependencies=[Depends(rate_limiter), Depends(require_admin)]
)
async def remove_blacklisted_domain(domain: str):
    """
    Remove a domain from the blacklist.
    
    - **domain**: Domain to remove from blacklist
    """
    try:
        success = validation_service.remove_blacklisted_domain(domain)
        
        if success:
            return SuccessResponse(
                message=f"Domain '{domain}' removed from blacklist"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Domain '{domain}' not found in blacklist"
            )
    
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove domain from blacklist"
        )

@router.post(
    "/validation/bulk-check",
    summary="Bulk domain validation",
    description="Validate multiple domains at once",
    dependencies=[Depends(rate_limiter), Depends(require_admin)]
)
async def bulk_validate_domains(domains: List[str]) -> Dict[str, Any]:
    """
    Validate multiple domains.
    
    - **domains**: List of domains to validate (max 20)
    """
    try:
        if len(domains) > 20:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 20 domains allowed per request"
            )
        
        results = await validation_service.bulk_check_domains(domains)
        
        return {
            "total_domains": len(domains),
            "results": results
        }
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate domains"
        )

@router.post(
    "/maintenance/cleanup",
    response_model=SuccessResponse,
    summary="Run maintenance cleanup",
    description="Clean up expired cache and perform maintenance tasks",
    dependencies=[Depends(rate_limiter), Depends(require_admin)]
)
async def run_maintenance_cleanup():
    """
    Run system maintenance cleanup.
    
    This will:
    - Clean expired cache entries
    - Remove temporary data
    - Optimize system performance
    """
    try:
        # Clean expired validation cache
        expired_count = await validation_service.clean_expired_cache()
        
        # Additional cleanup tasks can be added here
        
        return SuccessResponse(
            message=f"Maintenance cleanup completed. Cleaned {expired_count} expired cache entries."
        )
    
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run maintenance cleanup"
        )

@router.get(
    "/config",
    summary="Get system configuration",
    description="Get current system configuration",
    dependencies=[Depends(rate_limiter), Depends(require_admin)]
)
async def get_system_config() -> Dict[str, Any]:
    """
    Get current system configuration.
    """
    try:
        return {
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "debug": settings.debug,
            "api_prefix": settings.api_prefix,
            "base_url": settings.base_url,
            "short_code_length": settings.short_code_length,
            "max_url_length": settings.max_url_length,
            "default_expiry_days": settings.default_expiry_days,
            "rate_limit_per_minute": settings.rate_limit_per_minute,
            "rate_limit_burst": settings.rate_limit_burst,
            "cache_ttl": settings.cache_ttl,
            "redis_enabled": settings.redis_enabled,
            "enable_metrics": settings.enable_metrics,
            "log_level": settings.log_level
        }
    
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system configuration"
        )