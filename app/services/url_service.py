import secrets
import string
import asyncio
from typing import Optional, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from app.models import ShortenedUrl, UrlClick
from app.schemas import (
    ShortenUrlRequest,
    ShortenUrlResponse,
    ResolveUrlResponse,
    ListUrlsRequest,
    ShortenedUrlResponse
)
from app.core.config import settings
from app.core.database import get_redis


class UrlService:
    """URL short and management service"""
    def __init__(self):
        self.base_url = settings.base_url
        self.short_code_length = settings.short_code_length
        self.allowed_chars = settings.allowed_chars
        self.max_url_length = settings.max_url_length
        self.default_expiry_days = settings.default_expiry_days

    async def shorten_url(
        self,
        db: AsyncSession,
        request: ShortenUrlRequest,
        creator_ip: Optional[str] = None,
        creator_user_agent: Optional[str] = None
    ) -> ShortenUrlResponse:
        
        # URL length control
        original_url = str(request.original_url)
        if len(original_url) > self.max_url_length:
            raise ValueError(f"URL too long. Maximum {self.max_url_length} characters allowed.")
        
        # Custom code control
        if request.custom_code:
            short_code = request.custom_code
            is_custom = True

            if await self._code_exists(db, short_code):
                raise ValueError(f"Custom code '{short_code}' already exists.")
            
            if not self._is_valid_code(short_code):
                raise ValueError("Invalid custom code format. Use only letters, numbers, hyphens and underscores.")
            
        else:
            # Random Custom Code
            short_code = await self._generate_unique_code(db)
            is_custom = False

        # Calculate expiry date
        expires_at = None
        if request.expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)
        elif self.default_expiry_days > 0:
            expires_at = datetime.utcnow() + timedelta(days=self.default_expiry_days)

        shortened_url = ShortenedUrl(
            short_code=short_code,
            original_url=original_url,
            title=request.title,
            description=request.description,
            expires_at=expires_at,
            is_custom=is_custom,
            creator_ip=creator_ip,
            creator_user_agent=creator_user_agent
        )

        db.add(shortened_url)
        await db.commit()
        await db.refresh(shortened_url)

        # Add Cache

        await self._cache_url(short_code, original_url)

        return ShortenUrlResponse(
            short_code=short_code,
            short_url=f"{self.base_url}/{short_code}",
            original_url=original_url,
            expires_at=expires_at,
            created_at=shortened_url.created_at
        )
    
    async def resolve_url(
        self,
        db: AsyncSession,
        short_code: str,
        track_click: Optional[str] = None,
        visitor_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        referer: Optional[str] = None
    ) -> ResolveUrlResponse:
        """Resolve short code and return original URL"""

        # Control in cache
        cached_url = await self._get_cached_url(short_code)
        if cached_url:
            if track_click:
                asyncio.create_task(
                    self._track_click_async(db, short_code, visitor_ip, user_agent, referer)
                )
            return ResolveUrlResponse(
                success=True,
                original_url=cached_url,
                found=True,
                expired=False
            )
        
        # Find in DB
        result = await db.execute(
            select(ShortenedUrl).where(ShortenedUrl.short_code == short_code)
        )
        url = result.scalar_one_or_none()

        if not url:
            return ResolveUrlResponse(
                success=False,
                found=False,
                expired=False,
                message="Short code not found"
            )
        
        if not url.is_accessible:
            expired = url.is_expired
            return ResolveUrlResponse(
                success=False,
                found=True,
                expired=expired,
                message="URL is not accessible" + (" (expired)" if expired else " (deactivated)")
            )
        
        # Click tracking
        if track_click:
            url.increment_clicks()
            await db.commit()

            asyncio.create_task(
                self._track_click_async(db, short_code, visitor_ip, user_agent, referer)
            )

        await self._cache_url(short_code, url.original_url)

        return ResolveUrlResponse(
            success=True,
            original_url=url.original_url,
            found=True,
            expired=False
        )

    async def get_url_info(
        self,
        db: AsyncSession,
        short_code: str,
        include_recent_clicks: bool = False
    ) -> Optional[ShortenedUrlResponse]:
        
        query = select(ShortenedUrl).where(ShortenedUrl.short_code == short_code)

        if include_recent_clicks:
            query = query.options(selectinload(ShortenedUrl.clicks))

        result = await db.execute(query)
        url = result.scalar_one_or_none()

        if not url:
            return None
        
        recent_clicks = []
        if include_recent_clicks:
            recent_clicks_query = (
                select(UrlClick)
                .where(UrlClick.short_code == short_code)
                .order_by(UrlClick.created_at.desc())
                .limit(10)
            )
            clicks_result = await db.execute(recent_clicks_query)
            recent_clicks = clicks_result.scalars().all()

        return ShortenedUrlResponse(
            short_code=url.short_code,
            short_url=f"{self.base_url}/{url.short_code}",
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
            updated_at=url.updated_at,
            recent_clicks=[
                {
                    "id": click.id,
                    "timestamp": click.created_at,
                    "ip_address": click.ip_address,
                    "user_agent": click.user_agent,
                    "referer": click.referer,
                    "country": click.country,
                    "city": click.city
                }
                for click in recent_clicks
            ] if include_recent_clicks else None
        )
    
    async def list_urls(
        self,
        db: AsyncSession,
        request: ListUrlsRequest
    ) -> Tuple[List[ShortenedUrl], int]:
        query = select(ShortenedUrl)
        count_query = select(func.count(ShortenedUrl.short_code))

        # Filters
        conditions = []

        if request.is_active is not None:
            conditions.append(ShortenedUrl.is_active == request.is_active)

        if request.is_expired is not None:
            if request.is_expired:
                conditions.append(
                    and_(
                        ShortenedUrl.expires_at.is_not(None),
                        ShortenedUrl.expires_at < func.now()
                    )
                )
            else:
                conditions.append(
                    or_(
                        ShortenedUrl.expires_at.is_(None),
                        ShortenedUrl.expires_at >= func.now()
                    )
                )

        if conditions:
            query = query.where(and_(*conditions))
            count_query =  count_query.where(and_(*conditions))

        # Sorting
        if request.sort_by == "created_at":
            order_col = ShortenedUrl.created_at
        elif request.sort_by == "click_count":
            order_col = ShortenedUrl.click_count
        elif request.sort_by == "expires_at":
            order_col = ShortenedUrl.expires_at
        else:
            order_col = ShortenedUrl.created_at

        if request.sort_order == "asc":
            query = query.order_by(order_col.asc())
        else:
            query = query.order_by(order_col.desc())

        # Pagination
        query = query.offset(request.offset).limit(request.limit)
        
        # Execute queries
        urls_result = await db.execute(query)
        count_result = await db.execute(count_query)
        
        urls = urls_result.scalars().all()
        total = count_result.scalar()
        
        return urls, total
    
    async def update_url(
        self,
        db: AsyncSession,
        short_code: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        expires_in_days: Optional[int] = None,
        is_active: Optional[bool] = None
    ) -> Optional[ShortenedUrlResponse]:
        
        result = await db.execute(
            select(ShortenedUrl).where(ShortenedUrl.short_code == short_code)
        )
        url = result.scalar_one_or_none()

        if not url:
            return None
        if title is not None:
            url.title = title
        if description is not None:
            url.description = description
        if expires_in_days is not None:
            url.expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        if is_active is not None:
            url.is_active = is_active

            if not is_active:
                await self._remove_from_cache(short_code)

        await db.commit()
        await db.refresh(url)

        return await self.get_url_info(db, short_code)
        
    
    async def delete_url(self, db: AsyncSession, short_code: str) -> bool:
        result = await db.execute(
            select(ShortenedUrl).where(ShortenedUrl.short_code == short_code)
        )

        url = result.scalar_one_or_none()

        if not url:
            return False
        
        await self._remove_from_cache(short_code)
        
        await db.delete(url)
        await db.commit()
        return True
    
    async def _generate_unique_code(self, db: AsyncSession, max_attempts: int = 10) -> str:        
        for _ in range(max_attempts):
            code = ''.join(
                secrets.choice(self.allowed_chars) 
                for _ in range(self.short_code_length)
            )
            
            if not await self._code_exists(db, code):
                return code
        
        for length in range(self.short_code_length + 1, self.short_code_length + 4):
            for _ in range(max_attempts):
                code = ''.join(
                    secrets.choice(self.allowed_chars) 
                    for _ in range(length)
                )
                
                if not await self._code_exists(db, code):
                    return code
        
        raise RuntimeError("Unable to generate unique short code")
    
    async def _code_exists(self, db: AsyncSession, code: str) -> bool:
        result = await db.execute(
            select(func.count(ShortenedUrl.short_code))
            .where(ShortenedUrl.short_code == code)
        )
        return result.scalar() > 0
    
    def _is_valid_code(self, code: str) -> bool:
        if not code or len(code) < 3 or len(code) > 50:
            return False
        
        allowed_chars = self.allowed_chars + "-_"
        return all(c in allowed_chars for c in code)
    
    async def _cache_url(self, short_code: str, original_url: str) -> None:
        """Add URL to cache"""
        redis = await get_redis()
        if redis:
            try:
                await redis.setex(
                    f"url:{short_code}",
                    settings.cache_ttl,
                    original_url
                )
            except Exception:
                pass

    async def _get_cached_url(self, short_code: str) -> Optional[str]:
        redis = await get_redis()
        if redis:
            try:
                return await redis.get(f"url:{short_code}")
            except Exception:
                return None
        return None
    
    async def _remove_from_cache(self, short_code:str) -> None:
        redis = await get_redis()
        if redis:
            try:
                return await redis.delete(f"url:{short_code}")
            except Exception:
                return None
        return None
    
    async def _track_click_async(
        self,
        db: AsyncSession,
        short_code: str,
        visitor_ip: Optional[str],
        user_agent: Optional[str],
        referer: Optional[str]
    ) -> None:
        """Async click tracking"""
        try:
            click = UrlClick(
                short_code=short_code,
                ip_address=visitor_ip,
                user_agent=user_agent,
                referer=referer
            )
            db.add(click)
            await db.commit()
            await db.refresh(click)
        except Exception:
            pass