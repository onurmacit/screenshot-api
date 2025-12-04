"""
Webhook Tasks

Celery tasks for webhook delivery with retry logic.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import sign_webhook_payload
from app.models import RenderJob, Webhook
from app.utils.logger import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)

# Webhook configuration
WEBHOOK_TIMEOUT = 10  # seconds
WEBHOOK_MAX_RETRIES = 5


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    name="app.workers.webhook_tasks.send_webhook",
    max_retries=WEBHOOK_MAX_RETRIES,
    default_retry_delay=1,
    autoretry_for=(httpx.TimeoutException, httpx.ConnectError),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
)
def send_webhook(
    self,
    webhook_id: str,
    event: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Send a webhook notification.

    Args:
        webhook_id: Webhook UUID string
        event: Event type
        payload: Event payload

    Returns:
        Delivery result
    """
    logger.info(
        "Sending webhook",
        webhook_id=webhook_id,
        event=event,
        attempt=self.request.retries + 1,
    )

    return run_async(_send_webhook_async(self, webhook_id, event, payload))


async def _send_webhook_async(
    task,
    webhook_id: str,
    event: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Async implementation of webhook sending."""
    import json

    async with AsyncSessionLocal() as db:
        # Get webhook
        result = await db.execute(
            select(Webhook).where(Webhook.id == UUID(webhook_id))
        )
        webhook = result.scalar_one_or_none()

        if not webhook:
            logger.error("Webhook not found", webhook_id=webhook_id)
            return {"error": "Webhook not found"}

        if not webhook.is_active:
            logger.warning("Webhook is inactive", webhook_id=webhook_id)
            return {"error": "Webhook inactive"}

        # Build full payload
        full_payload = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": payload,
        }
        payload_json = json.dumps(full_payload, default=str)

        # Generate signature
        signature = sign_webhook_payload(payload_json, webhook.secret)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Event": event,
            "X-Webhook-Timestamp": full_payload["timestamp"],
        }

        try:
            async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
                response = await client.post(
                    webhook.url,
                    content=payload_json,
                    headers=headers,
                )

            if response.is_success:
                # Success - reset failure count
                webhook.failure_count = 0
                webhook.last_triggered_at = datetime.now(timezone.utc)
                await db.commit()

                logger.info(
                    "Webhook delivered",
                    webhook_id=webhook_id,
                    status_code=response.status_code,
                )

                return {
                    "status": "delivered",
                    "status_code": response.status_code,
                }

            else:
                # Non-2xx response
                logger.warning(
                    "Webhook delivery failed",
                    webhook_id=webhook_id,
                    status_code=response.status_code,
                )

                webhook.failure_count += 1

                # Disable if too many failures
                if webhook.failure_count >= 10:
                    webhook.is_active = False
                    logger.warning(
                        "Webhook disabled due to failures",
                        webhook_id=webhook_id,
                    )

                await db.commit()

                # Retry if appropriate
                if task.request.retries < WEBHOOK_MAX_RETRIES:
                    raise task.retry()

                return {
                    "status": "failed",
                    "status_code": response.status_code,
                }

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            logger.warning(
                "Webhook connection error",
                webhook_id=webhook_id,
                error=str(e),
            )

            webhook.failure_count += 1
            if webhook.failure_count >= 10:
                webhook.is_active = False

            await db.commit()

            raise  # Will trigger retry


@celery_app.task(
    bind=True,
    name="app.workers.webhook_tasks.send_job_webhook",
    max_retries=WEBHOOK_MAX_RETRIES,
    default_retry_delay=1,
    retry_backoff=True,
)
def send_job_webhook(self, job_id: str, event: str) -> dict[str, Any]:
    """
    Send webhook notification for a render job.

    Args:
        job_id: Render job UUID string
        event: Event type (job.completed or job.failed)

    Returns:
        Delivery result
    """
    logger.info("Sending job webhook", job_id=job_id, event=event)

    return run_async(_send_job_webhook_async(self, job_id, event))


async def _send_job_webhook_async(
    task,
    job_id: str,
    event: str,
) -> dict[str, Any]:
    """Async implementation of job webhook sending."""
    import json

    async with AsyncSessionLocal() as db:
        # Get job
        result = await db.execute(
            select(RenderJob).where(RenderJob.id == UUID(job_id))
        )
        job = result.scalar_one_or_none()

        if not job:
            logger.error("Job not found", job_id=job_id)
            return {"error": "Job not found"}

        if not job.webhook_url:
            logger.warning("Job has no webhook URL", job_id=job_id)
            return {"error": "No webhook URL"}

        # Build payload
        payload = {
            "job_id": str(job.id),
            "type": job.type,
            "status": job.status,
            "url": job.url,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        }

        if job.status == "completed":
            payload.update({
                "s3_url": job.s3_url,
                "file_size_bytes": job.file_size_bytes,
                "processing_time_ms": job.processing_time_ms,
                "result": job.result,
            })
        elif job.status == "failed":
            payload["error_message"] = job.error_message

        # Build full payload
        full_payload = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": payload,
        }
        payload_json = json.dumps(full_payload, default=str)

        # Generate signature using a derived secret
        # For job-specific webhooks, we use a hash of the job ID as secret
        import hashlib
        job_secret = hashlib.sha256(f"job:{job_id}".encode()).hexdigest()
        signature = sign_webhook_payload(payload_json, job_secret)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Event": event,
            "X-Webhook-Job-ID": str(job.id),
        }

        try:
            async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
                response = await client.post(
                    job.webhook_url,
                    content=payload_json,
                    headers=headers,
                )

            # Update webhook status
            job.webhook_attempts += 1

            if response.is_success:
                job.webhook_sent = True
                await db.commit()

                logger.info(
                    "Job webhook delivered",
                    job_id=job_id,
                    status_code=response.status_code,
                )

                return {
                    "status": "delivered",
                    "status_code": response.status_code,
                }

            else:
                await db.commit()

                logger.warning(
                    "Job webhook delivery failed",
                    job_id=job_id,
                    status_code=response.status_code,
                )

                if task.request.retries < WEBHOOK_MAX_RETRIES:
                    raise task.retry()

                return {
                    "status": "failed",
                    "status_code": response.status_code,
                }

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            job.webhook_attempts += 1
            await db.commit()

            logger.warning(
                "Job webhook connection error",
                job_id=job_id,
                error=str(e),
            )

            raise task.retry(exc=e)


@celery_app.task(
    name="app.workers.webhook_tasks.trigger_event_webhooks",
)
def trigger_event_webhooks(
    user_id: str,
    event: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Trigger all webhooks subscribed to an event.

    Args:
        user_id: User UUID string
        event: Event type
        payload: Event payload

    Returns:
        Trigger results
    """
    logger.info("Triggering event webhooks", user_id=user_id, event=event)

    return run_async(_trigger_event_webhooks_async(user_id, event, payload))


async def _trigger_event_webhooks_async(
    user_id: str,
    event: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Async implementation of event webhook triggering."""
    async with AsyncSessionLocal() as db:
        # Get all active webhooks for user subscribed to event
        result = await db.execute(
            select(Webhook).where(
                Webhook.user_id == UUID(user_id),
                Webhook.is_active == True,
                Webhook.events.contains([event]),
            )
        )
        webhooks = result.scalars().all()

        if not webhooks:
            logger.info("No webhooks for event", user_id=user_id, event=event)
            return {"triggered": 0}

        # Queue webhook deliveries
        triggered = 0
        for webhook in webhooks:
            send_webhook.delay(str(webhook.id), event, payload)
            triggered += 1

        logger.info(
            "Webhooks triggered",
            user_id=user_id,
            event=event,
            count=triggered,
        )

        return {"triggered": triggered}

