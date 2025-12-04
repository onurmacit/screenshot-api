"""
Unit Tests - Rate Limiter Service
==================================
Tests for rate limiting functionality.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.rate_limit_service import RateLimitService


class TestRateLimitService:
    """Tests for RateLimitService."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.get.return_value = None
        redis.set.return_value = True
        redis.incr.return_value = 1
        redis.expire.return_value = True
        redis.ttl.return_value = 60
        
        # Mock pipeline
        pipeline = AsyncMock()
        pipeline.incr.return_value = pipeline
        pipeline.expire.return_value = pipeline
        pipeline.execute.return_value = [1, True]
        redis.pipeline.return_value = pipeline
        
        return redis

    @pytest.fixture
    def rate_limiter(self, mock_redis):
        """Create RateLimitService instance."""
        return RateLimitService(mock_redis)

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, rate_limiter, mock_redis):
        """Test that request is allowed under rate limit."""
        mock_redis.pipeline.return_value.execute.return_value = [5, True]
        
        allowed, remaining, reset_at = await rate_limiter.check_rate_limit(
            key="test_key",
            limit=10,
            window=60,
        )
        
        assert allowed is True
        assert remaining == 5  # 10 - 5

    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self, rate_limiter, mock_redis):
        """Test that request is blocked when rate limit exceeded."""
        mock_redis.pipeline.return_value.execute.return_value = [15, True]
        mock_redis.ttl.return_value = 30
        
        allowed, remaining, reset_at = await rate_limiter.check_rate_limit(
            key="test_key",
            limit=10,
            window=60,
        )
        
        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_check_rate_limit_ip(self, rate_limiter, mock_redis):
        """Test IP-based rate limiting."""
        mock_redis.pipeline.return_value.execute.return_value = [1, True]
        
        allowed, remaining, reset_at = await rate_limiter.check_ip_rate_limit(
            ip_address="192.168.1.1",
            limit=100,
        )
        
        assert allowed is True
        # Verify correct key format was used
        mock_redis.pipeline.assert_called()

    @pytest.mark.asyncio
    async def test_check_rate_limit_user(self, rate_limiter, mock_redis):
        """Test user-based rate limiting."""
        mock_redis.pipeline.return_value.execute.return_value = [1, True]
        
        user_id = "test-user-123"
        allowed, remaining, reset_at = await rate_limiter.check_user_rate_limit(
            user_id=user_id,
            limit=1000,
        )
        
        assert allowed is True

    @pytest.mark.asyncio
    async def test_check_rate_limit_with_override(self, rate_limiter, mock_redis):
        """Test rate limiting with override."""
        # First call returns override value
        mock_redis.get.return_value = "200"  # Override limit
        mock_redis.pipeline.return_value.execute.return_value = [50, True]
        
        allowed, remaining, reset_at = await rate_limiter.check_user_rate_limit(
            user_id="premium-user",
            limit=100,  # Default limit
            check_override=True,
        )
        
        assert allowed is True
        # Should have 150 remaining (200 - 50)

    @pytest.mark.asyncio
    async def test_get_rate_limit_status(self, rate_limiter, mock_redis):
        """Test getting rate limit status."""
        mock_redis.get.return_value = "75"
        mock_redis.ttl.return_value = 45
        
        status = await rate_limiter.get_status(
            key="user:123:requests",
            limit=100,
        )
        
        assert status["current"] == 75
        assert status["limit"] == 100
        assert status["remaining"] == 25
        assert status["reset_in"] == 45

    @pytest.mark.asyncio
    async def test_reset_rate_limit(self, rate_limiter, mock_redis):
        """Test resetting rate limit."""
        mock_redis.delete.return_value = 1
        
        result = await rate_limiter.reset(key="user:123:requests")
        
        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_sliding_window_algorithm(self, rate_limiter, mock_redis):
        """Test sliding window rate limit implementation."""
        # Simulate multiple requests
        current_count = 0
        
        async def mock_execute():
            nonlocal current_count
            current_count += 1
            return [current_count, True]
        
        mock_redis.pipeline.return_value.execute = mock_execute
        
        results = []
        for _ in range(15):
            allowed, _, _ = await rate_limiter.check_rate_limit(
                key="sliding_test",
                limit=10,
                window=60,
            )
            results.append(allowed)
        
        # First 10 should be allowed, rest should be blocked
        assert results[:10] == [True] * 10
        assert all(not r for r in results[10:])

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, rate_limiter, mock_redis):
        """Test rate limiting under concurrent requests."""
        request_count = [0]
        
        async def mock_execute():
            request_count[0] += 1
            await asyncio.sleep(0.01)  # Simulate some latency
            return [request_count[0], True]
        
        mock_redis.pipeline.return_value.execute = mock_execute
        
        # Make concurrent requests
        tasks = [
            rate_limiter.check_rate_limit("concurrent_test", 100, 60)
            for _ in range(50)
        ]
        results = await asyncio.gather(*tasks)
        
        # All should be processed
        assert len(results) == 50
        # All should be allowed (under limit)
        assert all(r[0] for r in results)

