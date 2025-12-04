"""
Render Job model
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.api_key import APIKey
    from app.models.usage_record import UsageRecord
    from app.models.user import User


class RenderJob(BaseModel):
    """
    Render Job model for screenshot/PDF rendering tasks.

    Tracks the lifecycle of each render request.

    Attributes:
        id: UUID primary key
        user_id: Foreign key to user
        api_key_id: Foreign key to API key used
        type: Job type (screenshot, pdf)
        status: Current status (pending, processing, completed, failed, cancelled)
        url: Target URL to render
        options: JSON object with render options
        result: JSON object with output metadata
        s3_key: S3 object key for the rendered file
        s3_url: Full S3 URL
        file_size_bytes: Size of the rendered file
        processing_time_ms: Time taken to process
        error_message: Error message if failed
        retry_count: Number of retry attempts
        max_retries: Maximum retries allowed
        webhook_url: URL to notify on completion
        webhook_sent: Whether webhook was sent
        webhook_attempts: Number of webhook delivery attempts
        priority: Job priority (higher = more priority)
        created_at: Creation timestamp
        started_at: Processing start timestamp
        completed_at: Completion timestamp
        expires_at: File expiration timestamp
    """

    __tablename__ = "render_jobs"

    # Foreign keys
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    api_key_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Job type and status
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )

    # Request data
    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    options: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    # Result data
    result: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # S3 storage
    s3_key: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    s3_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    file_size_bytes: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    # Processing metrics
    processing_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )

    # Webhook
    webhook_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    webhook_sent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    webhook_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Priority
    priority: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
        index=True,
    )

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="render_jobs",
        lazy="selectin",
    )
    api_key: Mapped[Optional["APIKey"]] = relationship(
        "APIKey",
        back_populates="render_jobs",
        lazy="selectin",
    )
    usage_record: Mapped[Optional["UsageRecord"]] = relationship(
        "UsageRecord",
        back_populates="render_job",
        uselist=False,
        lazy="noload",
    )

    # Indexes
    __table_args__ = (
        Index("idx_render_jobs_user", "user_id"),
        Index("idx_render_jobs_status", "status"),
        Index("idx_render_jobs_created", "created_at"),
        Index("idx_render_jobs_type", "type"),
        Index("idx_render_jobs_priority", "priority", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<RenderJob(id={self.id}, type={self.type}, status={self.status})>"

    @property
    def is_completed(self) -> bool:
        """Check if job is completed."""
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        """Check if job has failed."""
        return self.status == "failed"

    @property
    def is_pending(self) -> bool:
        """Check if job is pending."""
        return self.status == "pending"

    @property
    def is_processing(self) -> bool:
        """Check if job is currently processing."""
        return self.status == "processing"

    @property
    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return self.retry_count < self.max_retries

    def get_queue_name(self, plan_name: str) -> str:
        """Get the Celery queue name based on plan."""
        queue_map = {
            "business": "high_priority",
            "pro": "high_priority",
            "starter": "default",
            "free": "low_priority",
        }
        return queue_map.get(plan_name, "low_priority")

