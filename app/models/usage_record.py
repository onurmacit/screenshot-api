"""
Usage Record model
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.api_key import APIKey
    from app.models.render_job import RenderJob
    from app.models.user import User


class UsageRecord(Base):
    """
    Usage Record model for tracking API usage.

    Records each API call for billing and analytics.

    Attributes:
        id: BigSerial primary key
        user_id: Foreign key to user
        api_key_id: Foreign key to API key used
        render_job_id: Foreign key to render job
        type: Usage type (screenshot, pdf)
        credits_used: Number of credits consumed
        extra_data: Additional metadata as JSON
        created_at: Record creation timestamp
    """

    __tablename__ = "usage_records"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

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
    render_job_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("render_jobs.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Usage data
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    credits_used: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # Additional metadata
    extra_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="usage_records",
        lazy="selectin",
    )
    api_key: Mapped[Optional["APIKey"]] = relationship(
        "APIKey",
        back_populates="usage_records",
        lazy="selectin",
    )
    render_job: Mapped[Optional["RenderJob"]] = relationship(
        "RenderJob",
        back_populates="usage_record",
        lazy="selectin",
    )

    # Indexes
    __table_args__ = (
        Index("idx_usage_user_date", "user_id", "created_at"),
        Index("idx_usage_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<UsageRecord(id={self.id}, user_id={self.user_id}, type={self.type})>"

