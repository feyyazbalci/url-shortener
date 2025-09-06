from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.url_service import UrlService
from app.services.analytics_service import AnalyticsService
from app.services.cache_service import cache_service
from app.services.validate_service import validation_service
from app.core.config import settings
from app.core.database import check_database_health, check_redis_health

# Security
security = HTTPBearer(auto_error=False)

# Service dependencies
def get_url_service() -> UrlService:
    """URL service dependency."""
    return UrlService()

def get_analytics_service() -> AnalyticsService:
    """Analytics service dependency."""
    return AnalyticsService()

def get_cache_service():
    return cache_service

def get_validation_service():
    return validation_service

# Request info dependencies
async def get_client_ip(request: Request) -> str:
    """Get client IP address."""

    # Check X-Forwarded-For header (for proxy/load balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Get First IP address
        return forwarded_for.split(",")[0].strip()
    
    # Control X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Direct client IP
    if hasattr(request.client, 'host'):
        return request.client.host
    
    return "unknown"

async def get_user_agent(request: Request) -> str:
    """Get the user agent."""
    return request.headers.get("User-Agent", "unknown")

async def get_referer(request: Request) -> Optional[str]:
    return request.headers.get("Referer")

class RateLimiter:
    """Simple rate limiter."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def __call__(
        self,
        request: Request,
        client_ip: str = Depends(get_client_ip)
    ):
        if not settings.rate_limit_per_minute:
            return # Rate limiting disabled
        
        cache_key = f"rate_limit:{client_ip}"

        try:
            current_requests = await cache_service.get(cache_key, 0)

            if current_requests >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "max_requests": self.max_requests,
                        "window_seconds": self.window_seconds,
                        "retry_after": self.window_seconds
                    }
                )
            
            await cache_service.incr(cache_key)

            # Set expiry on first request
            if current_requests == 0:
                await cache_service.expire(cache_key, self.window_seconds)
        except HTTPException:
            raise
        except Exception:
            pass

# Rate limiter instances
rate_limiter = RateLimiter(
    max_requests=settings.rate_limit_per_minute,
    window_seconds=60
)

# Stricter rate limiter for creation operations
creation_rate_limiter = RateLimiter(
    max_requests=settings.rate_limit_burst,
    window_seconds=60
)

async def get_current_user(token: Optional[str] = Depends(security)):
    """Current user (placeholder for auth)"""

    # This simple version does not include authentication.
    # JWT token validation will be available here in the future.

    return None

async def require_admin(current_user=Depends(get_current_user)):
    # Admin control will be here in the future
    return True

# Validation dependencies
async def validate_short_code(short_code: str) -> str:
    """Short code validation"""
    if not short_code or len(short_code.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Short code is required"
        )
    
    # Basic format validation
    short_code = short_code.strip()
    if len(short_code) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Short code too long (max 50 characters)"
        )
    
    allowed_chars = settings.allowed_chars + "-_"
    if not all(c in allowed_chars for c in short_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Short code contains invalid characters"
        )
    
    return short_code

# Database transaction wrapper
class DatabaseTransaction:
    """Database transaction dependency."""
    def __init__(self):
        self.db: Optional[AsyncSession] = None
    
    async def __call__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        return self

# Common response headers
def add_cors_headers(response):
    """Add CORS headers"""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

async def check_services_health():
    return {
        "database": await check_database_health(),
        "redis": await check_redis_health(),
        "cache_service": (await cache_service.get_stats()).get("status") == "connected",
        "validation_service": True  # Always available
    }