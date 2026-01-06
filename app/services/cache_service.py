"""
Cache Service

Handles Redis caching for API responses, user data, and render results.
"""

import hashlib
import json
from collections.abc import Callable
from typing import Any, TypeVar

from redis.asyncio import Redis

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
    PREFIX_PLAN = "plan"

    # Default TTLs (in seconds)
    TTL_API_KEY = 900  # 15 minutes
    TTL_USER_PLAN = 21600  # 6 hours
    TTL_RENDER = 3600  # 1 hour (or user-specified)
    TTL_SESSION = 86400  # 24 hours
    TTL_PLAN = 86400  # 24 hours

    def __init__(self, redis: Redis | None = None):
        self._redis = redis

    # =========================================================================
    # Generic Cache Operations
    # =========================================================================

    async def get(self, key: str) -> str | None:
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
        ttl: int | None = None,
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

    async def get_json(self, key: str) -> Any | None:
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
        ttl: int | None = None,
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

    async def get_api_key_cache(self, key_hash: str) -> dict | None:
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

    async def get_user_plan_cache(self, user_id: str) -> dict | None:
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
    ) -> dict | None:
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
        ttl: int | None = None,
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
    # Screenshot Image Cache (Binary)
    # =========================================================================
    
    PREFIX_SCREENSHOT = "screenshot"
    TTL_SCREENSHOT = 3600  # 1 hour default
    
    def _screenshot_cache_key(self, url: str, options: dict) -> str:
        """Generate cache key for screenshot image."""
        # Only include relevant options for cache key
        cache_options = {
            "width": options.get("width", 1920),
            "height": options.get("height", 1080),
            "format": options.get("format", "jpeg"),
            "quality": options.get("quality", 80),
            "full_page": options.get("full_page", False),
            "device_scale_factor": options.get("device_scale_factor", 1),
        }
        options_str = json.dumps(cache_options, sort_keys=True)
        combined = f"{url}:{options_str}"
        hash_value = hashlib.sha256(combined.encode()).hexdigest()[:24]
        return f"{self.PREFIX_SCREENSHOT}:{hash_value}"
    
    async def get_screenshot_cache(
        self,
        url: str,
        options: dict,
    ) -> tuple[bytes, dict] | None:
        """
        Get cached screenshot image.

        Args:
            url: Target URL
            options: Screenshot options

        Returns:
            Tuple of (image_bytes, metadata) or None
        """
        cache_key = self._screenshot_cache_key(url, options)
        
        async with redis_context("cache") as redis:
            # Get both image and metadata
            image_key = f"{cache_key}:img"
            meta_key = f"{cache_key}:meta"
            
            image_bytes = await redis.get(image_key)
            if not image_bytes:
                return None
            
            meta_str = await redis.get(meta_key)
            metadata = json.loads(meta_str) if meta_str else {}
            
            logger.info("Screenshot cache hit", url=url[:50])
            return image_bytes, metadata
    
    async def set_screenshot_cache(
        self,
        url: str,
        options: dict,
        image_bytes: bytes,
        metadata: dict,
        ttl: int | None = None,
    ) -> bool:
        """
        Cache screenshot image.

        Args:
            url: Target URL
            options: Screenshot options
            image_bytes: Screenshot image bytes
            metadata: Screenshot metadata
            ttl: Cache TTL (optional)

        Returns:
            True if cached
        """
        cache_key = self._screenshot_cache_key(url, options)
        ttl = ttl or self.TTL_SCREENSHOT
        
        async with redis_context("cache") as redis:
            image_key = f"{cache_key}:img"
            meta_key = f"{cache_key}:meta"
            
            # Use pipeline for atomic operations
            pipe = redis.pipeline()
            pipe.setex(image_key, ttl, image_bytes)
            pipe.setex(meta_key, ttl, json.dumps(metadata, default=str))
            await pipe.execute()
            
            logger.info(
                "Screenshot cached", 
                url=url[:50], 
                size=len(image_bytes),
                ttl=ttl,
            )
            return True

    # =========================================================================
    # Session Cache
    # =========================================================================

    def _session_cache_key(self, session_id: str) -> str:
        """Generate cache key for session."""
        return f"{self.PREFIX_SESSION}:{session_id}"

    async def get_session(self, session_id: str) -> dict | None:
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
        ttl: int | None = None,
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

    # =========================================================================
    # Plan Cache
    # =========================================================================

    def _plan_cache_key(self, plan_name: str) -> str:
        """Generate cache key for plan."""
        return f"{self.PREFIX_PLAN}:{plan_name}"

    async def get_plan_cache(self, plan_name: str) -> dict | None:
        """
        Get cached plan data.

        Args:
            plan_name: Plan name

        Returns:
            Cached plan data or None
        """
        cache_key = self._plan_cache_key(plan_name)
        return await self.get_json(cache_key)

    async def set_plan_cache(
        self,
        plan_name: str,
        data: dict,
    ) -> bool:
        """
        Cache plan data.

        Args:
            plan_name: Plan name
            data: Plan data to cache

        Returns:
            True if cached
        """
        cache_key = self._plan_cache_key(plan_name)
        return await self.set(cache_key, data, self.TTL_PLAN)

    async def invalidate_plan_cache(self, plan_name: str) -> bool:
        """
        Invalidate plan cache.

        Args:
            plan_name: Plan name

        Returns:
            True if invalidated
        """
        cache_key = self._plan_cache_key(plan_name)
        return await self.delete(cache_key)

    # =========================================================================
    # Demo Activity Tracking
    # =========================================================================

    PREFIX_DEMO_CAPTURE = "demo:capture"
    PREFIX_DEMO_STATS = "demo:stats"

    async def log_demo_capture(
        self,
        ip: str,
        url: str,
        render_time_ms: float,
        metadata: dict,
    ) -> bool:
        """
        Log a demo capture event.

        Args:
            ip: Client IP address
            url: Captured URL
            render_time_ms: Render time in milliseconds
            metadata: Capture metadata

        Returns:
            True if logged successfully
        """
        import time
        
        timestamp = int(time.time())
        
        capture_data = {
            "ip": ip,
            "url": url,
            "timestamp": timestamp,
            "render_time_ms": int(render_time_ms),
            "width": metadata.get("width"),
            "height": metadata.get("height"),
            "format": metadata.get("format"),
        }

        async with redis_context("cache") as redis:
            pipe = redis.pipeline()
            
            # Store in sorted set with timestamp as score (for recent captures)
            capture_key = f"{self.PREFIX_DEMO_CAPTURE}:recent"
            pipe.zadd(capture_key, {json.dumps(capture_data): timestamp})
            
            # Keep only last 100 captures
            pipe.zremrangebyrank(capture_key, 0, -101)
            
            # Set expiry to 7 days
            pipe.expire(capture_key, 604800)
            
            # Increment daily counter
            from datetime import datetime
            today = datetime.utcnow().strftime("%Y%m%d")
            daily_key = f"{self.PREFIX_DEMO_STATS}:daily:{today}"
            pipe.incr(daily_key)
            pipe.expire(daily_key, 604800)  # Keep for 7 days
            
            # Increment weekly counter
            week = datetime.utcnow().strftime("%Y-W%U")
            weekly_key = f"{self.PREFIX_DEMO_STATS}:weekly:{week}"
            pipe.incr(weekly_key)
            pipe.expire(weekly_key, 2592000)  # Keep for 30 days
            
            # Increment all-time counter
            all_time_key = f"{self.PREFIX_DEMO_STATS}:total"
            pipe.incr(all_time_key)
            
            # Track URL popularity (top URLs)
            url_key = f"{self.PREFIX_DEMO_STATS}:urls"
            pipe.zincrby(url_key, 1, url)
            pipe.expire(url_key, 2592000)  # Keep for 30 days
            
            await pipe.execute()
            
            logger.info(
                "Demo capture logged",
                ip=ip,
                url=url[:50],
                render_time_ms=int(render_time_ms),
            )
            return True

    async def get_demo_stats(self) -> dict:
        """
        Get demo activity statistics.

        Returns:
            Dict with demo usage stats
        """
        from datetime import datetime
        
        today = datetime.utcnow().strftime("%Y%m%d")
        week = datetime.utcnow().strftime("%Y-W%U")
        
        async with redis_context("cache") as redis:
            pipe = redis.pipeline()
            
            # Get counters
            pipe.get(f"{self.PREFIX_DEMO_STATS}:daily:{today}")
            pipe.get(f"{self.PREFIX_DEMO_STATS}:weekly:{week}")
            pipe.get(f"{self.PREFIX_DEMO_STATS}:total")
            
            # Get top URLs (top 10)
            pipe.zrevrange(
                f"{self.PREFIX_DEMO_STATS}:urls",
                0, 9,
                withscores=True
            )
            
            results = await pipe.execute()
            
            return {
                "total_today": int(results[0]) if results[0] else 0,
                "total_week": int(results[1]) if results[1] else 0,
                "total_all_time": int(results[2]) if results[2] else 0,
                "top_urls": [
                    {"url": url.decode() if isinstance(url, bytes) else url, "count": int(score)}
                    for url, score in (results[3] or [])
                ],
            }

    async def get_recent_demo_captures(self, limit: int = 20) -> list[dict]:
        """
        Get recent demo captures.

        Args:
            limit: Maximum number of captures to return

        Returns:
            List of recent captures
        """
        async with redis_context("cache") as redis:
            # Get recent captures from sorted set (newest first)
            captures = await redis.zrevrange(
                f"{self.PREFIX_DEMO_CAPTURE}:recent",
                0, limit - 1
            )
            
            result = []
            for capture_json in captures:
                try:
                    data = json.loads(capture_json)
                    result.append(data)
                except json.JSONDecodeError:
                    continue
            
            return result


# Import asyncio for the get_or_set method
import asyncio

# Global cache service instance
cache_service = CacheService()

