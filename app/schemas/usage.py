"""
Usage tracking Pydantic schemas
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RateLimitInfo(BaseModel):
    """Rate limit information."""

    used: int
    limit: int
    remaining: int = Field(default=0)


class UsageInfo(BaseModel):
    """Usage information."""

    requests_used: int
    requests_limit: int
    percentage: float = Field(..., ge=0, le=100)


class PlanInfo(BaseModel):
    """Plan information."""

    id: int
    name: str
    display_name: str
    requests_per_month: int


class CurrentUsageResponse(BaseModel):
    """Current usage response."""

    period: str = Field(..., description="Current billing period")
    period_start: datetime
    period_end: datetime
    plan: PlanInfo
    usage: UsageInfo
    rate_limits: dict[str, RateLimitInfo] = Field(
        default_factory=dict,
        description="Rate limit status by window",
    )
    next_reset: datetime = Field(..., description="Next rate limit reset time")

    model_config = {"from_attributes": True}


class DailyUsage(BaseModel):
    """Daily usage statistics."""

    date: str = Field(..., description="Date in ISO format")
    requests: int
    screenshots: int = 0
    pdfs: int = 0
    total_processing_time_ms: int = 0
    total_file_size_bytes: int = 0


class UsageHistoryResponse(BaseModel):
    """Usage history response."""

    start_date: str
    end_date: str
    granularity: str = Field(..., description="Aggregation granularity (day, week, month)")
    usage: list[DailyUsage]
    total_requests: int
    total_processing_time_ms: int
    total_file_size_bytes: int

    model_config = {"from_attributes": True}

