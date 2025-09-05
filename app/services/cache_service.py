import json
import asyncio
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from aioredis import Redis

from app.core.database import get_redis
from app.core.config import settings

class CacheService:
    """Redis cache operations abstraction layer."""

    def __init__(self):
        self.default_ttl = settings.cache_ttl
        self.key_prefix = "url_shortener:"
        self.batch_size = 100

    async def get_redis(self) -> Optional[Redis]:
        return await get_redis()
    
    # Basic operations
    async def get(self, key: str, default: Any = None) -> Any:
        """Get one key value."""
        redis = await self.get_redis()
        if not redis:
            return default
        
        try:
            value = await redis.get(self._make_key(key))
            if value is None:
                return default
            
            # JSON deserialize
            return json.loads(value)
        except Exception:
            return default
        
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        redis = await self.get_redis()
        if not redis:
            return False
        
        try:
            ttl = ttl or self.default_ttl
            serialized_value = json.dumps(value, default=str)

            await redis.setex(
                self._make_key(key),
                ttl,
                serialized_value
            )
            return True
        except Exception:
            return False
        
    async def delete(self, key: str) -> bool:
        redis = await self.get_redis()
        if not redis:
            return False
        
        try:
            result = await redis.delete(self._make_key(key))
            return result > 0
        except Exception:
            return False
        
    async def exists(self, key: str) -> bool:
        redis = await self.get_redis()
        if not redis:
            return False
        
        try:
            result = await redis.exists(self._make_key(key))
            return result > 0
        except Exception:
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Update the key's TTL."""
        redis = await self.get_redis()
        if not redis:
            return False
        
        try:
            result = await redis.expire(self._make_key(key), ttl)
            return result
        except Exception:
            return False
        
    async def ttl(self, key: str) -> int:
        """Get the remaining TTL of the key."""
        redis = await self.get_redis()
        if not redis:
            return -1
        
        try:
            result = await redis.ttl(self._make_key(key))
            return result
        except Exception:
            return -1
        
    async def mget(self, keys: List[str]) -> Dict[str, Any]:
        redis = await self.get_redis()
        if not redis:
            return {}

        if not keys:
            return {}

        try:
            prefixed_keys = [self._make_key(key) for key in keys]
            values = await redis.mget(*prefixed_keys)

            result = {}

            for i, key in enumerate(keys):
                if values[i] is not None:
                    try:
                        result[key] = json.loads(values[i])
                    except Exception:
                        result[key] = None
                else: 
                    result[key] = None
            
            return result
        
        except Exception:
            return {}
        
    async def mset(
        self, 
        mapping: Dict[str, Any], 
        ttl: Optional[int] = None
    ) -> bool:
        redis = await self.get_redis()
        if not redis:
            return False
        
        if not mapping:
            return True
        
        try:
            ttl = ttl or self.default_ttl
            
            # Use Pipeline
            pipe = redis.pipeline()
            
            for key, value in mapping.items():
                serialized_value = json.dumps(value, default=str)
                pipe.setex(self._make_key(key), ttl, serialized_value)
            
            await pipe.execute()
            return True
        except Exception:
            return False
    
    async def mdelete(self, keys: List[str]) -> int:
        """Delete Multiple key"""
        redis = await self.get_redis()
        if not redis:
            return 0
        
        if not keys:
            return 0
        
        try:
            prefixed_keys = [self._make_key(key) for key in keys]
            result = await redis.delete(*prefixed_keys)
            return result
        except Exception:
            return 0
    
    # Pattern operations
    async def keys(self, pattern: str = "*") -> List[str]:
        redis = await self.get_redis()
        if not redis:
            return []
        
        try:
            keys = await redis.keys(self._make_key(pattern))
            return [key.replace(self.key_prefix, "") for key in keys]
        except Exception:
            return []
        
    async def delete_pattern(self, pattern: str) -> int:
        redis = await self.get_redis()
        if not redis:
            return 0
        
        try:
            keys = await redis.keys(self._make_key(pattern))
            if keys:
                return await redis.delete(*keys)
            return 0
        except Exception:
            return 0
        
    # Hash operations
    async def hget(self, hash_key: str, field: str, default: Any = None) -> Any:
        redis = await self.get_redis()
        if not redis:
            return default
        
        try:
            value = await redis.hget(self._make_key(hash_key), field)
            if value is None:
                return default
            return json.loads(value)
        except Exception:
            return default
        
    async def hset(
        self, 
        hash_key: str, 
        field: str, 
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        redis = await self.get_redis()
        if not redis:
            return False
        
        try:
            serialized_value = json.dumps(value, default=str)
            await redis.hset(self._make_key(hash_key), field, serialized_value)
            
            # TTL
            if ttl:
                await redis.expire(self._make_key(hash_key), ttl)
            
            return True
        except Exception:
            return False
        
    async def hmget(self, hash_key: str, fields: List[str]) -> Dict[str, Any]:
        """Take multiple hash field"""
        redis = await self.get_redis()
        if not redis:
            return {}
        
        if not fields:
            return {}
        
        try:
            values = await redis.hmget(self._make_key(hash_key), *fields)
            
            result = {}
            for i, field in enumerate(fields):
                if values[i] is not None:
                    try:
                        result[field] = json.loads(values[i])
                    except Exception:
                        result[field] = None
                else:
                    result[field] = None
            
            return result
        except Exception:
            return {}
    
    async def hmset(
        self, 
        hash_key: str, 
        mapping: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        redis = await self.get_redis()
        if not redis:
            return False
        
        if not mapping:
            return True
        
        try:
            # Serialize all values
            serialized_mapping = {
                field: json.dumps(value, default=str) 
                for field, value in mapping.items()
            }
            
            await redis.hset(self._make_key(hash_key), mapping=serialized_mapping)
            
            # TTL
            if ttl:
                await redis.expire(self._make_key(hash_key), ttl)
            
            return True
        except Exception:
            return False
    
    async def hdel(self, hash_key: str, fields: List[str]) -> int:
        redis = await self.get_redis()
        if not redis:
            return 0
        
        if not fields:
            return 0
        
        try:
            result = await redis.hdel(self._make_key(hash_key), *fields)
            return result
        except Exception:
            return 0
    
    async def hgetall(self, hash_key: str) -> Dict[str, Any]:
        redis = await self.get_redis()
        if not redis:
            return {}
        
        try:
            result = await redis.hgetall(self._make_key(hash_key))
            
            # Deserialize all values
            deserialized = {}
            for field, value in result.items():
                try:
                    deserialized[field] = json.loads(value)
                except Exception:
                    deserialized[field] = value
            
            return deserialized
        except Exception:
            return {}
        
    # Counter operations for analytics
    async def incr(self, key: str, amount: int = 1) -> int:
        redis = await self.get_redis()
        if not redis:
            return 0
        
        try:
            result = await redis.incrby(self._make_key(key), amount)
            return result
        except Exception:
            return 0
        
    async def decr(self, key: str, amount: int = 1) -> int:
        redis = await self.get_redis()
        if not redis:
            return 0
        
        try:
            result = await redis.decrby(self._make_key(key), amount)
            return result
        except Exception:
            return 0
    
    # List operations for click tracking
    async def lpush(self, key: str, *values: Any) -> int:
        redis = await self.get_redis()
        if not redis:
            return 0
        
        try:
            serialized_values = [json.dumps(value, default=str) for value in values]
            result = await redis.lpush(self._make_key(key), *serialized_values)
            return result
        except Exception:
            return 0
    
    async def rpush(self, key: str, *values: Any) -> int:
        redis = await self.get_redis()
        if not redis:
            return 0
        
        try:
            serialized_values = [json.dumps(value, default=str) for value in values]
            result = await redis.rpush(self._make_key(key), *serialized_values)
            return result
        except Exception:
            return 0
    
    async def lrange(self, key: str, start: int = 0, end: int = -1) -> List[Any]:
        redis = await self.get_redis()
        if not redis:
            return []
        
        try:
            values = await redis.lrange(self._make_key(key), start, end)
            return [json.loads(value) for value in values]
        except Exception:
            return []
    
    async def ltrim(self, key: str, start: int, end: int) -> bool:
        redis = await self.get_redis()
        if not redis:
            return False
        
        try:
            await redis.ltrim(self._make_key(key), start, end)
            return True
        except Exception:
            return False
        
    # Utility methods
    async def flush_all(self) -> bool:
        """Clear all cache!"""
        redis = await self.get_redis()
        if not redis:
            return False
        
        try:
            keys = await redis.keys(f"{self.key_prefix}*")
            if keys:
                await redis.delete(*keys)
            return True
        except Exception:
            return False
        
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        redis = await self.get_redis()
        if not redis:
            return {"status": "disconnected"}
        
        try:
            info = await redis.info()
            keys = await redis.keys(f"{self.key_prefix}*")
            
            return {
                "status": "connected",
                "total_keys": len(keys),
                "used_memory": info.get("used_memory_human", "N/A"),
                "connected_clients": info.get("connected_clients", 0),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                ),
                "uptime": info.get("uptime_in_seconds", 0)
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _make_key(self, key: str) -> str:
        """Add prefix to key."""
        return f"{self.key_prefix}{key}"
    
    def _calculate_hit_rate(self, hits: int, misses: int) -> float:
        """Calculate Cache hit rate."""
        total = hits + misses
        if total == 0:
            return 0.0
        return round((hits / total) * 100, 2)
    
    # Context managers
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # Cleanup if needed
        pass


# Global cache service instance
cache_service = CacheService()