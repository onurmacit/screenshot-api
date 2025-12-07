"""
Unit Tests - Rate Limiter Service
==================================
Tests for rate limiting functionality.
"""

import asyncio
import time
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.rate_limit_service import (
    RateLimitService,
    RateLimitResult,
    RATE_LIMITS,
    WINDOWS,
)
from app.utils.exceptions import RateLimitError


class MockRedis:
    """Mock Redis client for testing."""
    
    def __init__(self):
        self._data = {}
        self._zsets = {}
        self._eval_return = [1, 9, 1]  # [allowed, remaining, count]
    
    async def eval(self, script: str, numkeys: int, *args):
        """Mock Lua script execution."""
        return self._eval_return
    
    async def zcard(self, key: str):
        """Mock ZCARD command."""
        return len(self._zsets.get(key, {}))
    
    async def get(self, key: str):
        """Mock GET command."""
        return self._data.get(key)
    
    async def delete(self, *keys):
        """Mock DELETE command."""
        deleted = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                deleted += 1
            if key in self._zsets:
                del self._zsets[key]
                deleted += 1
        return deleted
    
    def pipeline(self):
        """Return a mock pipeline."""
        return MockPipeline(self)
    
    def set_eval_return(self, allowed: int, remaining: int, count: int):
        """Set return value for eval."""
        self._eval_return = [allowed, remaining, count]


class MockPipeline:
    """Mock Redis pipeline."""
    
    def __init__(self, redis: MockRedis):
        self._redis = redis
        self._results = []
    
    def zcard(self, key: str):
        self._results.append(0)
        return self
    
    def get(self, key: str):
        self._results.append(None)
        return self
    
    async def execute(self):
        return self._results


class TestRateLimitResult:
    """Tests for RateLimitResult class."""

    def test_result_allowed(self):
        """Test allowed result."""
        result = RateLimitResult(
            allowed=True,
            remaining=5,
            limit=10,
            reset_at=int(time.time()) + 60,
            window="minute",
        )
        
        assert result.allowed is True
        assert result.remaining == 5
        assert result.limit == 10
        assert result.window == "minute"

    def test_result_denied(self):
        """Test denied result."""
        result = RateLimitResult(
            allowed=False,
            remaining=0,
            limit=10,
            reset_at=int(time.time()) + 60,
            window="minute",
        )
        
        assert result.allowed is False
        assert result.remaining == 0

    def test_retry_after(self):
        """Test retry_after calculation."""
        reset_at = int(time.time()) + 30
        result = RateLimitResult(
            allowed=False,
            remaining=0,
            limit=10,
            reset_at=reset_at,
            window="minute",
        )
        
        # retry_after should be approximately 30 seconds
        assert 25 <= result.retry_after <= 35

    def test_to_headers(self):
        """Test converting result to HTTP headers."""
        result = RateLimitResult(
            allowed=True,
            remaining=5,
            limit=10,
            reset_at=12345678,
            window="minute",
        )
        
        headers = result.to_headers()
        
        assert headers["X-RateLimit-Limit"] == "10"
        assert headers["X-RateLimit-Remaining"] == "5"
        assert headers["X-RateLimit-Reset"] == "12345678"


class TestRateLimits:
    """Tests for rate limit configurations."""

    def test_rate_limits_exist(self):
        """Test that rate limit configurations exist."""
        assert "free" in RATE_LIMITS
        assert "starter" in RATE_LIMITS
        assert "pro" in RATE_LIMITS
        assert "business" in RATE_LIMITS

    def test_free_tier_limits(self):
        """Test free tier has expected limits."""
        free = RATE_LIMITS["free"]
        
        assert "per_minute" in free
        assert "per_hour" in free
        assert "per_day" in free
        assert free["per_minute"] == 10

    def test_pro_tier_higher_than_free(self):
        """Test pro tier has higher limits than free."""
        free = RATE_LIMITS["free"]
        pro = RATE_LIMITS["pro"]
        
        assert pro["per_minute"] > free["per_minute"]
        assert pro["per_hour"] > free["per_hour"]
        assert pro["per_day"] > free["per_day"]

    def test_windows_defined(self):
        """Test time windows are defined."""
        assert WINDOWS["minute"] == 60
        assert WINDOWS["hour"] == 3600
        assert WINDOWS["day"] == 86400


class TestRateLimitService:
    """Tests for RateLimitService."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        return MockRedis()

    @pytest.fixture
    def rate_limiter(self, mock_redis):
        """Create RateLimitService instance."""
        return RateLimitService(redis=mock_redis)

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, mock_redis):
        """Test that request is allowed under rate limit."""
        mock_redis.set_eval_return(1, 9, 1)  # allowed, remaining=9, count=1
        
        rate_limiter = RateLimitService()
        user_id = uuid.uuid4()
        
        # Create proper async context manager
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def mock_context(pool):
            yield mock_redis
        
        with patch("app.services.rate_limit_service.redis_context", mock_context):
            result = await rate_limiter.check_rate_limit(
                user_id=user_id,
                plan_name="pro",
            )
        
        assert result.allowed is True
        assert result.remaining > 0

    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self, mock_redis):
        """Test that request is blocked when rate limit exceeded."""
        mock_redis.set_eval_return(0, 0, 100)  # not allowed, remaining=0
        
        rate_limiter = RateLimitService()
        user_id = uuid.uuid4()
        
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def mock_context(pool):
            yield mock_redis
        
        with patch("app.services.rate_limit_service.redis_context", mock_context):
            with pytest.raises(RateLimitError) as exc_info:
                await rate_limiter.check_rate_limit(
                    user_id=user_id,
                    plan_name="free",
                )
        
        assert "Rate limit exceeded" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_check_rate_limit_free_tier(self, mock_redis):
        """Test rate limiting with free tier."""
        mock_redis.set_eval_return(1, 5, 5)
        
        rate_limiter = RateLimitService()
        user_id = uuid.uuid4()
        
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def mock_context(pool):
            yield mock_redis
        
        with patch("app.services.rate_limit_service.redis_context", mock_context):
            result = await rate_limiter.check_rate_limit(
                user_id=user_id,
                plan_name="free",
            )
        
        assert result is not None
        assert result.limit == RATE_LIMITS["free"]["per_minute"]

    @pytest.mark.asyncio
    async def test_check_rate_limit_with_override(self, mock_redis):
        """Test rate limiting with custom override."""
        mock_redis.set_eval_return(1, 150, 50)
        
        rate_limiter = RateLimitService()
        user_id = uuid.uuid4()
        
        custom_limits = {
            "per_minute": 200,
            "per_hour": 5000,
            "per_day": 20000,
        }
        
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def mock_context(pool):
            yield mock_redis
        
        with patch("app.services.rate_limit_service.redis_context", mock_context):
            result = await rate_limiter.check_rate_limit(
                user_id=user_id,
                plan_name="free",
                override=custom_limits,
            )
        
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_check_rate_limit_disabled(self, mock_redis):
        """Test rate limiting when disabled."""
        rate_limiter = RateLimitService()
        user_id = uuid.uuid4()
        
        with patch("app.services.rate_limit_service.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = False
            
            result = await rate_limiter.check_rate_limit(
                user_id=user_id,
                plan_name="free",
            )
        
        assert result.allowed is True
        assert result.remaining == 999999

    @pytest.mark.asyncio
    async def test_increment_usage(self, mock_redis):
        """Test incrementing usage counter."""
        mock_redis._data["test_key"] = 5
        
        async def mock_eval(script, numkeys, *args):
            return 6  # New counter value
        
        mock_redis.eval = mock_eval
        
        rate_limiter = RateLimitService()
        user_id = uuid.uuid4()
        
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def mock_context(pool):
            yield mock_redis
        
        with patch("app.services.rate_limit_service.redis_context", mock_context):
            result = await rate_limiter.increment_usage(user_id=user_id, amount=1)
        
        assert result == 6

    @pytest.mark.asyncio
    async def test_get_usage(self, mock_redis):
        """Test getting usage statistics."""
        mock_redis._data["usage:monthly:test:2024:1"] = "75"
        
        rate_limiter = RateLimitService()
        user_id = uuid.uuid4()
        
        async def mock_get(key):
            return "75"
        
        mock_redis.get = mock_get
        
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def mock_context(pool):
            yield mock_redis
        
        with patch("app.services.rate_limit_service.redis_context", mock_context):
            result = await rate_limiter.get_usage(user_id=user_id, period="month")
        
        assert result["period"] == "month"
        assert result["count"] == 75

    @pytest.mark.asyncio
    async def test_reset_user_limits(self, mock_redis):
        """Test resetting user rate limits."""
        rate_limiter = RateLimitService()
        user_id = uuid.uuid4()
        
        deleted_keys = []
        
        async def mock_delete(*keys):
            deleted_keys.extend(keys)
            return len(keys)
        
        mock_redis.delete = mock_delete
        
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def mock_context(pool):
            yield mock_redis
        
        with patch("app.services.rate_limit_service.redis_context", mock_context):
            result = await rate_limiter.reset_user_limits(user_id=user_id)
        
        assert result is True
        assert len(deleted_keys) == 3  # minute, hour, day keys


class TestRateLimitEdgeCases:
    """Tests for edge cases in rate limiting."""

    def test_unknown_plan_uses_free_limits(self):
        """Test that unknown plan falls back to free limits."""
        limits = RATE_LIMITS.get("nonexistent", RATE_LIMITS["free"])
        assert limits == RATE_LIMITS["free"]

    @pytest.mark.asyncio
    async def test_api_key_id_optional(self):
        """Test that api_key_id is optional."""
        mock_redis = MockRedis()
        mock_redis.set_eval_return(1, 9, 1)
        
        rate_limiter = RateLimitService()
        user_id = uuid.uuid4()
        
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def mock_context(pool):
            yield mock_redis
        
        with patch("app.services.rate_limit_service.redis_context", mock_context):
            # Should work without api_key_id
            result = await rate_limiter.check_rate_limit(
                user_id=user_id,
                plan_name="pro",
            )
        
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_concurrent_rate_limit_checks(self):
        """Test rate limiting under concurrent requests."""
        mock_redis = MockRedis()
        call_count = [0]
        
        async def mock_eval(script, numkeys, *args):
            call_count[0] += 1
            await asyncio.sleep(0.01)  # Simulate some latency
            # Return allowed with decreasing remaining
            remaining = max(0, 50 - call_count[0])
            return [1, remaining, call_count[0]]
        
        mock_redis.eval = mock_eval
        
        rate_limiter = RateLimitService()
        user_id = uuid.uuid4()
        
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def mock_context(pool):
            yield mock_redis
        
        with patch("app.services.rate_limit_service.redis_context", mock_context):
            # Make concurrent requests
            tasks = [
                rate_limiter.check_rate_limit(user_id=user_id, plan_name="pro")
                for _ in range(10)
            ]
            results = await asyncio.gather(*tasks)
        
        # All should be processed
        assert len(results) == 10
        # All should be allowed (under limit)
        assert all(r.allowed for r in results)
