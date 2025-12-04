"""
Billing Pydantic schemas
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PlanFeatures(BaseModel):
    """Plan features."""

    watermark: bool = True
    full_page: bool = False
    custom_css: bool = False
    webhooks: bool = False
    priority_queue: bool = False
    element_selector: bool = False
    geolocation: bool = False
    custom_fonts: bool = False
    dedicated_support: bool = False


class PlanResponse(BaseModel):
    """Plan response."""

    id: int
    name: str
    display_name: str
    price_monthly: Decimal
    price_yearly: Optional[Decimal]
    requests_per_month: int
    max_concurrent_requests: int
    max_timeout_ms: int
    max_file_size_mb: int
    features: dict[str, Any]
    is_active: bool

    model_config = {"from_attributes": True}


class PlansListResponse(BaseModel):
    """List of plans response."""

    plans: list[PlanResponse]

    model_config = {"from_attributes": True}


class SubscribeRequest(BaseModel):
    """Subscription request."""

    plan_id: int = Field(..., description="Plan ID to subscribe to")
    payment_method_id: str = Field(..., description="Stripe payment method ID")
    billing_cycle: str = Field(
        default="monthly",
        description="Billing cycle (monthly or yearly)",
    )


class SubscriptionResponse(BaseModel):
    """Subscription response."""

    subscription_id: str
    status: str
    plan_id: int
    plan_name: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False

    model_config = {"from_attributes": True}


class InvoiceResponse(BaseModel):
    """Invoice response."""

    id: UUID
    stripe_invoice_id: Optional[str]
    amount: Decimal
    currency: str
    status: str
    period_start: date
    period_end: date
    paid_at: Optional[datetime]
    invoice_pdf: Optional[str] = Field(None, description="URL to download PDF")
    created_at: datetime

    model_config = {"from_attributes": True}


class InvoicesListResponse(BaseModel):
    """List of invoices response."""

    invoices: list[InvoiceResponse]
    total: int

    model_config = {"from_attributes": True}

