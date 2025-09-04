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
