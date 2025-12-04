"""
Unit Tests - Storage Service
=============================
Tests for S3 storage operations.
"""

import io
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.services.storage_service import StorageService


class TestStorageService:
    """Tests for StorageService."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client."""
        client = MagicMock()
        client.put_object = MagicMock(return_value={"ETag": '"test-etag"'})
        client.get_object = MagicMock(return_value={
            "Body": io.BytesIO(b"test-content"),
            "ContentLength": 12,
            "ContentType": "image/png",
        })
        client.head_object = MagicMock(return_value={
            "ContentLength": 12,
            "ContentType": "image/png",
            "LastModified": datetime.utcnow(),
        })
        client.delete_object = MagicMock(return_value={})
        client.generate_presigned_url = MagicMock(
            return_value="https://s3.example.com/bucket/key?signature=xyz"
        )
        client.list_objects_v2 = MagicMock(return_value={
            "Contents": [
                {"Key": "file1.png", "Size": 100},
                {"Key": "file2.png", "Size": 200},
            ],
            "IsTruncated": False,
        })
        return client

    @pytest.fixture
    def storage_service(self, mock_s3_client):
        """Create StorageService instance."""
        with patch("app.services.storage_service.boto3") as mock_boto:
            mock_boto.client.return_value = mock_s3_client
            service = StorageService(
                bucket_name="test-bucket",
                region="us-east-1",
            )
            service._client = mock_s3_client
            return service

    @pytest.mark.asyncio
    async def test_upload_file_bytes(self, storage_service):
        """Test uploading file from bytes."""
        file_data = b"test image content"
        key = f"renders/{uuid.uuid4()}/screenshot.png"
        
        result = await storage_service.upload_file(
            file_data=file_data,
            key=key,
            content_type="image/png",
        )
        
        assert result == key
        storage_service._client.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_file_with_metadata(self, storage_service):
        """Test uploading file with metadata."""
        file_data = b"test content"
        key = "renders/test/file.png"
        metadata = {"user_id": "123", "render_id": "456"}
        
        await storage_service.upload_file(
            file_data=file_data,
            key=key,
            content_type="image/png",
            metadata=metadata,
        )
        
        call_args = storage_service._client.put_object.call_args
        assert call_args.kwargs.get("Metadata") == metadata

    @pytest.mark.asyncio
    async def test_generate_signed_url(self, storage_service):
        """Test generating signed URL."""
        key = "renders/test/file.png"
        
        url = await storage_service.get_signed_url(key, expiration=3600)
        
        assert "https://" in url
        storage_service._client.generate_presigned_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_signed_url_custom_expiration(self, storage_service):
        """Test generating signed URL with custom expiration."""
        key = "renders/test/file.png"
        expiration = 7200
        
        await storage_service.get_signed_url(key, expiration=expiration)
        
        call_args = storage_service._client.generate_presigned_url.call_args
        assert call_args.kwargs.get("ExpiresIn") == expiration

    @pytest.mark.asyncio
    async def test_delete_file(self, storage_service):
        """Test deleting file."""
        key = "renders/test/file.png"
        
        result = await storage_service.delete_file(key)
        
        assert result is True
        storage_service._client.delete_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, storage_service):
        """Test deleting non-existent file."""
        storage_service._client.delete_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
            "DeleteObject"
        )
        
        result = await storage_service.delete_file("nonexistent.png")
        
        # Should not raise, return False
        assert result is False

    @pytest.mark.asyncio
    async def test_file_exists_true(self, storage_service):
        """Test checking if file exists (exists)."""
        key = "renders/test/file.png"
        
        result = await storage_service.file_exists(key)
        
        assert result is True
        storage_service._client.head_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_file_exists_false(self, storage_service):
        """Test checking if file exists (not exists)."""
        storage_service._client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not found"}},
            "HeadObject"
        )
        
        result = await storage_service.file_exists("nonexistent.png")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_get_file_metadata(self, storage_service):
        """Test getting file metadata."""
        key = "renders/test/file.png"
        
        metadata = await storage_service.get_file_metadata(key)
        
        assert metadata is not None
        assert "ContentLength" in metadata
        assert "ContentType" in metadata

    @pytest.mark.asyncio
    async def test_list_files(self, storage_service):
        """Test listing files with prefix."""
        prefix = "renders/user123/"
        
        files = await storage_service.list_files(prefix)
        
        assert len(files) == 2
        storage_service._client.list_objects_v2.assert_called()

    @pytest.mark.asyncio
    async def test_generate_key(self, storage_service):
        """Test generating storage key."""
        user_id = uuid.uuid4()
        render_id = uuid.uuid4()
        
        key = storage_service.generate_key(
            user_id=str(user_id),
            render_id=str(render_id),
            file_type="screenshot",
            format="png",
        )
        
        assert str(user_id) in key
        assert str(render_id) in key
        assert key.endswith(".png")

    @pytest.mark.asyncio
    async def test_upload_large_file(self, storage_service):
        """Test uploading large file (multipart)."""
        # Create 10MB file
        large_data = b"x" * (10 * 1024 * 1024)
        key = "renders/test/large-file.png"
        
        result = await storage_service.upload_file(
            file_data=large_data,
            key=key,
            content_type="image/png",
        )
        
        assert result == key

    @pytest.mark.asyncio
    async def test_delete_files_bulk(self, storage_service):
        """Test bulk file deletion."""
        storage_service._client.delete_objects = MagicMock(return_value={
            "Deleted": [{"Key": "file1.png"}, {"Key": "file2.png"}],
        })
        
        keys = ["file1.png", "file2.png", "file3.png"]
        
        result = await storage_service.delete_files_bulk(keys)
        
        assert result["deleted"] == 2

