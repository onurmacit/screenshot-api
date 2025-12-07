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
        assert "user_id" in data
        assert data["email"] == "newuser@example.com"
        assert "access_token" in data
        assert "refresh_token" in data
        assert "password" not in data

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
            json={
                "email": test_user.email,
                "password": "TestPassword123!",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, test_user):
        """Test login with wrong password."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "WrongPassword123!",
            },
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with non-existent user."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
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
            json={
                "email": "inactive@example.com",
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
            json={
                "email": test_user.email,
                "password": "TestPassword123!",
            },
        )
        assert login_response.status_code == 200
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
                "scopes": ["renders:read", "renders:write"],
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "api_key" in data
        assert data["name"] == "Test API Key"
        assert data["api_key"].startswith("sk_")

    @pytest.mark.asyncio
    async def test_list_api_keys(self, client: AsyncClient, auth_headers, test_api_key):
        """Test listing API keys."""
        response = await client.get(
            "/api/v1/auth/api-keys",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "keys" in data
        assert isinstance(data["keys"], list)
        assert len(data["keys"]) >= 1

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, client: AsyncClient, auth_headers, test_api_key):
        """Test revoking API key."""
        api_key, _ = test_api_key
        
        response = await client.delete(
            f"/api/v1/auth/api-keys/{api_key.id}",
            headers=auth_headers,
        )
        
        assert response.status_code in [200, 204]

    @pytest.mark.asyncio
    async def test_create_api_key_unauthenticated(self, client: AsyncClient):
        """Test creating API key without authentication."""
        response = await client.post(
            "/api/v1/auth/api-keys",
            json={"name": "Test Key"},
        )
        
        assert response.status_code in [401, 403]


class TestAuthLogout:
    """Tests for logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_success(self, client: AsyncClient, auth_headers):
        """Test successful logout."""
        response = await client.post(
            "/api/v1/auth/logout",
            headers=auth_headers,
        )
        
        assert response.status_code in [200, 204]
