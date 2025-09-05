from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, text
from collections import Counter, defaultdict
from urllib.parse import urlparse

from app.models import ShortenedUrl, UrlClick
from app.schemas import UrlStatsResponse, ShortenedUrlResponse, UrlClickResponse
from app.core.database import get_redis
import json

class AnalyticsService:
    """Analytics & Statistic Service"""

    def __init__(self):
        self.cache_prefix = "analytics:"
        self.cache_ttl = 1800 # 30 dakika

    async def get_url_stats(
        self,
        db: AsyncSession,
        short_code: str,
        include_detailed_clicks: bool = False,
        click_limit: int = 100
    ) -> Optional[UrlStatsResponse]:
        """Detailed URL Statics"""

        # Get URL info
        url_query = select(ShortenedUrl).where(ShortenedUrl.short_code == short_code)
        url_result = await db.execute(url_query)
        url = url_result.scalar_one_or_none()

        if not url:
            return None
        
        # Prepaire anaytics info
        analytics_data = await self._get_comprehensive_analytics(
            db, short_code, include_detailed_clicks, click_limit
        )

        # Prepaire url response
        url_response = ShortenedUrlResponse(
            short_code=url.short_code,
            short_url=f"http://localhost:8000/{url.short_code}",  # TODO: settings'den al
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
        
        return UrlStatsResponse(
            url_info=url_response,
            analytics=analytics_data
        )
    
    async def get_global_stats(self, db: AsyncSession) -> Dict[str, any]:

        cache_key = f"{self.cache_prefixc}global_stats"
        cached_stats = await self._get_cached_stats(cache_key)

        if cached_stats:
            return cached_stats
        
        total_urls_query = select(func.count(ShortenedUrl.short_code))
        active_urls_query = select(func.count(ShortenedUrl.short_code)).where(
            and_(
                ShortenedUrl.is_active == True,
                ShortenedUrl.expires_at > func.now()
            )
        )
        total_clicks_query = select(func.sum(ShortenedUrl.click_count))

        total_urls_result = await db.execute(total_urls_query)
        active_urls_result = await db.execute(active_urls_query)
        total_clicks_result = await db.execute(total_clicks_query)

        total_urls = total_urls_result.scalar() or 0
        active_urls = active_urls_result.scalar() or 0
        total_clicks = total_clicks_result.scalar() or 0

        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_urls_query = select(func.count(ShortenedUrl.short_code)).where(
            ShortenedUrl.created_at >= thirty_days_ago
        )

        recent_urls_result = await db.execute(recent_urls_query)
        recent_urls = recent_urls_result.scalar() or 0

        popular_urls_query = (
            select(ShortenedUrl.short_code, ShortenedUrl.original_url, ShortenedUrl.click_count)
            .where(ShortenedUrl.click_count > 0)
            .order_by(desc(ShortenedUrl.click_count))
            .limit(10)
        )

        popular_urls_result = await db.execute(popular_urls_query)
        popular_urls = [
            {
                "short_code": row.short_code,
                "original_url": row.original,
                "clicks": row.click_count
            }
            for row in popular_urls_result
        ]

        stats = {
            "overview": {
                "total_urls": total_urls,
                "active_urls": active_urls,
                "total_clicks": total_clicks,
                "recent_urls_30d": recent_urls,
                "average_clicks_per_url": round(total_clicks / total_urls, 2) if total_urls > 0 else 0
            },
            "popular_urls": popular_urls,
            "generated_at": datetime.utcnow().isoformat()
        }
        
        await self._cache_stats(cache_key, stats)
        
        return stats
    
    async def get_daily_stats(
        self,
        db: AsyncSession,
        short_code : Optional[str] = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Daily statics"""

        cache_key = f"{self.cache_prefix}daily_stats:{short_code or 'global'}:{days}"
        cached_stats = await self._get_cached_stats(cache_key)

        if cached_stats:
            return cached_stats
        
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days-1)

        if short_code:
            # For Specific URL
            click_query = text("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as clicks,
                    COUNT(DISTINCT ip_address) as unique_visitors
                FROM url_clicks 
                WHERE short_code = :short_code
                    AND DATE(created_at) BETWEEN :start_date AND :end_date
                GROUP BY DATE(created_at)
                ORDER BY date
            """)
            result = await db.execute(
                click_query,
                {"short_code": short_code, "start_date": start_date, "end_date": end_date}
            )
        else:
            # Global stats
            click_query = text("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as clicks,
                    COUNT(DISTINCT ip_address) as unique_visitors
                FROM url_clicks 
                WHERE DATE(created_at) BETWEEN :start_date AND :end_date
                GROUP BY DATE(created_at)
                ORDER BY date
            """)
            result = await db.execute(
                click_query,
                {"start_date": start_date, "end_date": end_date}
            )

        daily_data = {row.date: {"clicks": row.clicks, "unique_visitors": row.unique_visitors}
                      for row in result}
        
        daily_stats = []
        current_date = start_date

        while current_date <= end_date:
            data = daily_stats.get(current_date, {"clicks": 0, "unique_visitors": 0})

            daily_stats.append({
                "date": current_date.isoformat(),
                "clicks": data["clicks"],
                "unique_visitors": data["unique_visitors"]
            })

            current_date += timedelta(days=1)

        await self._cache_stats(cache_key, daily_stats)
        return daily_stats
    
    async def get_geographic_stats(
        self,
        db: AsyncSession,
        short_code: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        
        cache_key = f"{self.cache_prefix}geo_stats:{short_code or 'global'}:{limit}"
        cached_stats = await self._get_cached_stats(cache_key)

        if cached_stats:
            return cached_stats
        
        base_query = select(UrlClick.country, func.count().label('count'))

        if short_code:
            base_query = base_query.where(UrlClick.short_code == short_code)

        country_query = (
            base_query
            .where(UrlClick.country.is_not(None))
            .group_by(UrlClick.country)
            .order_by(desc('count'))
            .limit(limit)
        )

        country_result = await db.execute(country_query)
        countries = [
            {"country": row.country, "count": row.count}
            for row in country_result
        ]

        # City stats
        city_stats = {}
        if countries:
            top_countries = [c["country"] for c in countries[:5]]

            for country in top_countries:
                city_query = (
                    select(UrlClick.city, func.count().label('count'))
                    .where(
                        and_(
                            UrlClick.country == country,
                            UrlClick.city.is_not(None),
                            UrlClick.short_code == short_code if short_code else True
                        )
                    )
                    .group_by(UrlClick.city)
                    .order_by(desc('count'))
                    .limit(10)
                )
                
                city_result = await db.execute(city_query)
                city_stats[country] = [
                    {"city": row.city, "count": row.count}
                    for row in city_result
                ]

        geo_stats = {
            "countries": countries,
            "cities_by_country": city_stats,
            "total_countries": len(countries),
            "generated_at": datetime.utcnow().isoformat()
        }

        # Cache the value

        await self._cache_stats(cache_key, geo_stats)

        return geo_stats
    
    async def _get_cached_stats(self, cache_key: str) -> Optional[Dict[str, Any]]:
        redis = await get_redis()
        if redis:
            try:
                cached = await redis.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass
        return None
    
    async def _cache_stats(self, cache_key: str, stats: Dict[str, any]) -> None:
        redis = await get_redis()
        if redis:
            try:
                await redis.setex(
                    cache_key,
                    self.cache_ttl,
                    json.dumps(stats, default=str)
                )
            except Exception:
                pass
    
    def _extract_domain(self, url: str) -> str:
        if not url:
            return "direct"

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            if domain.startswith('www.'):
                domain = domain[4:]
            
            return domain or "unknown"
        except Exception:
            return "unknown"
    
    def _parse_user_agent(self, user_agent: str) -> Tuple[str, str, str]:
        if not user_agent:
            return "unknown", "unknown", "unknown"

        ua_lower = user_agent.lower()

        # Browser detection

        if "chrome" in ua_lower and "edg" not in ua_lower:
            browser = "Chrome"
        elif "firefox" in ua_lower:
            browser = "Firefox"
        elif "safari" in ua_lower and "chrome" not in ua_lower:
            browser = "Safari"
        elif "edg" in ua_lower:
            browser = "Edge"
        elif "opera" in ua_lower or "opr" in ua_lower:
            browser = "Opera"
        else:
            browser = "Other"

        # OS detection
        if "windows" in ua_lower:
            os = "Windows"
        elif "mac os" in ua_lower or "macos" in ua_lower:
            os = "macOS"
        elif "linux" in ua_lower:
            os = "Linux"
        elif "android" in ua_lower:
            os = "Android"
        elif "iphone" in ua_lower or "ipad" in ua_lower:
            os = "iOS"
        else:
            os = "Other"

        # Device detection
        if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
            device = "Mobile"
        elif "tablet" in ua_lower or "ipad" in ua_lower:
            device = "Tablet"
        else:
            device = "Desktop"
        
        return browser, os, device
    
    def _mask_ip(self, ip_address: Optional[str]) -> Optional[str]:
        if not ip_address:
            return None
        
        try:
            # For IPV4
            if "." in ip_address:
                parts = ip_address.split(".")
                if len(parts) == 4:
                    return f"{parts[0]}.{parts[1]}.{parts[2]}.xxx"
                
            # For IPV6
            if ":" in ip_address:
                parts = ip_address.split(":")
                if len(parts) >= 2:
                    return ":".join(parts[:-2]) + ":xxxx:xxxx"
                
            return "xxx.xxx.xxx.xxx"
        except Exception:
            return "xxx.xxx.xxx.xxx"

    
    async def invalidate_cache(self, pattern: str = None) -> int:
        """Clean Cache"""
        redis = await get_redis()
        if not redis:
            return 0
        
        try:
            if pattern:
                keys = await redis.keys(f"{self.cache_prefix}{pattern}*")
            else:
                keys = await redis.keys(f"{self.cache_prefix}*")
            if keys:
                return await redis.delete(*keys)
        except Exception:
            return 0
    
    async def get_cache_info(self) -> Dict[str, Any]:
        """Take Cache info"""
        redis = await get_redis()
        if not redis:
            return {"status": "disabled", "keys": 0}

        try:
            keys = await redis.keys(f"{self.cache_prefix}*")
            return {
                "status": "active",
                "total_keys": len(keys),
                "cache_ttl": self.cache_ttl,
                "sample_keys": keys[:10] if keys else []
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
