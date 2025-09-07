from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import logging
import time
import uvicorn

from app.core.config import settings
from app.core.database import init_database, init_redis, close_database, close_redis
from app.api.rest.router import api_router
from app.api.rest.dependencies import check_services_health

from app.api.rest.urls import redirect_url
from app.api.rest.dependencies import (
    validate_short_code,
    get_url_service,
    get_client_ip,
    get_user_agent,
    get_referer
)
from app.core.database import get_db

# Logging configuration
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""

    # Startup

    logger.info("Starting URL Shortener Service...")

    try:
        await init_database()
        logger.info("Database initialized")

        # Initialize database
        await init_redis()
        logger.info("Redis initialized")

        logger.info("Application startup completed")

    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise

    yield  # Application runs here

    # Shutdown
    logger.info("Shutting down URL Shortener Service...")
    
    try:
        # Close connections
        await close_database()
        await close_redis()
        
        logger.info("✅ Application shutdown completed")
        
    except Exception as e:
        logger.error(f"❌ Shutdown error: {e}")

    

# FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="A modern, async URL shortener service with comprehensive analytics",
    version=settings.app_version,
    openapi_url=f"{settings.api_prefix}/openapi.json",
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=settings.allowed_methods,
    allow_headers=settings.allowed_headers
)

# Trusted Host Middleware (security)
if not settings.debug:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"] # Configure this properly in production
    )

# Request/Response middleware for logging and metrics
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    """Request processing middleware"""

    start_time = time.time()

    # Log request
    logger.info(
        f"Request: {request.method} {request.url.path} "
        f"from {request.client.host if request.client else 'unknown'}"
    )

    # Process request
    try:
        response = await call_next(request)

        # Calculate response time
        process_time = time.time() - start_time

        # Add response headers
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-API-Version"] = settings.app_version
        
        # Log response
        logger.info(
            f"Response: {response.status_code} "
            f"({process_time:.3f}s)"
        )

        return response
    
    except Exception as e:
        # Log error
        process_time = time.time() - start_time
        logger.error(
            f"Request failed: {request.method} {request.url.path} "
            f"- {str(e)} ({process_time:.3f}s)"
        )

        # Return error response
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal server error",
                "request_id": str(id(request))
            },
            headers={
                "X-Process-Time": str(process_time),
                "X-API-Version": settings.app_version
            }
        )
    
app.include_router(api_router, prefix=settings.api_prefix)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": f"{settings.api_prefix}/docs",
        "redoc": f"{settings.api_prefix}/redoc",
        "openapi": f"{settings.api_prefix}/openapi.json"
    }

@app.get("/health")
async def health():
    """Simple health check endpoint."""

    try:
        services_health = await check_services_health()
        overall_status = "healthy" if all(services_health.values()) else "unhealthy"

        return {
            "status": overall_status,
            "services": services_health,
            "version": settings.app_version
        }
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": "Health check failed"
            }
        )
    
# Redirect endpoint (short URL resolution)
@app.get("/{short_code}")
async def redirect_short_url(short_code: str, request: Request):
    """Direct short URL redirect (no API prefix)."""

    try:
        # Get dependencies manually
        db = get_db().__anext__()
        async for session in db:
            result = await redirect_url(
                short_code=await validate_short_code(short_code),
                db=session,
                url_service=get_url_service(),
                client_ip=await get_client_ip(request),
                user_agent=await get_user_agent(request),
                referer=await get_referer(request)
            )
            return result
    
    except Exception as e:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": "Short URL not found",
                "short_code": short_code
            }
        )
    
# Custom exception handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 handler."""
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": "Resource not found",
            "path": request.url.path
        }
    )

@app.exception_handler(422)
async def validation_error_handler(request: Request, exc):
    """Custom validation error handler."""
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": "Validation error",
            "details": exc.detail if hasattr(exc, 'detail') else str(exc)
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Custom 500 handler."""
    logger.error(f"Internal error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "request_id": str(id(request))
        }
    )

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )