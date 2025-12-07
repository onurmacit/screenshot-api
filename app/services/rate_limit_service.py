"""
Rate Limit Service

Handles multi-tier rate limiting using Redis sliding window counters.
Uses atomic Lua scripts to prevent race conditions.
"""

import time
import uuid
from typing import Any, Optional
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import settings
from app.core.redis import redis_context
from app.utils.exceptions import RateLimitError
from app.utils.logger import get_logger

logger = get_logger(__name__)


# Rate limit configurations by plan tier
RATE_LIMITS = {
    "free": {
        "per_minute": 10,
        "per_hour": 100,
        "per_day": 200,
        "per_month": 100,
        "burst": 5,
    },
    "starter": {
        "per_minute": 30,
        "per_hour": 500,
        "per_day": 2000,
        "per_month": 5000,
        "burst": 10,
    },
    "pro": {
        "per_minute": 100,
        "per_hour": 2000,
        "per_day": 10000,
        "per_month": 25000,
        "burst": 50,
    },
    "business": {
        "per_minute": 500,
        "per_hour": 10000,
        "per_day": 50000,
        "per_month": 100000,
        "burst": 200,
    },
}

# Time windows in seconds
WINDOWS = {
    "minute": 60,
    "hour": 3600,
    "day": 86400,
    "month": 2592000,  # 30 days
}


# Lua script for atomic rate limit check
# Returns: {allowed (0/1), remaining, current_count}
RATE_LIMIT_LUA_SCRIPT = """
local key = KEYS[1]
local window_start = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local current_time = tonumber(ARGV[3])
local request_id = ARGV[4]
local window_size = tonumber(ARGV[5])

-- Remove expired entries
redis.call('ZREMRANGEBYSCORE', key, 0, window_start)

-- Get current count
local count = redis.call('ZCARD', key)

-- Check if under limit
if count < limit then
    -- Add new request with unique score
    redis.call('ZADD', key, current_time, current_time .. ':' .. request_id)
    -- Set expiry
    redis.call('EXPIRE', key, window_size + 1)
    return {1, limit - count - 1, count + 1}  -- allowed, remaining, new count
else
    return {0, 0, count}  -- not allowed, remaining=0, count
end
"""


class RateLimitResult:
    """Result of rate limit check."""

    def __init__(
        self,
        allowed: bool,
        remaining: int,
        limit: int,
        reset_at: int,
        window: str,
    ):
        self.allowed = allowed
        self.remaining = remaining
        self.limit = limit
        self.reset_at = reset_at
        self.window = window

    @property
    def retry_after(self) -> int:
        """Seconds until rate limit resets."""
        return max(0, self.reset_at - int(time.time()))

    def to_headers(self) -> dict[str, str]:
        """Convert to HTTP response headers."""
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.reset_at),
        }


class RateLimitService:
    """Service for rate limiting operations."""

    def __init__(self, redis: Optional[Redis] = None):
        self._redis = redis

    async def check_rate_limit(
        self,
        user_id: UUID,
        plan_name: str,
        api_key_id: Optional[UUID] = None,
        override: Optional[dict[str, int]] = None,
    ) -> RateLimitResult:
        """
        Check if request is within rate limits.

        Uses atomic Lua script to prevent race conditions.

        Args:
            user_id: User UUID
            plan_name: Plan name for limits
            api_key_id: API key UUID (optional)
            override: Custom rate limit override (optional)

        Returns:
            RateLimitResult with allowed status and remaining quota

        Raises:
            RateLimitError: If rate limit is exceeded
        """
        if not settings.RATE_LIMIT_ENABLED:
            return RateLimitResult(
                allowed=True,
                remaining=999999,
                limit=999999,
                reset_at=0,
                window="disabled",
            )

        # Get limits for plan
        limits = override or RATE_LIMITS.get(plan_name, RATE_LIMITS["free"])

        async with redis_context("rate_limit") as redis:
            # Check each window
            results = await self._check_all_windows(
                redis,
                str(user_id),
                limits,
            )

            # Find the most restrictive limit
            most_restrictive = None
            for result in results:
                if not result.allowed:
                    if most_restrictive is None or result.remaining < most_restrictive.remaining:
                        most_restrictive = result
                elif most_restrictive is None or result.remaining < most_restrictive.remaining:
                    most_restrictive = result

            if most_restrictive and not most_restrictive.allowed:
                logger.warning(
                    "Rate limit exceeded",
                    user_id=str(user_id),
                    window=most_restrictive.window,
                    limit=most_restrictive.limit,
                )
                raise RateLimitError(
                    message=f"Rate limit exceeded for {most_restrictive.window} window",
                    retry_after=most_restrictive.retry_after,
                    limit=most_restrictive.limit,
                    remaining=0,
                )

            return most_restrictive or RateLimitResult(
                allowed=True,
                remaining=limits.get("per_minute", 10),
                limit=limits.get("per_minute", 10),
                reset_at=int(time.time()) + 60,
                window="minute",
            )

    async def _check_all_windows(
        self,
        redis: Redis,
        user_id: str,
        limits: dict[str, int],
    ) -> list[RateLimitResult]:
        """Check rate limits for all time windows using atomic operations."""
        results = []
        current_time = int(time.time())
        request_id = str(uuid.uuid4())

        # Check minute window
        if "per_minute" in limits:
            result = await self._check_window_atomic(
                redis,
                user_id,
                "minute",
                limits["per_minute"],
                current_time,
                request_id,
            )
            results.append(result)

        # Check hour window
        if "per_hour" in limits:
            result = await self._check_window_atomic(
                redis,
                user_id,
                "hour",
                limits["per_hour"],
                current_time,
                request_id,
            )
            results.append(result)

        # Check day window
        if "per_day" in limits:
            result = await self._check_window_atomic(
                redis,
                user_id,
                "day",
                limits["per_day"],
                current_time,
                request_id,
            )
            results.append(result)

        return results

    async def _check_window_atomic(
        self,
        redis: Redis,
        user_id: str,
        window: str,
        limit: int,
        current_time: int,
        request_id: str,
    ) -> RateLimitResult:
        """
        Check rate limit for a specific time window using atomic Lua script.

        Uses sliding window algorithm with sorted sets.
        Atomic operation prevents race conditions.
        """
        window_size = WINDOWS.get(window, 60)
        window_start = current_time - window_size
        key = f"rl:user:{user_id}:{window}"
        reset_at = current_time + window_size

        # Execute atomic Lua script
        result = await redis.eval(
            RATE_LIMIT_LUA_SCRIPT,
            1,  # number of keys
            key,
            window_start,
            limit,
            current_time,
            request_id,
            window_size,
        )

        allowed = result[0] == 1
        remaining = result[1]

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining if allowed else 0,
            limit=limit,
            reset_at=reset_at,
            window=window,
        )

    async def increment_usage(
        self,
        user_id: UUID,
        amount: int = 1,
    ) -> int:
        """
        Increment usage counter for billing.

        Args:
            user_id: User UUID
            amount: Amount to increment

        Returns:
            New counter value
        """
        now = time.gmtime()
        key = f"usage:monthly:{user_id}:{now.tm_year}:{now.tm_mon}"

        # Lua script for atomic increment with expiry
        lua_script = """
        local key = KEYS[1]
        local amount = tonumber(ARGV[1])
        local expire = tonumber(ARGV[2])
        
        local new_value = redis.call('INCRBY', key, amount)
        
        -- Set expiry only if this is a new key (TTL = -1)
        if redis.call('TTL', key) == -1 then
            redis.call('EXPIRE', key, expire)
        end
        
        return new_value
        """

        async with redis_context("rate_limit") as redis:
            result = await redis.eval(
                lua_script,
                1,
                key,
                amount,
                WINDOWS["month"] + 86400,  # Extra day buffer
            )

        return result

    async def get_usage(
        self,
        user_id: UUID,
        period: str = "month",
    ) -> dict[str, Any]:
        """
        Get current usage for a period.

        Args:
            user_id: User UUID
            period: Period to get usage for

        Returns:
            Usage statistics
        """
        now = time.gmtime()

        async with redis_context("rate_limit") as redis:
            if period == "month":
                key = f"usage:monthly:{user_id}:{now.tm_year}:{now.tm_mon}"
                count = await redis.get(key)
                return {
                    "period": "month",
                    "year": now.tm_year,
                    "month": now.tm_mon,
                    "count": int(count) if count else 0,
                }

            elif period == "day":
                key = f"rl:user:{user_id}:day"
                count = await redis.zcard(key)
                return {
                    "period": "day",
                    "count": count,
                }

            elif period == "hour":
                key = f"rl:user:{user_id}:hour"
                count = await redis.zcard(key)
                return {
                    "period": "hour",
                    "count": count,
                }

            elif period == "minute":
                key = f"rl:user:{user_id}:minute"
                count = await redis.zcard(key)
                return {
                    "period": "minute",
                    "count": count,
                }

        return {"period": period, "count": 0}

    async def get_all_usage(
        self,
        user_id: UUID,
        plan_name: str,
    ) -> dict[str, Any]:
        """
        Get usage for all rate limit windows.

        Args:
            user_id: User UUID
            plan_name: Plan name for limits

        Returns:
            Usage for all windows
        """
        limits = RATE_LIMITS.get(plan_name, RATE_LIMITS["free"])

        async with redis_context("rate_limit") as redis:
            pipe = redis.pipeline()

            # Get counts for each window
            pipe.zcard(f"rl:user:{user_id}:minute")
            pipe.zcard(f"rl:user:{user_id}:hour")
            pipe.zcard(f"rl:user:{user_id}:day")

            # Get monthly usage
            now = time.gmtime()
            monthly_key = f"usage:monthly:{user_id}:{now.tm_year}:{now.tm_mon}"
            pipe.get(monthly_key)

            results = await pipe.execute()

        minute_count = results[0]
        hour_count = results[1]
        day_count = results[2]
        month_count = int(results[3]) if results[3] else 0

        return {
            "per_minute": {
                "used": minute_count,
                "limit": limits.get("per_minute", 10),
                "remaining": max(0, limits.get("per_minute", 10) - minute_count),
            },
            "per_hour": {
                "used": hour_count,
                "limit": limits.get("per_hour", 100),
                "remaining": max(0, limits.get("per_hour", 100) - hour_count),
            },
            "per_day": {
                "used": day_count,
                "limit": limits.get("per_day", 200),
                "remaining": max(0, limits.get("per_day", 200) - day_count),
            },
            "per_month": {
                "used": month_count,
                "limit": limits.get("per_month", 100),
                "remaining": max(0, limits.get("per_month", 100) - month_count),
            },
        }

    async def reset_user_limits(self, user_id: UUID) -> bool:
        """
        Reset all rate limits for a user (admin function).

        Args:
            user_id: User UUID

        Returns:
            True if reset successful
        """
        async with redis_context("rate_limit") as redis:
            keys = [
                f"rl:user:{user_id}:minute",
                f"rl:user:{user_id}:hour",
                f"rl:user:{user_id}:day",
            ]
            await redis.delete(*keys)

        logger.info("Rate limits reset", user_id=str(user_id))
        return True


# Global rate limit service instance
rate_limit_service = RateLimitService()
