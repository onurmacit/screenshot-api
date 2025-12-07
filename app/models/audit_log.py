"""
Audit Log model
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(Base):
    """
    Audit Log model for tracking user actions.

    Records all significant actions for security and compliance.

    Attributes:
        id: BigSerial primary key
        user_id: Foreign key to user (nullable for anonymous actions)
        action: Action performed (e.g., "user.login", "api_key.created")
        resource_type: Type of resource affected
        resource_id: ID of the affected resource
        ip_address: Client IP address
        user_agent: Client user agent string
        extra_data: Additional metadata as JSON
        created_at: Record creation timestamp
    """

    __tablename__ = "audit_logs"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Foreign key (nullable for anonymous actions)
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Action details
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Client information
    ip_address: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Additional metadata
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
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
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="audit_logs",
        lazy="selectin",
    )

    # Indexes
    __table_args__ = (
        Index("idx_audit_user_date", "user_id", "created_at"),
        Index("idx_audit_created", "created_at"),
        Index("idx_audit_action", "action"),
    )

    # Common action types
    ACTION_USER_REGISTER = "user.register"
    ACTION_USER_LOGIN = "user.login"
    ACTION_USER_LOGOUT = "user.logout"
    ACTION_USER_UPDATE = "user.update"
    ACTION_USER_DELETE = "user.delete"

    ACTION_API_KEY_CREATE = "api_key.create"
    ACTION_API_KEY_DELETE = "api_key.delete"

    ACTION_RENDER_CREATE = "render.create"
    ACTION_RENDER_COMPLETE = "render.complete"
    ACTION_RENDER_FAIL = "render.fail"

    ACTION_WEBHOOK_CREATE = "webhook.create"
    ACTION_WEBHOOK_DELETE = "webhook.delete"
    ACTION_WEBHOOK_TRIGGER = "webhook.trigger"

    ACTION_SUBSCRIPTION_CREATE = "subscription.create"
    ACTION_SUBSCRIPTION_UPDATE = "subscription.update"
    ACTION_SUBSCRIPTION_CANCEL = "subscription.cancel"

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action})>"

