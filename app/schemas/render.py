"""
Render request/response Pydantic schemas
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ScreenshotRequest(BaseModel):
    """Screenshot render request."""

    url: str = Field(..., description="URL to capture (HTTPS only)")
    async_mode: bool = Field(
        default=False,
        alias="async",
        description="Process asynchronously",
    )
    webhook_url: Optional[str] = Field(
        None,
        description="Webhook URL for async notifications",
    )

    # Viewport options
    width: int = Field(default=1920, ge=320, le=3840, description="Viewport width")
    height: int = Field(default=1080, ge=240, le=2160, description="Viewport height")
    full_page: bool = Field(default=False, description="Capture full page")

    # Image options
    format: str = Field(default="png", description="Output format (png, jpeg, webp)")
    quality: int = Field(default=90, ge=1, le=100, description="Image quality (for jpeg)")

    # Timing options
    delay: int = Field(default=0, ge=0, le=10000, description="Delay in ms before capture")
    wait_until: str = Field(
        default="networkidle",
        description="Wait condition (load, domcontentloaded, networkidle)",
    )

    # Advanced options (plan-gated)
    custom_css: Optional[str] = Field(None, description="Custom CSS to inject (pro+)")
    element_selector: Optional[str] = Field(None, description="Element to capture (pro+)")
    remove_elements: Optional[list[str]] = Field(None, description="Selectors to remove")
    geolocation: Optional[dict[str, float]] = Field(
        None,
        description="Geolocation {lat, lon} (pro+)",
    )

    # Browser options
    device: Optional[str] = Field(
        None,
        description="Device emulation (mobile, tablet, desktop)",
    )
    user_agent: Optional[str] = Field(None, description="Custom user agent")
    extra_http_headers: Optional[dict[str, str]] = Field(None, description="Extra headers")
    authentication: Optional[dict[str, str]] = Field(
        None,
        description="HTTP auth {username, password}",
    )

    # Caching
    cache: bool = Field(default=False, description="Use cached version if available")
    cache_ttl: int = Field(default=3600, ge=60, le=86400, description="Cache TTL in seconds")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format and protocol."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        if len(v) > 2048:
            raise ValueError("URL must be less than 2048 characters")
        return v

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate image format."""
        allowed = {"png", "jpeg", "jpg", "webp"}
        if v.lower() not in allowed:
            raise ValueError(f"Format must be one of: {', '.join(allowed)}")
        return v.lower()

    @field_validator("wait_until")
    @classmethod
    def validate_wait_until(cls, v: str) -> str:
        """Validate wait_until value."""
        allowed = {"load", "domcontentloaded", "networkidle"}
        if v.lower() not in allowed:
            raise ValueError(f"wait_until must be one of: {', '.join(allowed)}")
        return v.lower()

    model_config = {"populate_by_name": True}


class PDFRequest(BaseModel):
    """PDF render request."""

    url: str = Field(..., description="URL to render (HTTPS only)")
    async_mode: bool = Field(
        default=False,
        alias="async",
        description="Process asynchronously",
    )
    webhook_url: Optional[str] = Field(
        None,
        description="Webhook URL for async notifications",
    )

    # PDF options
    format: str = Field(default="A4", description="Page format (A4, Letter, Legal, Tabloid)")
    landscape: bool = Field(default=False, description="Landscape orientation")
    print_background: bool = Field(default=True, description="Print background graphics")
    scale: float = Field(default=1.0, ge=0.1, le=2.0, description="Scale factor")

    # Margin options (in mm)
    margin: Optional[dict[str, str]] = Field(
        None,
        description="Margins {top, right, bottom, left}",
    )

    # Page options
    page_ranges: Optional[str] = Field(None, description="Page ranges (e.g., '1-5,8-11')")
    prefer_css_page_size: bool = Field(default=False, description="Use CSS page size")

    # Header/Footer
    header_template: Optional[str] = Field(None, description="Header HTML template")
    footer_template: Optional[str] = Field(None, description="Footer HTML template")

    # Timing
    delay: int = Field(default=0, ge=0, le=10000, description="Delay in ms before render")
    wait_until: str = Field(default="networkidle", description="Wait condition")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate PDF format."""
        allowed = {"a4", "letter", "legal", "tabloid"}
        if v.lower() not in allowed:
            raise ValueError(f"Format must be one of: {', '.join(allowed)}")
        return v.upper()

    model_config = {"populate_by_name": True}


class SizeInfo(BaseModel):
    """Image size information."""

    width: int
    height: int


class RenderJobResponse(BaseModel):
    """Render job response."""

    job_id: UUID
    type: str
    status: str
    url: Optional[str] = Field(None, description="S3 signed URL (if completed)")
    format: Optional[str] = None
    size: Optional[SizeInfo] = None
    file_size: Optional[int] = Field(None, description="File size in bytes")
    page_count: Optional[int] = Field(None, description="PDF page count")
    processing_time_ms: Optional[int] = None
    cached: bool = False
    error_message: Optional[str] = None
    options: Optional[dict[str, Any]] = None
    result: Optional[dict[str, Any]] = None
    webhook_url: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RenderJobAsyncResponse(BaseModel):
    """Async render job response."""

    job_id: UUID
    status: str = "pending"
    message: str = "Job queued successfully"
    webhook_url: Optional[str] = None
    check_url: str = Field(..., description="URL to check job status")

    model_config = {"from_attributes": True}


class RenderJobsListResponse(BaseModel):
    """List of render jobs response."""

    jobs: list[RenderJobResponse]
    total: int
    limit: int
    offset: int

    model_config = {"from_attributes": True}

