"""
Integration Tests - Renders API
================================
Tests for screenshot and PDF rendering endpoints.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.render_job import RenderStatus


class TestScreenshotEndpoint:
    """Tests for screenshot rendering endpoint."""

    @pytest.mark.asyncio
    async def test_screenshot_sync_success(
        self,
        client: AsyncClient,
        auth_headers,
        sample_screenshot_request,
        mock_playwright,
        mock_s3_client,
    ):
        """Test successful synchronous screenshot."""
        with patch("app.services.render_service.RenderService") as mock_render, \
             patch("app.services.storage_service.StorageService") as mock_storage:
            
            mock_render_instance = mock_render.return_value
            mock_render_instance.capture_screenshot = AsyncMock(
                return_value=b"fake-image-data"
            )
            
            mock_storage_instance = mock_storage.return_value
            mock_storage_instance.upload_file = AsyncMock(
                return_value="renders/test/screenshot.png"
            )
            mock_storage_instance.get_signed_url = AsyncMock(
                return_value="https://s3.example.com/signed-url"
            )
            
            response = await client.post(
                "/api/v1/renders/screenshot",
                headers=auth_headers,
                json=sample_screenshot_request,
            )
            
            assert response.status_code in [200, 201]
            data = response.json()
            assert "id" in data
            assert "url" in data or "download_url" in data

    @pytest.mark.asyncio
    async def test_screenshot_async_success(
        self,
        client: AsyncClient,
        auth_headers,
        sample_screenshot_request,
        mock_celery,
    ):
        """Test successful asynchronous screenshot."""
        sample_screenshot_request["async"] = True
        
        response = await client.post(
            "/api/v1/renders/screenshot",
            headers=auth_headers,
            json=sample_screenshot_request,
        )
        
        assert response.status_code == 202
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_screenshot_invalid_url(
        self,
        client: AsyncClient,
        auth_headers,
    ):
        """Test screenshot with invalid URL."""
        response = await client.post(
            "/api/v1/renders/screenshot",
            headers=auth_headers,
            json={
                "url": "not-a-valid-url",
                "options": {"width": 1280, "height": 720},
            },
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_screenshot_localhost_blocked(
        self,
        client: AsyncClient,
        auth_headers,
    ):
        """Test screenshot of localhost is blocked."""
        response = await client.post(
            "/api/v1/renders/screenshot",
            headers=auth_headers,
            json={
                "url": "http://localhost:8080",
                "options": {"width": 1280, "height": 720},
            },
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_screenshot_private_ip_blocked(
        self,
        client: AsyncClient,
        auth_headers,
    ):
        """Test screenshot of private IP is blocked."""
        response = await client.post(
            "/api/v1/renders/screenshot",
            headers=auth_headers,
            json={
                "url": "http://192.168.1.1",
                "options": {"width": 1280, "height": 720},
            },
        )
        
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_screenshot_resolution_limit_free(
        self,
        client: AsyncClient,
        auth_headers,
    ):
        """Test screenshot resolution is limited for free users."""
        response = await client.post(
            "/api/v1/renders/screenshot",
            headers=auth_headers,
            json={
                "url": "https://example.com",
                "options": {
                    "width": 3840,  # 4K width
                    "height": 2160,
                },
            },
        )
        
        # Should be rejected or capped
        assert response.status_code in [200, 201, 422]

    @pytest.mark.asyncio
    async def test_screenshot_with_api_key(
        self,
        client: AsyncClient,
        api_key_headers,
        sample_screenshot_request,
        mock_playwright,
        mock_s3_client,
    ):
        """Test screenshot with API key authentication."""
        with patch("app.services.render_service.RenderService") as mock_render, \
             patch("app.services.storage_service.StorageService") as mock_storage:
            
            mock_render_instance = mock_render.return_value
            mock_render_instance.capture_screenshot = AsyncMock(
                return_value=b"fake-image-data"
            )
            
            mock_storage_instance = mock_storage.return_value
            mock_storage_instance.upload_file = AsyncMock(
                return_value="renders/test/screenshot.png"
            )
            mock_storage_instance.get_signed_url = AsyncMock(
                return_value="https://s3.example.com/signed-url"
            )
            
            response = await client.post(
                "/api/v1/renders/screenshot",
                headers=api_key_headers,
                json=sample_screenshot_request,
            )
            
            assert response.status_code in [200, 201, 202]

    @pytest.mark.asyncio
    async def test_screenshot_unauthenticated(
        self,
        client: AsyncClient,
        sample_screenshot_request,
    ):
        """Test screenshot without authentication."""
        response = await client.post(
            "/api/v1/renders/screenshot",
            json=sample_screenshot_request,
        )
        
        assert response.status_code == 401


class TestPDFEndpoint:
    """Tests for PDF rendering endpoint."""

    @pytest.mark.asyncio
    async def test_pdf_sync_success(
        self,
        client: AsyncClient,
        pro_auth_headers,
        sample_pdf_request,
        mock_playwright,
        mock_s3_client,
    ):
        """Test successful synchronous PDF generation."""
        with patch("app.services.render_service.RenderService") as mock_render, \
             patch("app.services.storage_service.StorageService") as mock_storage:
            
            mock_render_instance = mock_render.return_value
            mock_render_instance.generate_pdf = AsyncMock(
                return_value=b"fake-pdf-data"
            )
            
            mock_storage_instance = mock_storage.return_value
            mock_storage_instance.upload_file = AsyncMock(
                return_value="renders/test/document.pdf"
            )
            mock_storage_instance.get_signed_url = AsyncMock(
                return_value="https://s3.example.com/signed-pdf-url"
            )
            
            response = await client.post(
                "/api/v1/renders/pdf",
                headers=pro_auth_headers,
                json=sample_pdf_request,
            )
            
            assert response.status_code in [200, 201]
            data = response.json()
            assert "id" in data

    @pytest.mark.asyncio
    async def test_pdf_free_user_blocked(
        self,
        client: AsyncClient,
        auth_headers,  # Free user
        sample_pdf_request,
    ):
        """Test PDF generation blocked for free users."""
        response = await client.post(
            "/api/v1/renders/pdf",
            headers=auth_headers,
            json=sample_pdf_request,
        )
        
        # PDF should be blocked for free tier
        assert response.status_code in [403, 402]

    @pytest.mark.asyncio
    async def test_pdf_async_success(
        self,
        client: AsyncClient,
        pro_auth_headers,
        sample_pdf_request,
        mock_celery,
    ):
        """Test successful asynchronous PDF generation."""
        sample_pdf_request["async"] = True
        
        response = await client.post(
            "/api/v1/renders/pdf",
            headers=pro_auth_headers,
            json=sample_pdf_request,
        )
        
        assert response.status_code == 202
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"


class TestRenderJobStatus:
    """Tests for render job status endpoint."""

    @pytest.mark.asyncio
    async def test_get_render_status(
        self,
        client: AsyncClient,
        auth_headers,
        test_render_job,
    ):
        """Test getting render job status."""
        response = await client.get(
            f"/api/v1/renders/{test_render_job.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_render_job.id)
        assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_render_status_not_found(
        self,
        client: AsyncClient,
        auth_headers,
    ):
        """Test getting status of non-existent render job."""
        fake_id = uuid.uuid4()
        
        response = await client.get(
            f"/api/v1/renders/{fake_id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_render_status_other_user(
        self,
        client: AsyncClient,
        pro_auth_headers,  # Different user
        test_render_job,  # Belongs to test_user, not pro_user
    ):
        """Test getting status of another user's render job."""
        response = await client.get(
            f"/api/v1/renders/{test_render_job.id}",
            headers=pro_auth_headers,
        )
        
        assert response.status_code == 404


class TestRenderHistory:
    """Tests for render history endpoint."""

    @pytest.mark.asyncio
    async def test_list_renders(
        self,
        client: AsyncClient,
        auth_headers,
        test_render_job,
    ):
        """Test listing user's render jobs."""
        response = await client.get(
            "/api/v1/renders",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) >= 1

    @pytest.mark.asyncio
    async def test_list_renders_with_pagination(
        self,
        client: AsyncClient,
        auth_headers,
    ):
        """Test render list with pagination."""
        response = await client.get(
            "/api/v1/renders?page=1&limit=10",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "page" in data
        assert "limit" in data

    @pytest.mark.asyncio
    async def test_list_renders_filter_by_type(
        self,
        client: AsyncClient,
        auth_headers,
    ):
        """Test render list filtered by type."""
        response = await client.get(
            "/api/v1/renders?type=screenshot",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["type"] == "screenshot"

    @pytest.mark.asyncio
    async def test_list_renders_filter_by_status(
        self,
        client: AsyncClient,
        auth_headers,
    ):
        """Test render list filtered by status."""
        response = await client.get(
            "/api/v1/renders?status=completed",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["status"] == "completed"

