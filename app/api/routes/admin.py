"""
Admin API routes

Provides endpoints for admin users to view all users, API keys, and render jobs.
Only accessible to users with admin email addresses.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.dependencies import CurrentUser, DBSession, JWTUser
from app.core.config import settings
from app.models import APIKey, RenderJob, User
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# =============================================================================
# Admin Check Dependency
# =============================================================================

async def require_admin(current_user: JWTUser) -> CurrentUser:
    """Verify the current user is an admin."""
    if current_user.email not in settings.ADMIN_EMAILS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


AdminUser = Annotated[CurrentUser, Depends(require_admin)]


# =============================================================================
# Response Schemas
# =============================================================================

class AdminStatsResponse(BaseModel):
    total_users: int
    total_api_keys: int
    total_jobs: int
    total_screenshots: int
    total_pdfs: int


class AdminUserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    plan_name: str
    is_active: bool
    created_at: str
    api_keys_count: int
    jobs_count: int

    class Config:
        from_attributes = True


class AdminAPIKeyResponse(BaseModel):
    id: UUID
    name: str | None
    key_prefix: str
    user_email: str
    user_id: UUID
    is_active: bool
    created_at: str
    last_used_at: str | None

    class Config:
        from_attributes = True


class AdminJobResponse(BaseModel):
    id: UUID
    user_email: str
    type: str
    status: str
    url: str
    format: str | None
    processing_time_ms: int | None
    file_size_bytes: int | None
    created_at: str

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    per_page: int
    pages: int


# =============================================================================
# Admin Endpoints
# =============================================================================

@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    admin: AdminUser,
    db: DBSession,
) -> AdminStatsResponse:
    """Get overview statistics for admin dashboard."""
    # Count users
    users_result = await db.execute(select(func.count(User.id)))
    total_users = users_result.scalar() or 0

    # Count API keys
    keys_result = await db.execute(select(func.count(APIKey.id)))
    total_api_keys = keys_result.scalar() or 0

    # Count jobs
    jobs_result = await db.execute(select(func.count(RenderJob.id)))
    total_jobs = jobs_result.scalar() or 0

    # Count screenshots
    screenshots_result = await db.execute(
        select(func.count(RenderJob.id)).where(RenderJob.type == "screenshot")
    )
    total_screenshots = screenshots_result.scalar() or 0

    # Count PDFs
    pdfs_result = await db.execute(
        select(func.count(RenderJob.id)).where(RenderJob.type == "pdf")
    )
    total_pdfs = pdfs_result.scalar() or 0

    return AdminStatsResponse(
        total_users=total_users,
        total_api_keys=total_api_keys,
        total_jobs=total_jobs,
        total_screenshots=total_screenshots,
        total_pdfs=total_pdfs,
    )


@router.get("/users")
async def list_users(
    admin: AdminUser,
    db: DBSession,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> PaginatedResponse:
    """List all users with pagination."""
    offset = (page - 1) * per_page

    # Count total
    count_result = await db.execute(select(func.count(User.id)))
    total = count_result.scalar() or 0

    # Get users with counts
    query = (
        select(User)
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    result = await db.execute(query)
    users = result.scalars().all()

    # Build response with counts
    items = []
    for user in users:
        # Count API keys for user
        keys_result = await db.execute(
            select(func.count(APIKey.id)).where(APIKey.user_id == user.id)
        )
        api_keys_count = keys_result.scalar() or 0

        # Count jobs for user
        jobs_result = await db.execute(
            select(func.count(RenderJob.id)).where(RenderJob.user_id == user.id)
        )
        jobs_count = jobs_result.scalar() or 0

        items.append(AdminUserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            plan_name=user.plan.name if user.plan else "free",
            is_active=user.is_active,
            created_at=user.created_at.isoformat(),
            api_keys_count=api_keys_count,
            jobs_count=jobs_count,
        ))

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@router.get("/api-keys")
async def list_api_keys(
    admin: AdminUser,
    db: DBSession,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> PaginatedResponse:
    """List all API keys with pagination."""
    offset = (page - 1) * per_page

    # Count total
    count_result = await db.execute(select(func.count(APIKey.id)))
    total = count_result.scalar() or 0

    # Get API keys with user info
    query = (
        select(APIKey)
        .options(selectinload(APIKey.user))
        .order_by(APIKey.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    result = await db.execute(query)
    keys = result.scalars().all()

    items = [
        AdminAPIKeyResponse(
            id=key.id,
            name=key.name,
            key_prefix=key.key_prefix,
            user_email=key.user.email if key.user else "Unknown",
            user_id=key.user_id,
            is_active=key.is_active,
            created_at=key.created_at.isoformat(),
            last_used_at=key.last_used_at.isoformat() if key.last_used_at else None,
        )
        for key in keys
    ]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@router.get("/jobs")
async def list_jobs(
    admin: AdminUser,
    db: DBSession,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
) -> PaginatedResponse:
    """List all render jobs with pagination."""
    offset = (page - 1) * per_page

    # Count total
    count_result = await db.execute(select(func.count(RenderJob.id)))
    total = count_result.scalar() or 0

    # Get jobs with user info
    query = (
        select(RenderJob)
        .options(selectinload(RenderJob.user))
        .order_by(RenderJob.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    result = await db.execute(query)
    jobs = result.scalars().all()

    items = [
        AdminJobResponse(
            id=job.id,
            user_email=job.user.email if job.user else "Unknown",
            type=job.type,
            status=job.status,
            url=job.url,
            format=job.options.get("format") if job.options else None,
            processing_time_ms=job.processing_time_ms,
            file_size_bytes=job.file_size_bytes,
            created_at=job.created_at.isoformat(),
        )
        for job in jobs
    ]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )

@router.get("/demo-stats")
async def get_demo_activity(
    admin: AdminUser,
) -> dict:
    """
    Get demo activity statistics and recent captures.
    
    Returns demo usage metrics including:
    - Total requests (today/week/all-time)
    - Recent demo captures with IP and URL
    - Top captured URLs
    """
    from app.services.cache_service import cache_service
    
    # Get demo stats from cache service
    stats = await cache_service.get_demo_stats()
    
    # Get recent captures (last 50)
    recent_captures = await cache_service.get_recent_demo_captures(limit=50)
    
    # Convert timestamps to ISO format for frontend
    for capture in recent_captures:
        if "timestamp" in capture:
            from datetime import datetime
            capture["timestamp"] = datetime.fromtimestamp(capture["timestamp"]).isoformat()
    
    return {
        **stats,
        "recent_captures": recent_captures,
    }
