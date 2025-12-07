"""
Webhook Pydantic schemas
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class WebhookCreate(BaseModel):
    """Webhook creation request."""

    url: str = Field(..., description="Webhook endpoint URL (HTTPS only)")
    events: list[str] = Field(..., description="Events to subscribe to")
    is_active: bool = Field(default=True, description="Whether webhook is active")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate webhook URL."""
        if not v.startswith("https://"):
            raise ValueError("Webhook URL must use HTTPS")
        return v

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str]) -> list[str]:
        """Validate webhook events."""
        allowed_events = {
            "job.completed",
            "job.failed",
            "usage.limit_reached",
            "usage.limit_warning",
        }
        for event in v:
            if event not in allowed_events:
                raise ValueError(f"Invalid event: {event}")
        return v


class WebhookUpdate(BaseModel):
    """Webhook update request."""

    url: str | None = None
    events: list[str] | None = None
    is_active: bool | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        """Validate webhook URL."""
        if v and not v.startswith("https://"):
            raise ValueError("Webhook URL must use HTTPS")
        return v


class WebhookResponse(BaseModel):
    """Webhook response."""

    webhook_id: UUID
    url: str
    secret: str | None = Field(None, description="Only returned on creation")
    events: list[str]
    is_active: bool
    last_triggered_at: datetime | None
    failure_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhooksListResponse(BaseModel):
    """List of webhooks response."""

    webhooks: list[WebhookResponse]

    model_config = {"from_attributes": True}


class WebhookSecretResponse(BaseModel):
    """Webhook secret response (after rotation)."""

    webhook_id: UUID
    secret: str = Field(..., description="New webhook secret. Save it securely!")

    model_config = {"from_attributes": True}


class WebhookVerifyRequest(BaseModel):
    """Request to verify webhook signature."""

    payload: str = Field(..., description="The raw JSON payload string")
    signature: str = Field(..., description="The signature from X-Webhook-Signature header")
    secret: str = Field(..., description="Your webhook secret")


class WebhookVerifyResponse(BaseModel):
    """Response from signature verification."""

    valid: bool = Field(..., description="Whether the signature is valid")
    message: str = Field(..., description="Verification result message")


class WebhookPayload(BaseModel):
    """Webhook delivery payload."""

    event: str
    timestamp: datetime
    data: dict

    model_config = {"from_attributes": True}


class WebhookDeliveryInfo(BaseModel):
    """Information about a webhook delivery attempt."""

    webhook_id: UUID
    event: str
    status_code: int | None = None
    success: bool
    attempt: int
    error: str | None = None
    delivered_at: datetime

    model_config = {"from_attributes": True}
