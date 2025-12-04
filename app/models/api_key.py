"""
API Key model
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.render_job import RenderJob
    from app.models.usage_record import UsageRecord
    from app.models.user import User


class APIKey(BaseModel):
    """
    API Key model for authentication.

    Stores hashed API keys with their associated metadata.

    Attributes:
        id: UUID primary key
        user_id: Foreign key to user
        key_hash: SHA256 hash of the full API key
        key_prefix: First 8 characters for identification
        name: User-provided name for the key
        scopes: Array of permission scopes
        last_used_at: Last usage timestamp
        is_active: Whether the key is active
        created_at: Creation timestamp
        expires_at: Expiration timestamp (optional)
    """

    __tablename__ = "api_keys"

    # Foreign key
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Key data
    key_hash: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    key_prefix: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Permissions
    scopes: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
        default=list,
    )

    # Usage tracking
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Expiration
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="api_keys",
        lazy="selectin",
    )
    render_jobs: Mapped[list["RenderJob"]] = relationship(
        "RenderJob",
        back_populates="api_key",
        lazy="noload",
    )
    usage_records: Mapped[list["UsageRecord"]] = relationship(
        "UsageRecord",
        back_populates="api_key",
        lazy="noload",
    )

    # Indexes
    __table_args__ = (
        Index("idx_api_keys_user", "user_id"),
        Index("idx_api_keys_hash", "key_hash"),
        Index("idx_api_keys_prefix", "key_prefix"),
    )

    def __repr__(self) -> str:
        return f"<APIKey(id={self.id}, prefix={self.key_prefix}...)>"

    @property
    def is_expired(self) -> bool:
        """Check if the API key has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if the API key is valid (active and not expired)."""
        return self.is_active and not self.is_expired

    def has_scope(self, scope: str) -> bool:
        """Check if the API key has a specific scope."""
        if not self.scopes:
            return False
        return scope in self.scopes

