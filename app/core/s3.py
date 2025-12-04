"""
AWS S3 / MinIO client configuration
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator

import aioboto3
from botocore.config import Config

from app.core.config import settings

# Boto3 configuration
_boto_config = Config(
    region_name=settings.AWS_REGION,
    signature_version="s3v4",
    retries={"max_attempts": 3, "mode": "standard"},
)

# Session for async operations
_session: aioboto3.Session | None = None


def get_session() -> aioboto3.Session:
    """Get or create aioboto3 session."""
    global _session
    if _session is None:
        _session = aioboto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
    return _session


@asynccontextmanager
async def get_s3_client() -> AsyncGenerator[Any, None]:
    """
    Get async S3 client.

    Yields:
        S3 client
    """
    session = get_session()

    client_kwargs: dict[str, Any] = {
        "config": _boto_config,
    }

    # For MinIO or other S3-compatible storage
    if settings.AWS_S3_ENDPOINT_URL:
        client_kwargs["endpoint_url"] = settings.AWS_S3_ENDPOINT_URL

    async with session.client("s3", **client_kwargs) as client:
        yield client


@asynccontextmanager
async def get_s3_resource() -> AsyncGenerator[Any, None]:
    """
    Get async S3 resource.

    Yields:
        S3 resource
    """
    session = get_session()

    resource_kwargs: dict[str, Any] = {
        "config": _boto_config,
    }

    if settings.AWS_S3_ENDPOINT_URL:
        resource_kwargs["endpoint_url"] = settings.AWS_S3_ENDPOINT_URL

    async with session.resource("s3", **resource_kwargs) as resource:
        yield resource


class S3Manager:
    """
    S3 operations manager.
    """

    def __init__(self, bucket: str | None = None):
        self.bucket = bucket or settings.AWS_S3_BUCKET

    def generate_key(
        self,
        user_id: str,
        job_id: str,
        extension: str,
    ) -> str:
        """
        Generate S3 key for a render output.

        Format: renders/{user_id}/{year}/{month}/{day}/{job_id}.{ext}

        Args:
            user_id: User UUID
            job_id: Job UUID
            extension: File extension (png, jpeg, webp, pdf)

        Returns:
            S3 key string
        """
        now = datetime.utcnow()
        return (
            f"renders/{user_id}/{now.year:04d}/{now.month:02d}/"
            f"{now.day:02d}/{job_id}.{extension}"
        )

    async def upload_file(
        self,
        file_bytes: bytes,
        key: str,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Upload file to S3.

        Args:
            file_bytes: File content as bytes
            key: S3 object key
            content_type: MIME content type
            metadata: Optional metadata dict

        Returns:
            Dict with s3_key and s3_url
        """
        async with get_s3_client() as client:
            extra_args: dict[str, Any] = {
                "ContentType": content_type,
                "CacheControl": "public, max-age=31536000",
            }

            if metadata:
                extra_args["Metadata"] = metadata

            await client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=file_bytes,
                **extra_args,
            )

        s3_url = self._get_object_url(key)

        return {
            "s3_key": key,
            "s3_url": s3_url,
        }

    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int | None = None,
    ) -> str:
        """
        Generate a presigned URL for downloading.

        Args:
            key: S3 object key
            expires_in: URL expiration in seconds

        Returns:
            Presigned URL string
        """
        if expires_in is None:
            expires_in = settings.SIGNED_URL_EXPIRY_SECONDS

        async with get_s3_client() as client:
            url = await client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": key,
                },
                ExpiresIn=expires_in,
            )

        return url

    async def delete_file(self, key: str) -> bool:
        """
        Delete file from S3.

        Args:
            key: S3 object key

        Returns:
            True if deleted successfully
        """
        async with get_s3_client() as client:
            await client.delete_object(
                Bucket=self.bucket,
                Key=key,
            )
        return True

    async def delete_files(self, keys: list[str]) -> int:
        """
        Delete multiple files from S3.

        Args:
            keys: List of S3 object keys

        Returns:
            Number of deleted files
        """
        if not keys:
            return 0

        async with get_s3_client() as client:
            response = await client.delete_objects(
                Bucket=self.bucket,
                Delete={
                    "Objects": [{"Key": key} for key in keys],
                    "Quiet": True,
                },
            )

        return len(keys) - len(response.get("Errors", []))

    async def get_file_metadata(self, key: str) -> dict[str, Any] | None:
        """
        Get file metadata from S3.

        Args:
            key: S3 object key

        Returns:
            Metadata dict or None if not found
        """
        async with get_s3_client() as client:
            try:
                response = await client.head_object(
                    Bucket=self.bucket,
                    Key=key,
                )
                return {
                    "size": response.get("ContentLength"),
                    "content_type": response.get("ContentType"),
                    "last_modified": response.get("LastModified"),
                    "metadata": response.get("Metadata", {}),
                }
            except Exception:
                return None

    async def file_exists(self, key: str) -> bool:
        """
        Check if file exists in S3.

        Args:
            key: S3 object key

        Returns:
            True if file exists
        """
        return await self.get_file_metadata(key) is not None

    def _get_object_url(self, key: str) -> str:
        """Get the base URL for an S3 object."""
        if settings.AWS_S3_ENDPOINT_URL:
            return f"{settings.AWS_S3_ENDPOINT_URL}/{self.bucket}/{key}"
        return f"https://{self.bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"


# Global S3 manager instance
s3_manager = S3Manager()

