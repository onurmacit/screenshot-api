"""
Storage Service

Handles S3 file operations for storing rendered screenshots and PDFs.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.core.config import settings
from app.core.s3 import S3Manager, get_s3_client
from app.utils.helpers import get_content_type, get_file_extension
from app.utils.logger import get_logger

logger = get_logger(__name__)


class StorageService:
    """Service for S3 storage operations."""

    def __init__(self):
        self.s3 = S3Manager()
        self.bucket = settings.AWS_S3_BUCKET

    async def upload_render(
        self,
        file_bytes: bytes,
        user_id: str,
        job_id: str,
        file_type: str,
        metadata: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """
        Upload rendered file to S3.

        Args:
            file_bytes: File content as bytes
            user_id: User UUID string
            job_id: Job UUID string
            file_type: File type (png, jpeg, webp, pdf)
            metadata: Additional metadata

        Returns:
            Dict with s3_key, s3_url, file_size
        """
        # Generate S3 key
        extension = get_file_extension(file_type)
        s3_key = self.s3.generate_key(user_id, job_id, extension)

        # Content type
        content_type = get_content_type(file_type)

        # Build metadata
        upload_metadata = {
            "user-id": user_id,
            "job-id": job_id,
            "file-type": file_type,
            "created-at": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            upload_metadata.update(metadata)

        # Upload to S3
        result = await self.s3.upload_file(
            file_bytes=file_bytes,
            key=s3_key,
            content_type=content_type,
            metadata=upload_metadata,
        )

        logger.info(
            "File uploaded to S3",
            s3_key=s3_key,
            file_size=len(file_bytes),
            user_id=user_id,
            job_id=job_id,
        )

        return {
            "s3_key": result["s3_key"],
            "s3_url": result["s3_url"],
            "file_size": len(file_bytes),
        }

    async def generate_download_url(
        self,
        s3_key: str,
        expires_in: Optional[int] = None,
    ) -> str:
        """
        Generate a presigned URL for downloading a file.

        Args:
            s3_key: S3 object key
            expires_in: URL expiration in seconds (default from settings)

        Returns:
            Presigned URL string
        """
        if expires_in is None:
            expires_in = settings.SIGNED_URL_EXPIRY_SECONDS

        url = await self.s3.generate_presigned_url(s3_key, expires_in)

        logger.debug(
            "Generated presigned URL",
            s3_key=s3_key,
            expires_in=expires_in,
        )

        return url

    async def delete_file(self, s3_key: str) -> bool:
        """
        Delete a file from S3.

        Args:
            s3_key: S3 object key

        Returns:
            True if deleted
        """
        result = await self.s3.delete_file(s3_key)

        logger.info("File deleted from S3", s3_key=s3_key)

        return result

    async def delete_files(self, s3_keys: list[str]) -> int:
        """
        Delete multiple files from S3.

        Args:
            s3_keys: List of S3 object keys

        Returns:
            Number of deleted files
        """
        if not s3_keys:
            return 0

        deleted_count = await self.s3.delete_files(s3_keys)

        logger.info(
            "Files deleted from S3",
            count=deleted_count,
            total=len(s3_keys),
        )

        return deleted_count

    async def get_file_info(self, s3_key: str) -> Optional[dict[str, Any]]:
        """
        Get file metadata from S3.

        Args:
            s3_key: S3 object key

        Returns:
            File metadata dict or None if not found
        """
        return await self.s3.get_file_metadata(s3_key)

    async def file_exists(self, s3_key: str) -> bool:
        """
        Check if a file exists in S3.

        Args:
            s3_key: S3 object key

        Returns:
            True if file exists
        """
        return await self.s3.file_exists(s3_key)

    async def cleanup_expired_files(
        self,
        expired_keys: list[str],
    ) -> dict[str, Any]:
        """
        Clean up expired render files.

        Args:
            expired_keys: List of S3 keys to delete

        Returns:
            Cleanup statistics
        """
        if not expired_keys:
            return {"deleted": 0, "errors": 0}

        deleted = 0
        errors = 0

        # Process in batches of 1000 (S3 limit)
        batch_size = 1000
        for i in range(0, len(expired_keys), batch_size):
            batch = expired_keys[i : i + batch_size]
            try:
                count = await self.delete_files(batch)
                deleted += count
            except Exception as e:
                logger.error(
                    "Error deleting batch",
                    batch_start=i,
                    error=str(e),
                )
                errors += len(batch)

        logger.info(
            "Cleanup completed",
            deleted=deleted,
            errors=errors,
            total=len(expired_keys),
        )

        return {
            "deleted": deleted,
            "errors": errors,
            "total": len(expired_keys),
        }

    def calculate_expiry_date(self, days: Optional[int] = None) -> datetime:
        """
        Calculate file expiry date.

        Args:
            days: Number of days until expiry (default from settings)

        Returns:
            Expiry datetime
        """
        if days is None:
            days = settings.RENDER_EXPIRY_DAYS

        return datetime.now(timezone.utc) + timedelta(days=days)


# Global storage service instance
storage_service = StorageService()

