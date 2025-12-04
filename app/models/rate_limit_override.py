"""
Rate Limit Override model
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class RateLimitOverride(Base):
    """
    Rate Limit Override model for custom user limits.

    Allows setting custom rate limits for specific users (enterprise, promotions).

    Attributes:
        id: Serial primary key
        user_id: Foreign key to user (unique)
        requests_per_minute: Custom per-minute limit
        requests_per_hour: Custom per-hour limit
        requests_per_day: Custom per-day limit
        burst_limit: Custom burst allowance
        reason: Reason for the override
        expires_at: Override expiration timestamp
        created_at: Creation timestamp
    """

    __tablename__ = "rate_limit_overrides"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Foreign key (unique - one override per user)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Custom limits (nullable - if null, use plan defaults)
    requests_per_minute: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    requests_per_hour: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    requests_per_day: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    burst_limit: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Documentation
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Expiration
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="rate_limit_overrides",
        lazy="selectin",
    )

    # Indexes
    __table_args__ = (
        Index("idx_rate_overrides_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<RateLimitOverride(id={self.id}, user_id={self.user_id})>"

    @property
    def is_expired(self) -> bool:
        """Check if the override has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def is_active(self) -> bool:
        """Check if the override is currently active."""
        return not self.is_expired

    def get_effective_limits(self, plan_limits: dict[str, int]) -> dict[str, int]:
        """
        Get effective rate limits with override applied.

        Args:
            plan_limits: Default limits from user's plan

        Returns:
            Dict with effective limits
        """
        if self.is_expired:
            return plan_limits

        return {
            "per_minute": self.requests_per_minute or plan_limits.get("per_minute", 10),
            "per_hour": self.requests_per_hour or plan_limits.get("per_hour", 100),
            "per_day": self.requests_per_day or plan_limits.get("per_day", 200),
            "burst": self.burst_limit or plan_limits.get("burst", 5),
        }

