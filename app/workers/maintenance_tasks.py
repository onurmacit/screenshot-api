"""
Maintenance Tasks

Celery tasks for cleanup, usage calculation, and maintenance operations.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import AuditLog, RenderJob
from app.services.storage_service import storage_service
from app.utils.logger import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="app.workers.maintenance_tasks.cleanup_expired_files",
)
def cleanup_expired_files() -> dict[str, Any]:
    """
    Clean up expired render files from S3.

    Runs hourly to remove files past their expiration date.

    Returns:
        Cleanup statistics
    """
    logger.info("Starting expired files cleanup")
    return run_async(_cleanup_expired_files_async())


async def _cleanup_expired_files_async() -> dict[str, Any]:
    """Async implementation of expired files cleanup."""
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)

        # Find expired jobs with S3 keys
        result = await db.execute(
            select(RenderJob).where(
                RenderJob.expires_at < now,
                RenderJob.s3_key.isnot(None),
                RenderJob.status == "completed",
            ).limit(1000)  # Process in batches
        )
        expired_jobs = result.scalars().all()

        if not expired_jobs:
            logger.info("No expired files to clean up")
            return {"deleted": 0, "errors": 0}

        # Collect S3 keys
        s3_keys = [job.s3_key for job in expired_jobs if job.s3_key]

        # Delete from S3
        cleanup_result = await storage_service.cleanup_expired_files(s3_keys)

        # Update job records
        for job in expired_jobs:
            job.s3_key = None
            job.s3_url = None
            job.status = "expired"

        await db.commit()

        logger.info(
            "Expired files cleanup completed",
            deleted=cleanup_result["deleted"],
            errors=cleanup_result["errors"],
        )

        return cleanup_result


@celery_app.task(
    name="app.workers.maintenance_tasks.calculate_daily_usage",
)
def calculate_daily_usage() -> dict[str, Any]:
    """
    Calculate and record daily usage statistics.

    Runs at midnight UTC to aggregate the previous day's usage.

    Returns:
        Calculation statistics
    """
    logger.info("Starting daily usage calculation")
    return run_async(_calculate_daily_usage_async())


async def _calculate_daily_usage_async() -> dict[str, Any]:
    """Async implementation of daily usage calculation."""
    async with AsyncSessionLocal() as db:
        # Calculate for yesterday
        now = datetime.now(timezone.utc)
        yesterday_start = (now - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        yesterday_end = yesterday_start + timedelta(days=1)

        # Aggregate usage by user
        result = await db.execute(
            select(
                RenderJob.user_id,
                func.count(RenderJob.id).label("total_jobs"),
                func.count(RenderJob.id).filter(RenderJob.type == "screenshot").label("screenshots"),
                func.count(RenderJob.id).filter(RenderJob.type == "pdf").label("pdfs"),
                func.coalesce(func.sum(RenderJob.file_size_bytes), 0).label("total_size"),
                func.coalesce(func.sum(RenderJob.processing_time_ms), 0).label("total_time"),
            ).where(
                RenderJob.created_at >= yesterday_start,
                RenderJob.created_at < yesterday_end,
                RenderJob.status == "completed",
            ).group_by(RenderJob.user_id)
        )
        usage_records = result.all()

        logger.info(
            "Daily usage calculated",
            date=yesterday_start.strftime("%Y-%m-%d"),
            users=len(usage_records),
        )

        # Could store these in a daily_usage table for reporting
        # For now, just log and return

        return {
            "date": yesterday_start.strftime("%Y-%m-%d"),
            "users_with_activity": len(usage_records),
            "total_jobs": sum(r.total_jobs for r in usage_records),
        }


@celery_app.task(
    name="app.workers.maintenance_tasks.cleanup_old_audit_logs",
)
def cleanup_old_audit_logs() -> dict[str, Any]:
    """
    Clean up old audit logs.

    Runs weekly to remove audit logs older than retention period.

    Returns:
        Cleanup statistics
    """
    logger.info("Starting audit logs cleanup")
    return run_async(_cleanup_old_audit_logs_async())


async def _cleanup_old_audit_logs_async() -> dict[str, Any]:
    """Async implementation of audit logs cleanup."""
    async with AsyncSessionLocal() as db:
        # Delete logs older than 90 days
        retention_days = 90
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

        result = await db.execute(
            delete(AuditLog).where(AuditLog.created_at < cutoff)
        )
        deleted_count = result.rowcount

        await db.commit()

        logger.info(
            "Audit logs cleanup completed",
            deleted=deleted_count,
            retention_days=retention_days,
        )

        return {
            "deleted": deleted_count,
            "retention_days": retention_days,
        }


@celery_app.task(
    name="app.workers.maintenance_tasks.cleanup_failed_jobs",
)
def cleanup_failed_jobs() -> dict[str, Any]:
    """
    Clean up old failed jobs.

    Removes failed job records older than 30 days.

    Returns:
        Cleanup statistics
    """
    logger.info("Starting failed jobs cleanup")
    return run_async(_cleanup_failed_jobs_async())


async def _cleanup_failed_jobs_async() -> dict[str, Any]:
    """Async implementation of failed jobs cleanup."""
    async with AsyncSessionLocal() as db:
        # Delete failed jobs older than 30 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        result = await db.execute(
            delete(RenderJob).where(
                RenderJob.status == "failed",
                RenderJob.created_at < cutoff,
            )
        )
        deleted_count = result.rowcount

        await db.commit()

        logger.info(
            "Failed jobs cleanup completed",
            deleted=deleted_count,
        )

        return {"deleted": deleted_count}


@celery_app.task(
    name="app.workers.maintenance_tasks.refresh_expired_tokens",
)
def refresh_expired_tokens() -> dict[str, Any]:
    """
    Clean up expired refresh tokens.

    Removes expired and revoked refresh tokens.

    Returns:
        Cleanup statistics
    """
    logger.info("Starting expired tokens cleanup")
    return run_async(_refresh_expired_tokens_async())


async def _refresh_expired_tokens_async() -> dict[str, Any]:
    """Async implementation of expired tokens cleanup."""
    from app.models import RefreshToken

    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)

        # Delete expired and revoked tokens
        result = await db.execute(
            delete(RefreshToken).where(
                (RefreshToken.expires_at < now) | (RefreshToken.is_revoked == True)
            )
        )
        deleted_count = result.rowcount

        await db.commit()

        logger.info(
            "Expired tokens cleanup completed",
            deleted=deleted_count,
        )

        return {"deleted": deleted_count}


@celery_app.task(
    name="app.workers.maintenance_tasks.health_check",
)
def health_check() -> dict[str, Any]:
    """
    Perform a health check from worker.

    Verifies worker can connect to database and Redis.

    Returns:
        Health status
    """
    logger.info("Running worker health check")
    return run_async(_health_check_async())


async def _health_check_async() -> dict[str, Any]:
    """Async implementation of health check."""
    from app.core.redis import redis_context

    status = {
        "database": "unknown",
        "redis": "unknown",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Check database
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import text
            await db.execute(text("SELECT 1"))
        status["database"] = "healthy"
    except Exception as e:
        status["database"] = f"unhealthy: {str(e)}"

    # Check Redis
    try:
        async with redis_context() as redis:
            await redis.ping()
        status["redis"] = "healthy"
    except Exception as e:
        status["redis"] = f"unhealthy: {str(e)}"

    logger.info("Worker health check completed", status=status)

    return status

