"""
Integration Tests - Health API
===============================
Tests for health check endpoints.
"""

import pytest
from httpx import AsyncClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test basic health check endpoint."""
        response = await client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_liveness_probe(self, client: AsyncClient):
        """Test Kubernetes liveness probe."""
        response = await client.get("/api/v1/health/live")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

    @pytest.mark.asyncio
    async def test_readiness_probe(self, client: AsyncClient):
        """Test Kubernetes readiness probe."""
        response = await client.get("/api/v1/health/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "checks" in data

    @pytest.mark.asyncio
    async def test_version_endpoint(self, client: AsyncClient):
        """Test version endpoint."""
        response = await client.get("/api/v1/health/version")
        
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "environment" in data


class TestRootEndpoint:
    """Tests for root endpoint."""

    @pytest.mark.asyncio
    async def test_root_redirect_or_info(self, client: AsyncClient):
        """Test root endpoint."""
        response = await client.get("/")
        
        # Should either redirect to docs or return API info
        assert response.status_code in [200, 307, 308]

    @pytest.mark.asyncio
    async def test_docs_endpoint(self, client: AsyncClient):
        """Test OpenAPI docs endpoint."""
        response = await client.get("/docs")
        
        # Should return HTML or redirect
        assert response.status_code in [200, 307, 308]

    @pytest.mark.asyncio
    async def test_openapi_schema(self, client: AsyncClient):
        """Test OpenAPI schema endpoint."""
        response = await client.get("/openapi.json")
        
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
        assert "info" in data

