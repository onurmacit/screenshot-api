"""
User model
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.api_key import APIKey
    from app.models.audit_log import AuditLog
    from app.models.invoice import BillingInvoice
    from app.models.plan import Plan
    from app.models.rate_limit_override import RateLimitOverride
    from app.models.refresh_token import RefreshToken
    from app.models.render_job import RenderJob
    from app.models.usage_record import UsageRecord
    from app.models.webhook import Webhook


class User(BaseModel):
    """
    User model representing registered users.

    Attributes:
        id: UUID primary key
        email: Unique email address
        password_hash: Bcrypt hashed password
        full_name: User's full name (optional)
        plan_id: Foreign key to subscription plan
        stripe_customer_id: Stripe customer ID for billing
        is_active: Whether the user account is active
        email_verified: Whether the email has been verified
        created_at: Account creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "users"

    # Core fields
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Subscription
    plan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("plans.id", ondelete="SET NULL"),
        nullable=True,
        default=1,  # Default to free plan
    )

    # Stripe integration
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
    )

    # Status flags
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Relationships
    plan: Mapped[Optional["Plan"]] = relationship(
        "Plan",
        back_populates="users",
        lazy="selectin",
    )
    api_keys: Mapped[list["APIKey"]] = relationship(
        "APIKey",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    render_jobs: Mapped[list["RenderJob"]] = relationship(
        "RenderJob",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    usage_records: Mapped[list["UsageRecord"]] = relationship(
        "UsageRecord",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    invoices: Mapped[list["BillingInvoice"]] = relationship(
        "BillingInvoice",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    webhooks: Mapped[list["Webhook"]] = relationship(
        "Webhook",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    rate_limit_overrides: Mapped[list["RateLimitOverride"]] = relationship(
        "RateLimitOverride",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        lazy="noload",
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # Indexes
    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_stripe_customer", "stripe_customer_id"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"

