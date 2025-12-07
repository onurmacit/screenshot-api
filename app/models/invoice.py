"""
Billing Invoice model
"""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class BillingInvoice(BaseModel):
    """
    Billing Invoice model for tracking payments.

    Stores invoice records synced with Stripe.

    Attributes:
        id: UUID primary key
        user_id: Foreign key to user
        stripe_invoice_id: Stripe invoice ID
        amount: Invoice amount
        currency: Currency code (USD)
        status: Invoice status (draft, open, paid, uncollectible, void)
        period_start: Billing period start date
        period_end: Billing period end date
        paid_at: Payment timestamp
        created_at: Creation timestamp
    """

    __tablename__ = "billing_invoices"

    # Foreign key
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Stripe integration
    stripe_invoice_id: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
    )

    # Amount
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # Billing period
    period_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    # Payment timestamp
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="invoices",
        lazy="selectin",
    )

    # Indexes
    __table_args__ = (
        Index("idx_invoices_user", "user_id"),
        Index("idx_invoices_stripe", "stripe_invoice_id"),
    )

    # Invoice statuses
    STATUS_DRAFT = "draft"
    STATUS_OPEN = "open"
    STATUS_PAID = "paid"
    STATUS_UNCOLLECTIBLE = "uncollectible"
    STATUS_VOID = "void"

    def __repr__(self) -> str:
        return f"<BillingInvoice(id={self.id}, amount={self.amount}, status={self.status})>"

    @property
    def is_paid(self) -> bool:
        """Check if invoice is paid."""
        return self.status == self.STATUS_PAID

