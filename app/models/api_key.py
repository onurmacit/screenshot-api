"""
API Key model
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.render_job import RenderJob
    from app.models.usage_record import UsageRecord
    from app.models.user import User


class APIKey(BaseModel):
    """
    API Key model for authentication.

    Dual-key system (ScreenshotOne parity):
    - access_key: Public identifier, safe to share in URLs
    - secret_key_encrypted: Private key for HMAC signing (encrypted at rest)

    Attributes:
        id: UUID primary key
        user_id: Foreign key to user
        access_key: Public access key (e.g., ak_xxx)
        secret_key_encrypted: Encrypted secret key for signing
        enforce_signing: If True, all requests must be signed
        key_hash: (Legacy) SHA256 hash of the old single API key
        key_prefix: (Legacy) First 8 characters for identification
        name: User-provided name for the key
        scopes: Array of permission scopes
        last_used_at: Last usage timestamp
        is_active: Whether the key is active
        is_legacy: True for old-style keys, False for dual-key
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

    # === NEW DUAL-KEY SYSTEM ===
    # Public access key (safe to share in URLs)
    access_key: Mapped[str | None] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=True,  # Nullable for legacy keys
    )
    # Private secret key (encrypted at rest)
    secret_key_encrypted: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,  # Nullable for legacy keys
    )
    # Security: Require signature for all requests
    enforce_signing: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # === LEGACY KEY SYSTEM (Deprecated) ===
    key_hash: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,  # Changed to nullable for new keys
        index=True,
    )
    key_prefix: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,  # Changed to nullable for new keys
        index=True,
    )
    is_legacy: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # === COMMON FIELDS ===
    name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Permissions
    scopes: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
        default=list,
    )

    # Usage tracking
    last_used_at: Mapped[datetime | None] = mapped_column(
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
    expires_at: Mapped[datetime | None] = mapped_column(
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
        Index("idx_api_keys_access_key", "access_key"),
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

