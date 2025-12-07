"""
Render Tasks

Celery tasks for asynchronous screenshot and PDF rendering.
Uses sync Celery tasks with asyncio.run for async operations.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import Plan, RenderJob, User
from app.services.rate_limit_service import rate_limit_service
from app.services.render_service import render_service
from app.services.storage_service import storage_service
from app.utils.exceptions import RenderError, ValidationError
from app.utils.logger import get_logger
from app.workers.celery_app import celery_app, get_queue_for_plan, run_async

logger = get_logger(__name__)


async def get_job_with_user(
    db: AsyncSession,
    job_id: UUID,
) -> tuple[RenderJob | None, User | None, Plan | None]:
    """Get render job with associated user and plan."""
    result = await db.execute(
        select(RenderJob).where(RenderJob.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        return None, None, None

    result = await db.execute(
        select(User).where(User.id == job.user_id)
    )
    user = result.scalar_one_or_none()

    plan = None
    if user and user.plan_id:
        result = await db.execute(
            select(Plan).where(Plan.id == user.plan_id)
        )
        plan = result.scalar_one_or_none()

    return job, user, plan


@celery_app.task(
    bind=True,
    name="app.workers.render_tasks.process_screenshot",
    max_retries=3,
    default_retry_delay=5,
    autoretry_for=(RenderError, ConnectionError, TimeoutError, OSError),
    dont_autoretry_for=(ValidationError, ValueError),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    soft_time_limit=270,
    time_limit=300,
)
def process_screenshot(self, job_id: str) -> dict[str, Any]:
    """
    Process screenshot render job.

    Args:
        job_id: UUID string of the render job

    Returns:
        Dict with job result

    Raises:
        Retry: If job should be retried
    """
    logger.info("Processing screenshot job", job_id=job_id, attempt=self.request.retries + 1)

    try:
        return run_async(_process_screenshot_async(self, job_id))
    except SoftTimeLimitExceeded:
        logger.warning("Screenshot job soft time limit exceeded", job_id=job_id)
        run_async(_mark_job_failed(job_id, "Job timed out"))
        return {"error": "timeout"}


async def _mark_job_failed(job_id: str, error_message: str) -> None:
    """Mark a job as failed."""
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(RenderJob).where(RenderJob.id == UUID(job_id))
            )
            job = result.scalar_one_or_none()
            if job:
                job.status = "failed"
                job.error_message = error_message
                job.completed_at = datetime.now(UTC)
                await db.commit()
        except Exception as e:
            logger.error("Failed to mark job as failed", job_id=job_id, error=str(e))
            await db.rollback()


async def _process_screenshot_async(task, job_id: str) -> dict[str, Any]:
    """Async implementation of screenshot processing."""
    async with AsyncSessionLocal() as db:
        job = None
        try:
            # Get job
            job, user, plan = await get_job_with_user(db, UUID(job_id))

            if not job:
                logger.error("Job not found", job_id=job_id)
                return {"error": "Job not found"}

            if job.status not in ("pending", "processing"):
                logger.warning("Job already processed", job_id=job_id, status=job.status)
                return {"status": job.status}

            # Update status
            job.status = "processing"
            job.started_at = datetime.now(UTC)
            job.retry_count = task.request.retries
            await db.commit()

            # Get plan features
            plan_features = plan.features if plan else {"watermark": True}

            # Capture screenshot
            image_bytes, metadata = await render_service.capture_screenshot(
                url=job.url,
                options=job.options,
                user_plan=plan_features,
            )

            # Apply watermark for free tier
            if plan_features.get("watermark", True):
                image_bytes = render_service.inject_watermark(
                    image_bytes,
                    format=job.options.get("format", "png"),
                )

            # Upload to S3
            upload_result = await storage_service.upload_render(
                file_bytes=image_bytes,
                user_id=str(job.user_id),
                job_id=str(job.id),
                file_type=job.options.get("format", "png"),
            )

            # Update job
            job.status = "completed"
            job.completed_at = datetime.now(UTC)
            job.s3_key = upload_result["s3_key"]
            job.s3_url = upload_result["s3_url"]
            job.file_size_bytes = upload_result["file_size"]
            job.processing_time_ms = metadata["processing_time_ms"]
            job.result = metadata

            await db.commit()

            # Increment usage
            await rate_limit_service.increment_usage(job.user_id)

            logger.info(
                "Screenshot job completed",
                job_id=job_id,
                processing_time_ms=metadata["processing_time_ms"],
            )

            # Trigger webhook if configured
            if job.webhook_url:
                from app.workers.webhook_tasks import send_job_webhook

                send_job_webhook.delay(str(job.id), "job.completed")

            return {
                "status": "completed",
                "job_id": job_id,
                "s3_key": upload_result["s3_key"],
                "file_size": upload_result["file_size"],
                "processing_time_ms": metadata["processing_time_ms"],
            }

        except ValidationError as e:
            # Don't retry validation errors
            logger.warning("Validation error in screenshot job", job_id=job_id, error=str(e))
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now(UTC)
                await db.commit()
            return {"error": str(e)}

        except (RenderError, ConnectionError, TimeoutError, OSError) as e:
            logger.warning("Retryable error in screenshot job", job_id=job_id, error=str(e))

            # Update job status
            if job:
                if task.request.retries < task.max_retries:
                    job.status = "pending"  # Will be retried
                else:
                    job.status = "failed"
                    job.error_message = str(e)
                    job.completed_at = datetime.now(UTC)

                    # Trigger failure webhook
                    if job.webhook_url:
                        from app.workers.webhook_tasks import send_job_webhook
                        send_job_webhook.delay(str(job.id), "job.failed")

                await db.commit()

            raise  # Re-raise for Celery retry

        except Exception as e:
            logger.exception("Screenshot job failed", job_id=job_id, error=str(e))

            # Update job status
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now(UTC)

                # Trigger failure webhook
                if job.webhook_url:
                    from app.workers.webhook_tasks import send_job_webhook
                    send_job_webhook.delay(str(job.id), "job.failed")

                await db.commit()

            return {"error": str(e)}


@celery_app.task(
    bind=True,
    name="app.workers.render_tasks.process_pdf",
    max_retries=3,
    default_retry_delay=5,
    autoretry_for=(RenderError, ConnectionError, TimeoutError, OSError),
    dont_autoretry_for=(ValidationError, ValueError),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    soft_time_limit=270,
    time_limit=300,
)
def process_pdf(self, job_id: str) -> dict[str, Any]:
    """
    Process PDF render job.

    Args:
        job_id: UUID string of the render job

    Returns:
        Dict with job result
    """
    logger.info("Processing PDF job", job_id=job_id, attempt=self.request.retries + 1)

    try:
        return run_async(_process_pdf_async(self, job_id))
    except SoftTimeLimitExceeded:
        logger.warning("PDF job soft time limit exceeded", job_id=job_id)
        run_async(_mark_job_failed(job_id, "Job timed out"))
        return {"error": "timeout"}


async def _process_pdf_async(task, job_id: str) -> dict[str, Any]:
    """Async implementation of PDF processing."""
    async with AsyncSessionLocal() as db:
        job = None
        try:
            # Get job
            job, user, plan = await get_job_with_user(db, UUID(job_id))

            if not job:
                logger.error("Job not found", job_id=job_id)
                return {"error": "Job not found"}

            if job.status not in ("pending", "processing"):
                logger.warning("Job already processed", job_id=job_id, status=job.status)
                return {"status": job.status}

            # Update status
            job.status = "processing"
            job.started_at = datetime.now(UTC)
            job.retry_count = task.request.retries
            await db.commit()

            # Get plan features
            plan_features = plan.features if plan else {}

            # Generate PDF
            pdf_bytes, metadata = await render_service.generate_pdf(
                url=job.url,
                options=job.options,
                user_plan=plan_features,
            )

            # Upload to S3
            upload_result = await storage_service.upload_render(
                file_bytes=pdf_bytes,
                user_id=str(job.user_id),
                job_id=str(job.id),
                file_type="pdf",
            )

            # Update job
            job.status = "completed"
            job.completed_at = datetime.now(UTC)
            job.s3_key = upload_result["s3_key"]
            job.s3_url = upload_result["s3_url"]
            job.file_size_bytes = upload_result["file_size"]
            job.processing_time_ms = metadata["processing_time_ms"]
            job.result = metadata

            await db.commit()

            # Increment usage
            await rate_limit_service.increment_usage(job.user_id)

            logger.info(
                "PDF job completed",
                job_id=job_id,
                processing_time_ms=metadata["processing_time_ms"],
            )

            # Trigger webhook if configured
            if job.webhook_url:
                from app.workers.webhook_tasks import send_job_webhook

                send_job_webhook.delay(str(job.id), "job.completed")

            return {
                "status": "completed",
                "job_id": job_id,
                "s3_key": upload_result["s3_key"],
                "file_size": upload_result["file_size"],
                "processing_time_ms": metadata["processing_time_ms"],
            }

        except ValidationError as e:
            logger.warning("Validation error in PDF job", job_id=job_id, error=str(e))
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now(UTC)
                await db.commit()
            return {"error": str(e)}

        except (RenderError, ConnectionError, TimeoutError, OSError) as e:
            logger.warning("Retryable error in PDF job", job_id=job_id, error=str(e))

            if job:
                if task.request.retries < task.max_retries:
                    job.status = "pending"
                else:
                    job.status = "failed"
                    job.error_message = str(e)
                    job.completed_at = datetime.now(UTC)

                    if job.webhook_url:
                        from app.workers.webhook_tasks import send_job_webhook
                        send_job_webhook.delay(str(job.id), "job.failed")

                await db.commit()

            raise

        except Exception as e:
            logger.exception("PDF job failed", job_id=job_id, error=str(e))

            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now(UTC)

                if job.webhook_url:
                    from app.workers.webhook_tasks import send_job_webhook
                    send_job_webhook.delay(str(job.id), "job.failed")

                await db.commit()

            return {"error": str(e)}


def queue_render_job(job_id: str, job_type: str, plan_name: str) -> str:
    """
    Queue a render job with appropriate priority.

    Args:
        job_id: Job UUID string
        job_type: Job type (screenshot or pdf)
        plan_name: User's plan name

    Returns:
        Celery task ID
    """
    queue = get_queue_for_plan(plan_name)

    if job_type == "screenshot":
        task = process_screenshot
    else:
        task = process_pdf

    result = task.apply_async(
        args=[job_id],
        queue=queue,
    )

    logger.info(
        "Render job queued",
        job_id=job_id,
        job_type=job_type,
        queue=queue,
        task_id=result.id,
    )

    return result.id
