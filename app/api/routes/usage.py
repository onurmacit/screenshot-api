"""
Usage tracking endpoints
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import APIKeyUser, DBSession, JWTUser
from app.models import Plan, RenderJob, UsageRecord
from app.schemas.usage import (
    CurrentUsageResponse,
    DailyUsage,
    PlanInfo,
    RateLimitInfo,
    UsageHistoryResponse,
    UsageInfo,
)
from app.services.rate_limit_service import RATE_LIMITS, rate_limit_service
from app.utils.helpers import utc_now

router = APIRouter()


@router.get(
    "/current",
    response_model=CurrentUsageResponse,
    summary="Get current usage",
    description="Get current usage for the billing period.",
)
async def get_current_usage(
    current_user: APIKeyUser,
    db: DBSession,
) -> CurrentUsageResponse:
    """
    Get current usage statistics.

    **Requires API key authentication.**

    Returns:
    - Current billing period
    - Plan details
    - Usage counts and limits
    - Rate limit status
    """
    # Get current month period
    now = utc_now()
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 12:
        period_end = period_start.replace(year=now.year + 1, month=1)
    else:
        period_end = period_start.replace(month=now.month + 1)

    # Get plan info
    plan_info = PlanInfo(
        id=current_user.plan_id or 1,
        name=current_user.plan_name,
        display_name=current_user.plan_name.title(),
        requests_per_month=RATE_LIMITS.get(current_user.plan_name, RATE_LIMITS["free"])["per_month"],
    )

    # Get usage from rate limit service
    all_usage = await rate_limit_service.get_all_usage(
        user_id=current_user.user_id,
        plan_name=current_user.plan_name,
    )

    monthly_usage = all_usage["per_month"]["used"]
    monthly_limit = all_usage["per_month"]["limit"]
    percentage = (monthly_usage / monthly_limit * 100) if monthly_limit > 0 else 0

    usage_info = UsageInfo(
        requests_used=monthly_usage,
        requests_limit=monthly_limit,
        percentage=min(100, round(percentage, 2)),
    )

    # Build rate limit info
    rate_limits = {
        "per_minute": RateLimitInfo(
            used=all_usage["per_minute"]["used"],
            limit=all_usage["per_minute"]["limit"],
            remaining=all_usage["per_minute"]["remaining"],
        ),
        "per_hour": RateLimitInfo(
            used=all_usage["per_hour"]["used"],
            limit=all_usage["per_hour"]["limit"],
            remaining=all_usage["per_hour"]["remaining"],
        ),
    }

    # Calculate next reset (next minute)
    next_reset = now.replace(second=0, microsecond=0) + timedelta(minutes=1)

    return CurrentUsageResponse(
        period=f"{period_start.strftime('%Y-%m')}",
        period_start=period_start,
        period_end=period_end,
        plan=plan_info,
        usage=usage_info,
        rate_limits=rate_limits,
        next_reset=next_reset,
    )


@router.get(
    "/history",
    response_model=UsageHistoryResponse,
    summary="Get usage history",
    description="Get historical usage data.",
)
async def get_usage_history(
    current_user: JWTUser,
    db: DBSession,
    start_date: Optional[str] = Query(
        None,
        description="Start date (ISO format: YYYY-MM-DD)",
    ),
    end_date: Optional[str] = Query(
        None,
        description="End date (ISO format: YYYY-MM-DD)",
    ),
    granularity: str = Query(
        "day",
        description="Aggregation granularity (day, week, month)",
    ),
) -> UsageHistoryResponse:
    """
    Get usage history.

    **Requires JWT authentication.**

    - **start_date**: Start date (defaults to 30 days ago)
    - **end_date**: End date (defaults to today)
    - **granularity**: Aggregation level (day, week, month)
    """
    now = utc_now()

    # Parse dates
    if start_date:
        start = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
    else:
        start = now - timedelta(days=30)

    if end_date:
        end = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
    else:
        end = now

    # Ensure end is after start
    if end < start:
        start, end = end, start

    # Query usage records grouped by date
    if granularity == "month":
        date_trunc = func.date_trunc("month", RenderJob.created_at)
    elif granularity == "week":
        date_trunc = func.date_trunc("week", RenderJob.created_at)
    else:
        date_trunc = func.date_trunc("day", RenderJob.created_at)

    query = (
        select(
            date_trunc.label("date"),
            func.count(RenderJob.id).label("total"),
            func.count(RenderJob.id).filter(RenderJob.type == "screenshot").label("screenshots"),
            func.count(RenderJob.id).filter(RenderJob.type == "pdf").label("pdfs"),
            func.coalesce(func.sum(RenderJob.processing_time_ms), 0).label("processing_time"),
            func.coalesce(func.sum(RenderJob.file_size_bytes), 0).label("file_size"),
        )
        .where(
            RenderJob.user_id == current_user.user_id,
            RenderJob.created_at >= start,
            RenderJob.created_at <= end,
            RenderJob.status == "completed",
        )
        .group_by(date_trunc)
        .order_by(date_trunc)
    )

    result = await db.execute(query)
    rows = result.all()

    # Build usage list
    usage_data = []
    total_requests = 0
    total_processing_time = 0
    total_file_size = 0

    for row in rows:
        usage_data.append(
            DailyUsage(
                date=row.date.strftime("%Y-%m-%d"),
                requests=row.total,
                screenshots=row.screenshots,
                pdfs=row.pdfs,
                total_processing_time_ms=row.processing_time,
                total_file_size_bytes=row.file_size,
            )
        )
        total_requests += row.total
        total_processing_time += row.processing_time
        total_file_size += row.file_size

    return UsageHistoryResponse(
        start_date=start.strftime("%Y-%m-%d"),
        end_date=end.strftime("%Y-%m-%d"),
        granularity=granularity,
        usage=usage_data,
        total_requests=total_requests,
        total_processing_time_ms=total_processing_time,
        total_file_size_bytes=total_file_size,
    )
