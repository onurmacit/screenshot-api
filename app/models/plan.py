"""
Subscription Plan model
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Plan(Base):
    """
    Subscription plan model.

    Defines different tiers with their limits and features.

    Attributes:
        id: Serial primary key
        name: Internal plan name (free, starter, pro, business)
        display_name: Human-readable name
        price_monthly: Monthly price in USD
        price_yearly: Yearly price in USD (optional)
        requests_per_month: Monthly request limit
        max_concurrent_requests: Maximum concurrent requests
        max_timeout_ms: Maximum render timeout in milliseconds
        max_file_size_mb: Maximum file size in MB
        features: JSON object with feature flags
        stripe_price_id: Stripe price ID for billing
        is_active: Whether the plan is available for new subscriptions
        created_at: Plan creation timestamp
    """

    __tablename__ = "plans"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Plan identification
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Pricing
    price_monthly: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    price_yearly: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Limits
    requests_per_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    max_concurrent_requests: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )
    max_timeout_ms: Mapped[int] = mapped_column(
        Integer,
        default=30000,
        nullable=False,
    )
    max_file_size_mb: Mapped[int] = mapped_column(
        Integer,
        default=50,
        nullable=False,
    )

    # Features (JSON object)
    features: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )

    # Stripe integration
    stripe_price_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="plan",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Plan(id={self.id}, name={self.name})>"

    @property
    def rate_limits(self) -> dict[str, int]:
        """Get rate limits based on plan tier."""
        limits = {
            "free": {"per_minute": 10, "per_hour": 100, "per_day": 200, "burst": 5},
            "starter": {"per_minute": 30, "per_hour": 500, "per_day": 2000, "burst": 10},
            "pro": {"per_minute": 100, "per_hour": 2000, "per_day": 10000, "burst": 50},
            "business": {"per_minute": 500, "per_hour": 10000, "per_day": 50000, "burst": 200},
        }
        return limits.get(self.name, limits["free"])

    def has_feature(self, feature_name: str) -> bool:
        """Check if plan has a specific feature."""
        if not self.features:
            return False
        return self.features.get(feature_name, False)

