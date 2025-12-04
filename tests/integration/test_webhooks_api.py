"""
Integration Tests - Webhooks API
=================================
Tests for webhook management endpoints.
"""

import uuid

import pytest
from httpx import AsyncClient

from app.models.webhook import Webhook


class TestWebhookCRUD:
    """Tests for webhook CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_webhook(
        self,
        client: AsyncClient,
        pro_auth_headers,  # Webhooks require paid plan
        sample_webhook_payload,
    ):
        """Test creating a webhook."""
        response = await client.post(
            "/api/v1/webhooks",
            headers=pro_auth_headers,
            json=sample_webhook_payload,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["url"] == sample_webhook_payload["url"]
        assert "secret" in data
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_create_webhook_free_user_blocked(
        self,
        client: AsyncClient,
        auth_headers,  # Free user
        sample_webhook_payload,
    ):
        """Test webhook creation blocked for free users."""
        response = await client.post(
            "/api/v1/webhooks",
            headers=auth_headers,
            json=sample_webhook_payload,
        )
        
        # Webhooks not available on free tier
        assert response.status_code in [403, 402]

    @pytest.mark.asyncio
    async def test_create_webhook_invalid_url(
        self,
        client: AsyncClient,
        pro_auth_headers,
    ):
        """Test creating webhook with invalid URL."""
        response = await client.post(
            "/api/v1/webhooks",
            headers=pro_auth_headers,
            json={
                "url": "not-a-valid-url",
                "events": ["render.completed"],
            },
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_webhooks(
        self,
        client: AsyncClient,
        pro_auth_headers,
        db_session,
        test_pro_user,
    ):
        """Test listing webhooks."""
        # Create a webhook
        webhook = Webhook(
            id=uuid.uuid4(),
            user_id=test_pro_user.id,
            url="https://webhook.example.com/test",
            secret="test-secret",
            events=["render.completed"],
            is_active=True,
        )
        db_session.add(webhook)
        await db_session.commit()
        
        response = await client.get(
            "/api/v1/webhooks",
            headers=pro_auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_get_webhook(
        self,
        client: AsyncClient,
        pro_auth_headers,
        db_session,
        test_pro_user,
    ):
        """Test getting a specific webhook."""
        webhook = Webhook(
            id=uuid.uuid4(),
            user_id=test_pro_user.id,
            url="https://webhook.example.com/test",
            secret="test-secret",
            events=["render.completed"],
            is_active=True,
        )
        db_session.add(webhook)
        await db_session.commit()
        
        response = await client.get(
            f"/api/v1/webhooks/{webhook.id}",
            headers=pro_auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(webhook.id)

    @pytest.mark.asyncio
    async def test_update_webhook(
        self,
        client: AsyncClient,
        pro_auth_headers,
        db_session,
        test_pro_user,
    ):
        """Test updating a webhook."""
        webhook = Webhook(
            id=uuid.uuid4(),
            user_id=test_pro_user.id,
            url="https://webhook.example.com/old",
            secret="test-secret",
            events=["render.completed"],
            is_active=True,
        )
        db_session.add(webhook)
        await db_session.commit()
        
        response = await client.patch(
            f"/api/v1/webhooks/{webhook.id}",
            headers=pro_auth_headers,
            json={
                "url": "https://webhook.example.com/new",
                "events": ["render.completed", "render.failed"],
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["url"] == "https://webhook.example.com/new"
        assert "render.failed" in data["events"]

    @pytest.mark.asyncio
    async def test_delete_webhook(
        self,
        client: AsyncClient,
        pro_auth_headers,
        db_session,
        test_pro_user,
    ):
        """Test deleting a webhook."""
        webhook = Webhook(
            id=uuid.uuid4(),
            user_id=test_pro_user.id,
            url="https://webhook.example.com/delete",
            secret="test-secret",
            events=["render.completed"],
            is_active=True,
        )
        db_session.add(webhook)
        await db_session.commit()
        
        response = await client.delete(
            f"/api/v1/webhooks/{webhook.id}",
            headers=pro_auth_headers,
        )
        
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_webhook_not_found(
        self,
        client: AsyncClient,
        pro_auth_headers,
    ):
        """Test deleting non-existent webhook."""
        fake_id = uuid.uuid4()
        
        response = await client.delete(
            f"/api/v1/webhooks/{fake_id}",
            headers=pro_auth_headers,
        )
        
        assert response.status_code == 404


class TestWebhookEvents:
    """Tests for webhook events endpoint."""

    @pytest.mark.asyncio
    async def test_list_available_events(
        self,
        client: AsyncClient,
        pro_auth_headers,
    ):
        """Test listing available webhook events."""
        response = await client.get(
            "/api/v1/webhooks/events",
            headers=pro_auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert "render.completed" in data
        assert "render.failed" in data


class TestWebhookDelivery:
    """Tests for webhook delivery functionality."""

    @pytest.mark.asyncio
    async def test_webhook_test_delivery(
        self,
        client: AsyncClient,
        pro_auth_headers,
        db_session,
        test_pro_user,
    ):
        """Test sending test webhook delivery."""
        webhook = Webhook(
            id=uuid.uuid4(),
            user_id=test_pro_user.id,
            url="https://webhook.example.com/test",
            secret="test-secret",
            events=["render.completed"],
            is_active=True,
        )
        db_session.add(webhook)
        await db_session.commit()
        
        response = await client.post(
            f"/api/v1/webhooks/{webhook.id}/test",
            headers=pro_auth_headers,
        )
        
        # Test delivery should be accepted
        assert response.status_code in [200, 202]

