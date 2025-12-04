"""
Cache Service

Handles Redis caching for API responses, user data, and render results.
"""

import hashlib
import json
from typing import Any, Optional, TypeVar, Callable
from datetime import datetime, timezone

from redis.asyncio import Redis

from app.core.config import settings
from app.core.redis import redis_context
from app.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CacheService:
    """Service for Redis caching operations."""

    # Cache key prefixes
    PREFIX_API_KEY = "auth:apikey"
    PREFIX_USER_PLAN = "user:plan"
    PREFIX_RENDER = "render"
    PREFIX_USAGE = "usage:monthly"
    PREFIX_SESSION = "session"

    # Default TTLs (in seconds)
    TTL_API_KEY = 300  # 5 minutes
    TTL_USER_PLAN = 3600  # 1 hour
    TTL_RENDER = 3600  # 1 hour (or user-specified)
    TTL_SESSION = 86400  # 24 hours

    def __init__(self, redis: Optional[Redis] = None):
        self._redis = redis

    # =========================================================================
    # Generic Cache Operations
    # =========================================================================

    async def get(self, key: str) -> Optional[str]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        async with redis_context("cache") as redis:
            value = await redis.get(key)
            if value:
                logger.debug("Cache hit", key=key)
            return value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized if not string)
            ttl: Time to live in seconds

        Returns:
            True if set successfully
        """
        if ttl is None:
            ttl = 3600  # Default 1 hour

        # Serialize if not string
        if not isinstance(value, str):
            value = json.dumps(value, default=str)

        async with redis_context("cache") as redis:
            result = await redis.setex(key, ttl, value)
            logger.debug("Cache set", key=key, ttl=ttl)
            return result

    async def delete(self, key: str) -> bool:
        """
        Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        async with redis_context("cache") as redis:
            result = await redis.delete(key)
            logger.debug("Cache delete", key=key, deleted=bool(result))
            return bool(result)

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if exists
        """
        async with redis_context("cache") as redis:
            return bool(await redis.exists(key))

    async def get_json(self, key: str) -> Optional[Any]:
        """
        Get JSON value from cache.

        Args:
            key: Cache key

        Returns:
            Deserialized JSON value or None
        """
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def get_or_set(
        self,
        key: str,
        callback: Callable[[], Any],
        ttl: Optional[int] = None,
    ) -> Any:
        """
        Get value from cache or compute and store it.

        Args:
            key: Cache key
            callback: Function to compute value if not cached
            ttl: Time to live in seconds

        Returns:
            Cached or computed value
        """
        value = await self.get_json(key)
        if value is not None:
            return value

        # Compute value
        value = callback()
        if asyncio.iscoroutine(value):
            value = await value

        # Store in cache
        await self.set(key, value, ttl)
        return value

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching pattern.

        Args:
            pattern: Redis key pattern (e.g., "user:*:plan")

        Returns:
            Number of keys deleted
        """
        async with redis_context("cache") as redis:
            keys = []
            async for key in redis.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                deleted = await redis.delete(*keys)
                logger.info(
                    "Cache invalidated",
                    pattern=pattern,
                    count=deleted,
                )
                return deleted
        return 0

    # =========================================================================
    # API Key Cache
    # =========================================================================

    def _api_key_cache_key(self, key_hash: str) -> str:
        """Generate cache key for API key."""
        return f"{self.PREFIX_API_KEY}:{key_hash}"

    async def get_api_key_cache(self, key_hash: str) -> Optional[dict]:
        """
        Get cached API key data.

        Args:
            key_hash: SHA256 hash of API key

        Returns:
            Cached API key data or None
        """
        cache_key = self._api_key_cache_key(key_hash)
        return await self.get_json(cache_key)

    async def set_api_key_cache(
        self,
        key_hash: str,
        data: dict,
    ) -> bool:
        """
        Cache API key data.

        Args:
            key_hash: SHA256 hash of API key
            data: API key data to cache

        Returns:
            True if cached
        """
        cache_key = self._api_key_cache_key(key_hash)
        return await self.set(cache_key, data, self.TTL_API_KEY)

    async def invalidate_api_key_cache(self, key_hash: str) -> bool:
        """
        Invalidate API key cache.

        Args:
            key_hash: SHA256 hash of API key

        Returns:
            True if invalidated
        """
        cache_key = self._api_key_cache_key(key_hash)
        return await self.delete(cache_key)

    # =========================================================================
    # User Plan Cache
    # =========================================================================

    def _user_plan_cache_key(self, user_id: str) -> str:
        """Generate cache key for user plan."""
        return f"{self.PREFIX_USER_PLAN}:{user_id}"

    async def get_user_plan_cache(self, user_id: str) -> Optional[dict]:
        """
        Get cached user plan data.

        Args:
            user_id: User UUID string

        Returns:
            Cached plan data or None
        """
        cache_key = self._user_plan_cache_key(user_id)
        return await self.get_json(cache_key)

    async def set_user_plan_cache(
        self,
        user_id: str,
        data: dict,
    ) -> bool:
        """
        Cache user plan data.

        Args:
            user_id: User UUID string
            data: Plan data to cache

        Returns:
            True if cached
        """
        cache_key = self._user_plan_cache_key(user_id)
        return await self.set(cache_key, data, self.TTL_USER_PLAN)

    async def invalidate_user_plan_cache(self, user_id: str) -> bool:
        """
        Invalidate user plan cache.

        Args:
            user_id: User UUID string

        Returns:
            True if invalidated
        """
        cache_key = self._user_plan_cache_key(user_id)
        return await self.delete(cache_key)

    # =========================================================================
    # Render Cache
    # =========================================================================

    def _render_cache_key(self, url: str, options: dict) -> str:
        """Generate cache key for render result."""
        # Create deterministic hash of URL + options
        options_str = json.dumps(options, sort_keys=True)
        combined = f"{url}:{options_str}"
        hash_value = hashlib.sha256(combined.encode()).hexdigest()[:16]
        return f"{self.PREFIX_RENDER}:{hash_value}"

    async def get_render_cache(
        self,
        url: str,
        options: dict,
    ) -> Optional[dict]:
        """
        Get cached render result.

        Args:
            url: Target URL
            options: Render options

        Returns:
            Cached render data (s3_key, etc.) or None
        """
        cache_key = self._render_cache_key(url, options)
        return await self.get_json(cache_key)

    async def set_render_cache(
        self,
        url: str,
        options: dict,
        data: dict,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache render result.

        Args:
            url: Target URL
            options: Render options
            data: Render result data
            ttl: Cache TTL (optional)

        Returns:
            True if cached
        """
        cache_key = self._render_cache_key(url, options)
        return await self.set(cache_key, data, ttl or self.TTL_RENDER)

    # =========================================================================
    # Session Cache
    # =========================================================================

    def _session_cache_key(self, session_id: str) -> str:
        """Generate cache key for session."""
        return f"{self.PREFIX_SESSION}:{session_id}"

    async def get_session(self, session_id: str) -> Optional[dict]:
        """
        Get cached session data.

        Args:
            session_id: Session ID

        Returns:
            Session data or None
        """
        cache_key = self._session_cache_key(session_id)
        return await self.get_json(cache_key)

    async def set_session(
        self,
        session_id: str,
        data: dict,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache session data.

        Args:
            session_id: Session ID
            data: Session data
            ttl: Session TTL

        Returns:
            True if cached
        """
        cache_key = self._session_cache_key(session_id)
        return await self.set(cache_key, data, ttl or self.TTL_SESSION)

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete session from cache.

        Args:
            session_id: Session ID

        Returns:
            True if deleted
        """
        cache_key = self._session_cache_key(session_id)
        return await self.delete(cache_key)


# Import asyncio for the get_or_set method
import asyncio

# Global cache service instance
cache_service = CacheService()

