"""
Redis connection management

Thread-safe connection pool initialization.
"""

import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

# Connection pools for different purposes
_main_pool: ConnectionPool | None = None
_cache_pool: ConnectionPool | None = None
_rate_limit_pool: ConnectionPool | None = None

# Thread-safe initialization lock
_init_lock = threading.Lock()
_initialized = False


def get_redis_url(db: int = 0) -> str:
    """Get Redis URL with specific database number."""
    # Upstash Redis doesn't support database numbers, use the same URL for all
    # For other Redis instances, append database number
    if "upstash.io" in settings.REDIS_URL or "rediss://" in settings.REDIS_URL:
        # Upstash Redis - no database numbers
        return settings.REDIS_URL
    # Standard Redis - append database number
    base_url = settings.REDIS_URL.rsplit("/", 1)[0]
    return f"{base_url}/{db}"


async def init_redis_pools() -> None:
    """
    Initialize Redis connection pools.

    Thread-safe - can be called from multiple threads/coroutines.
    """
    global _main_pool, _cache_pool, _rate_limit_pool, _initialized

    # Quick check without lock
    if _initialized:
        return

    with _init_lock:
        # Double-check after acquiring lock
        if _initialized:
            return

        _main_pool = ConnectionPool.from_url(
            get_redis_url(0),
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
        )

        _cache_pool = ConnectionPool.from_url(
            get_redis_url(settings.REDIS_CACHE_DB),
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
        )

        _rate_limit_pool = ConnectionPool.from_url(
            get_redis_url(settings.REDIS_RATE_LIMIT_DB),
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
        )

        _initialized = True


async def close_redis_pools() -> None:
    """Close Redis connection pools."""
    global _main_pool, _cache_pool, _rate_limit_pool, _initialized

    with _init_lock:
        if _main_pool:
            await _main_pool.disconnect()
            _main_pool = None

        if _cache_pool:
            await _cache_pool.disconnect()
            _cache_pool = None

        if _rate_limit_pool:
            await _rate_limit_pool.disconnect()
            _rate_limit_pool = None

        _initialized = False


async def get_redis() -> AsyncGenerator[Redis, None]:
    """
    Dependency for getting Redis connection.

    Yields:
        Redis: Redis client
    """
    if not _initialized:
        await init_redis_pools()

    client = Redis(connection_pool=_main_pool)
    try:
        yield client
    finally:
        await client.aclose()


async def get_cache_redis() -> AsyncGenerator[Redis, None]:
    """
    Dependency for getting Redis cache connection.

    Yields:
        Redis: Redis client for caching
    """
    if not _initialized:
        await init_redis_pools()

    client = Redis(connection_pool=_cache_pool)
    try:
        yield client
    finally:
        await client.aclose()


async def get_rate_limit_redis() -> AsyncGenerator[Redis, None]:
    """
    Dependency for getting Redis rate limit connection.

    Yields:
        Redis: Redis client for rate limiting
    """
    if not _initialized:
        await init_redis_pools()

    client = Redis(connection_pool=_rate_limit_pool)
    try:
        yield client
    finally:
        await client.aclose()


@asynccontextmanager
async def redis_context(pool: str = "main") -> AsyncGenerator[Redis, None]:
    """
    Context manager for getting Redis connection.

    Args:
        pool: Which pool to use ('main', 'cache', 'rate_limit')

    Yields:
        Redis: Redis client
    """
    if not _initialized:
        await init_redis_pools()

    pool_map = {
        "main": _main_pool,
        "cache": _cache_pool,
        "rate_limit": _rate_limit_pool,
    }

    selected_pool = pool_map.get(pool, _main_pool)
    client = Redis(connection_pool=selected_pool)

    try:
        yield client
    finally:
        await client.aclose()


class RedisClient:
    """
    Redis client wrapper with common operations.
    """

    def __init__(self, redis_client: Redis):
        self._redis = redis_client

    async def get(self, key: str) -> str | None:
        """Get value by key."""
        return await self._redis.get(key)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """Set value with optional TTL."""
        if ttl:
            return await self._redis.setex(key, ttl, value)
        return await self._redis.set(key, value)

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys."""
        return await self._redis.delete(*keys)

    async def exists(self, *keys: str) -> int:
        """Check if keys exist."""
        return await self._redis.exists(*keys)

    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment key value."""
        return await self._redis.incrby(key, amount)

    async def expire(self, key: str, seconds: int) -> bool:
        """Set key expiration."""
        return await self._redis.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        """Get remaining TTL for key."""
        return await self._redis.ttl(key)

    async def hget(self, name: str, key: str) -> str | None:
        """Get hash field value."""
        return await self._redis.hget(name, key)

    async def hset(self, name: str, key: str, value: Any) -> int:
        """Set hash field value."""
        return await self._redis.hset(name, key, value)

    async def hmset(self, name: str, mapping: dict[str, Any]) -> bool:
        """Set multiple hash fields."""
        return await self._redis.hset(name, mapping=mapping)

    async def hgetall(self, name: str) -> dict[str, str]:
        """Get all hash fields."""
        return await self._redis.hgetall(name)

    async def hdel(self, name: str, *keys: str) -> int:
        """Delete hash fields."""
        return await self._redis.hdel(name, *keys)

    async def lpush(self, name: str, *values: Any) -> int:
        """Push values to list head."""
        return await self._redis.lpush(name, *values)

    async def rpush(self, name: str, *values: Any) -> int:
        """Push values to list tail."""
        return await self._redis.rpush(name, *values)

    async def lrange(self, name: str, start: int, end: int) -> list[str]:
        """Get list range."""
        return await self._redis.lrange(name, start, end)

    async def pipeline(self) -> Any:
        """Get Redis pipeline for batch operations."""
        return self._redis.pipeline()

    async def ping(self) -> bool:
        """Check Redis connection."""
        return await self._redis.ping()

    async def eval(
        self,
        script: str,
        numkeys: int,
        *keys_and_args,
    ) -> Any:
        """Execute Lua script."""
        return await self._redis.eval(script, numkeys, *keys_and_args)
