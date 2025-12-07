"""
Webhook model
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class Webhook(BaseModel):
    """
    Webhook model for notification endpoints.

    Stores user-configured webhook endpoints for event notifications.

    Attributes:
        id: UUID primary key
        user_id: Foreign key to user
        url: Webhook endpoint URL
        secret: Secret for HMAC signature verification
        events: Array of subscribed events
        is_active: Whether the webhook is active
        last_triggered_at: Last successful trigger timestamp
        failure_count: Consecutive failure count
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "webhooks"

    # Foreign key
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Webhook configuration
    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    secret: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Subscribed events
    events: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Tracking
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    failure_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="webhooks",
        lazy="selectin",
    )

    # Indexes
    __table_args__ = (
        Index("idx_webhooks_user", "user_id"),
    )

    # Available webhook events
    AVAILABLE_EVENTS = [
        "job.completed",
        "job.failed",
        "usage.limit_reached",
        "usage.limit_warning",
    ]

    def __repr__(self) -> str:
        return f"<Webhook(id={self.id}, url={self.url[:50]}...)>"

    def is_subscribed_to(self, event: str) -> bool:
        """Check if webhook is subscribed to a specific event."""
        return event in self.events

    def should_disable(self, max_failures: int = 10) -> bool:
        """Check if webhook should be disabled due to failures."""
        return self.failure_count >= max_failures

