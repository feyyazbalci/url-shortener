from fastapi import APIRouter

from . import urls, analytics, admin

api_router = APIRouter()

api_router.include_router(urls.router)
api_router.include_router(analytics.router)
api_router.include_router(admin.router)

