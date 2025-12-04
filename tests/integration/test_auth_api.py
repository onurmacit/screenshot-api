"""
Integration Tests - Auth API
=============================
Tests for authentication endpoints.
"""

import uuid

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, get_password_hash


class TestAuthRegister:
    """Tests for user registration endpoint."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient, test_plan):
        """Test successful user registration."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePass123!",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["email"] == "newuser@example.com"
        assert "password" not in data
        assert "password_hash" not in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, test_user):
        """Test registration with existing email."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user.email,
                "password": "SecurePass123!",
            },
        )
        
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient, test_plan):
        """Test registration with invalid email."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "invalid-email",
                "password": "SecurePass123!",
            },
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_weak_password(self, client: AsyncClient, test_plan):
        """Test registration with weak password."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "password": "weak",
            },
        )
        
        assert response.status_code == 422


class TestAuthLogin:
    """Tests for login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user):
        """Test successful login."""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "TestPassword123!",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, test_user):
        """Test login with wrong password."""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "WrongPassword123!",
            },
        )
        
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with non-existent user."""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent@example.com",
                "password": "AnyPassword123!",
            },
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, client: AsyncClient, db_session, test_plan):
        """Test login with inactive user."""
        from app.models.user import User
        
        user = User(
            id=uuid.uuid4(),
            email="inactive@example.com",
            password_hash=get_password_hash("TestPassword123!"),
            plan_id=test_plan.id,
            is_active=False,
        )
        db_session.add(user)
        await db_session.commit()
        
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "inactive@example.com",
                "password": "TestPassword123!",
            },
        )
        
        assert response.status_code == 401


class TestAuthRefreshToken:
    """Tests for token refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client: AsyncClient, test_user):
        """Test successful token refresh."""
        # First, login to get refresh token
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "TestPassword123!",
            },
        )
        refresh_token = login_response.json()["refresh_token"]
        
        # Use refresh token to get new access token
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, client: AsyncClient):
        """Test token refresh with invalid token."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        
        assert response.status_code == 401


class TestAuthAPIKeys:
    """Tests for API key management endpoints."""

    @pytest.mark.asyncio
    async def test_create_api_key(self, client: AsyncClient, auth_headers):
        """Test creating API key."""
        response = await client.post(
            "/api/v1/auth/api-keys",
            headers=auth_headers,
            json={
                "name": "Test API Key",
                "scopes": ["render:read", "render:write"],
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "key" in data  # Raw key only returned on creation
        assert data["name"] == "Test API Key"
        assert data["key"].startswith("sk_")

    @pytest.mark.asyncio
    async def test_list_api_keys(self, client: AsyncClient, auth_headers, test_api_key):
        """Test listing API keys."""
        response = await client.get(
            "/api/v1/auth/api-keys",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        # Should not include raw key
        for key in data:
            assert "key_hash" not in key
            assert "key_prefix" in key

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, client: AsyncClient, auth_headers, test_api_key):
        """Test revoking API key."""
        api_key, _ = test_api_key
        
        response = await client.delete(
            f"/api/v1/auth/api-keys/{api_key.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_create_api_key_unauthenticated(self, client: AsyncClient):
        """Test creating API key without authentication."""
        response = await client.post(
            "/api/v1/auth/api-keys",
            json={"name": "Test Key"},
        )
        
        assert response.status_code == 401


class TestAuthMe:
    """Tests for current user endpoint."""

    @pytest.mark.asyncio
    async def test_get_current_user(self, client: AsyncClient, auth_headers, test_user):
        """Test getting current user info."""
        response = await client.get(
            "/api/v1/auth/me",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert "password" not in data

    @pytest.mark.asyncio
    async def test_get_current_user_unauthenticated(self, client: AsyncClient):
        """Test getting current user without authentication."""
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401

