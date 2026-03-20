"""Redis cache layer for high-speed operations."""

from __future__ import annotations

import asyncio
import json
import pickle
from typing import Any, Optional
from datetime import timedelta

try:
    from redis import asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    try:
        import aioredis
        REDIS_AVAILABLE = True
    except ImportError:
        REDIS_AVAILABLE = False

class RedisCache:
    """Async Redis cache for deal validation and hot item lookups."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", db: int = 0):
        self.redis_url = redis_url
        self.db = db
        self._client: Optional[aioredis.Redis] = None
        self._available = REDIS_AVAILABLE
    
    async def connect(self) -> bool:
        """Connect to Redis. Returns True if successful."""
        if not self._available:
            return False
        try:
            self._client = await aioredis.from_url(
                self.redis_url,
                db=self.db,
                decode_responses=False,
                socket_connect_timeout=5,
                socket_keepalive=True,
            )
            await self._client.ping()
            return True
        except Exception as e:
            print(f"Redis connection failed: {e}")
            self._client = None
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self._client:
            return None
        try:
            data = await self._client.get(key)
            if data:
                return pickle.loads(data)
            return None
        except Exception:
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
    ) -> bool:
        """Set value in cache with optional TTL (seconds)."""
        if not self._client:
            return False
        try:
            serialized = pickle.dumps(value)
            if ttl:
                await self._client.setex(key, ttl, serialized)
            else:
                await self._client.set(key, serialized)
            return True
        except Exception:
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self._client:
            return False
        try:
            await self._client.delete(key)
            return True
        except Exception:
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self._client:
            return False
        try:
            return await self._client.exists(key) > 0
        except Exception:
            return False
    
    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None

# Global cache instance
_cache_instance: Optional[RedisCache] = None

async def get_cache() -> RedisCache:
    """Get or create global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache()
        await _cache_instance.connect()
    return _cache_instance
