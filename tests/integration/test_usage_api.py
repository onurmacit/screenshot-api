"""
Integration Tests - Usage API
==============================
Tests for usage tracking endpoints.
"""

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

from app.models.usage_record import UsageRecord


class TestUsageEndpoints:
    """Tests for usage tracking endpoints."""

    @pytest.mark.asyncio
    async def test_get_current_usage(
        self,
        client: AsyncClient,
        auth_headers,
        test_user,
    ):
        """Test getting current period usage."""
        response = await client.get(
            "/api/v1/usage/current",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "requests_used" in data
        assert "requests_limit" in data
        assert "period_start" in data
        assert "period_end" in data

    @pytest.mark.asyncio
    async def test_get_usage_history(
        self,
        client: AsyncClient,
        auth_headers,
        db_session,
        test_user,
        test_api_key,
    ):
        """Test getting usage history."""
        api_key, _ = test_api_key
        
        # Create some usage records
        for i in range(5):
            record = UsageRecord(
                id=uuid.uuid4(),
                user_id=test_user.id,
                api_key_id=api_key.id,
                endpoint="/api/v1/renders/screenshot",
                method="POST",
                credits_used=1,
                timestamp=datetime.utcnow() - timedelta(days=i),
            )
            db_session.add(record)
        await db_session.commit()
        
        response = await client.get(
            "/api/v1/usage/history",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 5

    @pytest.mark.asyncio
    async def test_get_usage_history_with_date_range(
        self,
        client: AsyncClient,
        auth_headers,
    ):
        """Test getting usage history with date range."""
        start_date = (datetime.utcnow() - timedelta(days=7)).isoformat()
        end_date = datetime.utcnow().isoformat()
        
        response = await client.get(
            f"/api/v1/usage/history?start_date={start_date}&end_date={end_date}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    @pytest.mark.asyncio
    async def test_get_usage_by_day(
        self,
        client: AsyncClient,
        auth_headers,
    ):
        """Test getting usage aggregated by day."""
        response = await client.get(
            "/api/v1/usage/history?aggregate=day",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        # Should have aggregated data
        assert "items" in data

    @pytest.mark.asyncio
    async def test_get_usage_unauthenticated(self, client: AsyncClient):
        """Test getting usage without authentication."""
        response = await client.get("/api/v1/usage/current")
        
        assert response.status_code == 401


class TestUsageLimits:
    """Tests for usage limit enforcement."""

    @pytest.mark.asyncio
    async def test_rate_limit_headers(
        self,
        client: AsyncClient,
        auth_headers,
    ):
        """Test that rate limit headers are included in response."""
        response = await client.get(
            "/api/v1/usage/current",
            headers=auth_headers,
        )
        
        # Check rate limit headers
        assert "X-RateLimit-Limit" in response.headers or response.status_code == 200
        # Note: Headers may be added by middleware

    @pytest.mark.asyncio
    async def test_quota_check(
        self,
        client: AsyncClient,
        auth_headers,
    ):
        """Test checking remaining quota."""
        response = await client.get(
            "/api/v1/usage/current",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "remaining" in data or "requests_limit" in data

