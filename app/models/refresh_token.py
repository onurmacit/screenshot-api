"""
Refresh Token model
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class RefreshToken(BaseModel):
    """
    Refresh Token model for JWT token rotation.

    Stores refresh tokens for secure token rotation and revocation.

    Attributes:
        id: UUID primary key
        user_id: Foreign key to user
        token_hash: SHA256 hash of the refresh token
        device_info: Information about the client device
        ip_address: IP address used when token was issued
        is_revoked: Whether the token has been revoked
        expires_at: Token expiration timestamp
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "refresh_tokens"

    # Foreign key
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Token data
    token_hash: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    # Client information
    device_info: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
    )

    # Status
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Expiration
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="refresh_tokens",
        lazy="selectin",
    )

    # Indexes
    __table_args__ = (
        Index("idx_refresh_tokens_user", "user_id"),
        Index("idx_refresh_tokens_hash", "token_hash"),
        Index("idx_refresh_tokens_expires", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id}, user_id={self.user_id})>"

    @property
    def is_expired(self) -> bool:
        """Check if the token has expired."""
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if the token is valid (not revoked and not expired)."""
        return not self.is_revoked and not self.is_expired

