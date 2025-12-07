"""
Unit Tests - Storage Service
=============================
Tests for S3 storage operations.
"""

import io
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.storage_service import StorageService


class MockS3Manager:
    """Mock S3Manager for testing."""
    
    def __init__(self):
        self.uploaded_files = {}
        self.deleted_files = []
        self._presigned_url = "https://s3.example.com/bucket/key?signature=xyz"
        self._file_exists = True
        self._file_metadata = {
            "ContentLength": 12345,
            "ContentType": "image/png",
            "LastModified": datetime.now(timezone.utc),
        }
    
    def generate_key(self, user_id: str, job_id: str, extension: str) -> str:
        """Generate S3 key."""
        return f"renders/{user_id}/{job_id}.{extension}"
    
    async def upload_file(
        self,
        file_bytes: bytes,
        key: str,
        content_type: str,
        metadata: dict = None,
    ) -> dict:
        """Mock upload file."""
        self.uploaded_files[key] = {
            "bytes": file_bytes,
            "content_type": content_type,
            "metadata": metadata,
        }
        return {
            "s3_key": key,
            "s3_url": f"https://s3.example.com/bucket/{key}",
        }
    
    async def generate_presigned_url(self, key: str, expires_in: int) -> str:
        """Mock generate presigned URL."""
        return f"{self._presigned_url}&key={key}&expires={expires_in}"
    
    async def delete_file(self, key: str) -> bool:
        """Mock delete file."""
        self.deleted_files.append(key)
        return True
    
    async def delete_files(self, keys: list) -> int:
        """Mock delete multiple files."""
        self.deleted_files.extend(keys)
        return len(keys)
    
    async def get_file_metadata(self, key: str) -> dict:
        """Mock get file metadata."""
        if not self._file_exists:
            return None
        return self._file_metadata
    
    async def file_exists(self, key: str) -> bool:
        """Mock file exists check."""
        return self._file_exists


class TestStorageService:
    """Tests for StorageService."""

    @pytest.fixture
    def mock_s3_manager(self):
        """Create mock S3Manager."""
        return MockS3Manager()

    @pytest.fixture
    def storage_service(self, mock_s3_manager):
        """Create StorageService instance with mock."""
        with patch.object(StorageService, '__init__', lambda self: None):
            service = StorageService()
            service.s3 = mock_s3_manager
            service.bucket = "test-bucket"
            return service

    @pytest.mark.asyncio
    async def test_upload_render(self, storage_service, mock_s3_manager):
        """Test uploading render file."""
        file_bytes = b"test image content"
        user_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        
        result = await storage_service.upload_render(
            file_bytes=file_bytes,
            user_id=user_id,
            job_id=job_id,
            file_type="png",
        )
        
        assert "s3_key" in result
        assert "s3_url" in result
        assert result["file_size"] == len(file_bytes)
        assert user_id in result["s3_key"]
        assert job_id in result["s3_key"]

    @pytest.mark.asyncio
    async def test_upload_render_with_metadata(self, storage_service, mock_s3_manager):
        """Test uploading render file with custom metadata."""
        file_bytes = b"test content"
        user_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        metadata = {"custom-key": "custom-value"}
        
        await storage_service.upload_render(
            file_bytes=file_bytes,
            user_id=user_id,
            job_id=job_id,
            file_type="png",
            metadata=metadata,
        )
        
        # Check that custom metadata was included
        uploaded_key = list(mock_s3_manager.uploaded_files.keys())[0]
        uploaded_metadata = mock_s3_manager.uploaded_files[uploaded_key]["metadata"]
        assert "custom-key" in uploaded_metadata

    @pytest.mark.asyncio
    async def test_generate_download_url(self, storage_service):
        """Test generating download URL."""
        s3_key = "renders/user123/job456.png"
        
        url = await storage_service.generate_download_url(s3_key, expires_in=3600)
        
        assert "https://" in url
        assert s3_key in url

    @pytest.mark.asyncio
    async def test_generate_download_url_default_expiration(self, storage_service):
        """Test generating download URL with default expiration."""
        s3_key = "renders/user123/job456.png"
        
        with patch("app.services.storage_service.settings") as mock_settings:
            mock_settings.SIGNED_URL_EXPIRY_SECONDS = 1800
            
            url = await storage_service.generate_download_url(s3_key)
        
        assert url is not None

    @pytest.mark.asyncio
    async def test_delete_file(self, storage_service, mock_s3_manager):
        """Test deleting file."""
        s3_key = "renders/user123/job456.png"
        
        result = await storage_service.delete_file(s3_key)
        
        assert result is True
        assert s3_key in mock_s3_manager.deleted_files

    @pytest.mark.asyncio
    async def test_delete_files(self, storage_service, mock_s3_manager):
        """Test deleting multiple files."""
        s3_keys = [
            "renders/user123/job1.png",
            "renders/user123/job2.png",
            "renders/user123/job3.png",
        ]
        
        count = await storage_service.delete_files(s3_keys)
        
        assert count == 3
        for key in s3_keys:
            assert key in mock_s3_manager.deleted_files

    @pytest.mark.asyncio
    async def test_delete_files_empty(self, storage_service):
        """Test deleting empty list of files."""
        count = await storage_service.delete_files([])
        
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_file_info(self, storage_service, mock_s3_manager):
        """Test getting file info."""
        s3_key = "renders/user123/job456.png"
        
        info = await storage_service.get_file_info(s3_key)
        
        assert info is not None
        assert "ContentLength" in info
        assert "ContentType" in info

    @pytest.mark.asyncio
    async def test_get_file_info_not_found(self, storage_service, mock_s3_manager):
        """Test getting file info for non-existent file."""
        mock_s3_manager._file_exists = False
        mock_s3_manager._file_metadata = None
        
        async def mock_metadata(key):
            return None
        
        mock_s3_manager.get_file_metadata = mock_metadata
        
        s3_key = "renders/nonexistent.png"
        info = await storage_service.get_file_info(s3_key)
        
        assert info is None

    @pytest.mark.asyncio
    async def test_file_exists_true(self, storage_service, mock_s3_manager):
        """Test checking if file exists (exists)."""
        s3_key = "renders/user123/job456.png"
        mock_s3_manager._file_exists = True
        
        result = await storage_service.file_exists(s3_key)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_file_exists_false(self, storage_service, mock_s3_manager):
        """Test checking if file exists (not exists)."""
        mock_s3_manager._file_exists = False
        s3_key = "renders/nonexistent.png"
        
        result = await storage_service.file_exists(s3_key)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_expired_files(self, storage_service, mock_s3_manager):
        """Test cleaning up expired files."""
        expired_keys = [
            "renders/old1.png",
            "renders/old2.png",
        ]
        
        result = await storage_service.cleanup_expired_files(expired_keys)
        
        assert result["deleted"] == 2
        assert result["errors"] == 0
        assert result["total"] == 2

    @pytest.mark.asyncio
    async def test_cleanup_expired_files_empty(self, storage_service):
        """Test cleaning up with no expired files."""
        result = await storage_service.cleanup_expired_files([])
        
        assert result["deleted"] == 0
        assert result["errors"] == 0

    def test_calculate_expiry_date(self, storage_service):
        """Test calculating expiry date."""
        with patch("app.services.storage_service.settings") as mock_settings:
            mock_settings.RENDER_EXPIRY_DAYS = 7
            
            expiry = storage_service.calculate_expiry_date()
        
        expected = datetime.now(timezone.utc) + timedelta(days=7)
        # Allow 1 second tolerance
        diff = abs((expiry - expected).total_seconds())
        assert diff < 1

    def test_calculate_expiry_date_custom_days(self, storage_service):
        """Test calculating expiry date with custom days."""
        expiry = storage_service.calculate_expiry_date(days=30)
        
        expected = datetime.now(timezone.utc) + timedelta(days=30)
        # Allow 1 second tolerance
        diff = abs((expiry - expected).total_seconds())
        assert diff < 1


class TestStorageServiceFileTypes:
    """Tests for different file types."""

    @pytest.fixture
    def mock_s3_manager(self):
        return MockS3Manager()

    @pytest.fixture
    def storage_service(self, mock_s3_manager):
        with patch.object(StorageService, '__init__', lambda self: None):
            service = StorageService()
            service.s3 = mock_s3_manager
            service.bucket = "test-bucket"
            return service

    @pytest.mark.asyncio
    async def test_upload_png(self, storage_service, mock_s3_manager):
        """Test uploading PNG file."""
        file_bytes = b"PNG content"
        user_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        
        result = await storage_service.upload_render(
            file_bytes=file_bytes,
            user_id=user_id,
            job_id=job_id,
            file_type="png",
        )
        
        assert result["s3_key"].endswith(".png")

    @pytest.mark.asyncio
    async def test_upload_jpeg(self, storage_service, mock_s3_manager):
        """Test uploading JPEG file."""
        file_bytes = b"JPEG content"
        user_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        
        result = await storage_service.upload_render(
            file_bytes=file_bytes,
            user_id=user_id,
            job_id=job_id,
            file_type="jpeg",
        )
        
        # Implementation uses .jpg extension for jpeg
        assert result["s3_key"].endswith(".jpg") or result["s3_key"].endswith(".jpeg")

    @pytest.mark.asyncio
    async def test_upload_webp(self, storage_service, mock_s3_manager):
        """Test uploading WebP file."""
        file_bytes = b"WebP content"
        user_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        
        result = await storage_service.upload_render(
            file_bytes=file_bytes,
            user_id=user_id,
            job_id=job_id,
            file_type="webp",
        )
        
        assert result["s3_key"].endswith(".webp")

    @pytest.mark.asyncio
    async def test_upload_pdf(self, storage_service, mock_s3_manager):
        """Test uploading PDF file."""
        file_bytes = b"PDF content"
        user_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        
        result = await storage_service.upload_render(
            file_bytes=file_bytes,
            user_id=user_id,
            job_id=job_id,
            file_type="pdf",
        )
        
        assert result["s3_key"].endswith(".pdf")
