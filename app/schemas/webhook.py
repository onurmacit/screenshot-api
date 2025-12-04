"""
Webhook Pydantic schemas
"""

from datetime import datetime
from typing import Optional
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

    url: Optional[str] = None
    events: Optional[list[str]] = None
    is_active: Optional[bool] = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate webhook URL."""
        if v and not v.startswith("https://"):
            raise ValueError("Webhook URL must use HTTPS")
        return v


class WebhookResponse(BaseModel):
    """Webhook response."""

    webhook_id: UUID
    url: str
    secret: Optional[str] = Field(None, description="Only returned on creation")
    events: list[str]
    is_active: bool
    last_triggered_at: Optional[datetime]
    failure_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhooksListResponse(BaseModel):
    """List of webhooks response."""

    webhooks: list[WebhookResponse]

    model_config = {"from_attributes": True}


class WebhookPayload(BaseModel):
    """Webhook delivery payload."""

    event: str
    timestamp: datetime
    data: dict

    model_config = {"from_attributes": True}

