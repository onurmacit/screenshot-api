"""
Webhook Service

Handles webhook delivery with retry logic and signature verification.
"""

import hmac
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.security import generate_webhook_secret, sign_webhook_payload
from app.models import Webhook
from app.utils.logger import get_logger

logger = get_logger(__name__)


# Webhook delivery configuration
WEBHOOK_TIMEOUT = 10  # seconds
WEBHOOK_MAX_RETRIES = 5
WEBHOOK_MAX_FAILURES = 10  # Disable after this many consecutive failures


class WebhookPayload:
    """Webhook payload builder."""

    def __init__(
        self,
        event: str,
        data: dict[str, Any],
        timestamp: datetime | None = None,
    ):
        self.event = event
        self.data = data
        self.timestamp = timestamp or datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event": self.event,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class WebhookService:
    """Service for webhook operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Webhook CRUD
    # =========================================================================

    async def create_webhook(
        self,
        user_id: UUID,
        url: str,
        events: list[str],
    ) -> Webhook:
        """
        Create a new webhook.

        Args:
            user_id: User UUID
            url: Webhook endpoint URL
            events: List of events to subscribe to

        Returns:
            Created webhook with secret
        """
        secret = generate_webhook_secret()

        webhook = Webhook(
            user_id=user_id,
            url=url,
            secret=secret,
            events=events,
            is_active=True,
            failure_count=0,
        )

        self.db.add(webhook)
        await self.db.commit()
        await self.db.refresh(webhook)

        logger.info(
            "Webhook created",
            webhook_id=str(webhook.id),
            user_id=str(user_id),
            events=events,
        )

        return webhook

    async def get_webhook(
        self,
        webhook_id: UUID,
        user_id: UUID,
    ) -> Webhook | None:
        """
        Get webhook by ID for a user.

        Args:
            webhook_id: Webhook UUID
            user_id: User UUID

        Returns:
            Webhook or None
        """
        result = await self.db.execute(
            select(Webhook).where(
                Webhook.id == webhook_id,
                Webhook.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_webhooks(self, user_id: UUID) -> list[Webhook]:
        """
        List all webhooks for a user.

        Args:
            user_id: User UUID

        Returns:
            List of webhooks
        """
        result = await self.db.execute(
            select(Webhook)
            .where(Webhook.user_id == user_id)
            .order_by(Webhook.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_webhook(
        self,
        webhook_id: UUID,
        user_id: UUID,
        url: str | None = None,
        events: list[str] | None = None,
        is_active: bool | None = None,
    ) -> Webhook | None:
        """
        Update a webhook.

        Args:
            webhook_id: Webhook UUID
            user_id: User UUID
            url: New URL (optional)
            events: New events (optional)
            is_active: Active status (optional)

        Returns:
            Updated webhook or None
        """
        webhook = await self.get_webhook(webhook_id, user_id)
        if not webhook:
            return None

        if url is not None:
            webhook.url = url
        if events is not None:
            webhook.events = events
        if is_active is not None:
            webhook.is_active = is_active

        await self.db.commit()
        await self.db.refresh(webhook)

        logger.info("Webhook updated", webhook_id=str(webhook_id))

        return webhook

    async def delete_webhook(
        self,
        webhook_id: UUID,
        user_id: UUID,
    ) -> bool:
        """
        Delete a webhook.

        Args:
            webhook_id: Webhook UUID
            user_id: User UUID

        Returns:
            True if deleted
        """
        webhook = await self.get_webhook(webhook_id, user_id)
        if not webhook:
            return False

        await self.db.delete(webhook)
        await self.db.commit()

        logger.info("Webhook deleted", webhook_id=str(webhook_id))

        return True

    # =========================================================================
    # Webhook Delivery
    # =========================================================================

    async def get_webhooks_for_event(
        self,
        user_id: UUID,
        event: str,
    ) -> list[Webhook]:
        """
        Get all active webhooks subscribed to an event.

        Args:
            user_id: User UUID
            event: Event name

        Returns:
            List of matching webhooks
        """
        result = await self.db.execute(
            select(Webhook).where(
                Webhook.user_id == user_id,
                Webhook.is_active == True,
                Webhook.events.contains([event]),
            )
        )
        return list(result.scalars().all())

    async def trigger_webhooks(
        self,
        user_id: UUID,
        event: str,
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Trigger all webhooks for an event.

        Args:
            user_id: User UUID
            event: Event name
            data: Event data

        Returns:
            List of delivery results
        """
        webhooks = await self.get_webhooks_for_event(user_id, event)
        results = []

        for webhook in webhooks:
            try:
                success = await self.deliver_webhook(webhook, event, data)
                results.append({
                    "webhook_id": str(webhook.id),
                    "success": success,
                    "error": None,
                })
            except Exception as e:
                results.append({
                    "webhook_id": str(webhook.id),
                    "success": False,
                    "error": str(e),
                })

        return results

    async def deliver_webhook(
        self,
        webhook: Webhook,
        event: str,
        data: dict[str, Any],
    ) -> bool:
        """
        Deliver a webhook with retry logic.

        Args:
            webhook: Webhook model
            event: Event name
            data: Event data

        Returns:
            True if delivered successfully
        """
        payload = WebhookPayload(event=event, data=data)
        payload_json = payload.to_json()

        # Generate signature
        signature = sign_webhook_payload(payload_json, webhook.secret)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Event": event,
            "X-Webhook-Timestamp": payload.timestamp.isoformat(),
        }

        try:
            success = await self._deliver_with_retry(
                url=webhook.url,
                payload=payload_json,
                headers=headers,
            )

            if success:
                # Reset failure count on success
                webhook.failure_count = 0
                webhook.last_triggered_at = datetime.now(UTC)
            else:
                # Increment failure count
                webhook.failure_count += 1

                # Disable if too many failures
                if webhook.failure_count >= WEBHOOK_MAX_FAILURES:
                    webhook.is_active = False
                    logger.warning(
                        "Webhook disabled due to failures",
                        webhook_id=str(webhook.id),
                        failures=webhook.failure_count,
                    )

            await self.db.commit()
            return success

        except Exception as e:
            logger.error(
                "Webhook delivery failed",
                webhook_id=str(webhook.id),
                error=str(e),
            )

            webhook.failure_count += 1
            if webhook.failure_count >= WEBHOOK_MAX_FAILURES:
                webhook.is_active = False

            await self.db.commit()
            return False

    @retry(
        stop=stop_after_attempt(WEBHOOK_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True,
    )
    async def _deliver_with_retry(
        self,
        url: str,
        payload: str,
        headers: dict[str, str],
    ) -> bool:
        """
        Deliver webhook with exponential backoff retry.

        Args:
            url: Webhook URL
            payload: JSON payload
            headers: Request headers

        Returns:
            True if delivered successfully (2xx response)
        """
        async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
            response = await client.post(
                url,
                content=payload,
                headers=headers,
            )

            if response.is_success:
                logger.info(
                    "Webhook delivered",
                    url=url,
                    status=response.status_code,
                )
                return True
            else:
                logger.warning(
                    "Webhook delivery failed",
                    url=url,
                    status=response.status_code,
                )
                return False

    # =========================================================================
    # Signature Verification
    # =========================================================================

    def verify_signature(
        self,
        payload: str,
        signature: str,
        secret: str,
    ) -> bool:
        """
        Verify webhook signature.

        Args:
            payload: Request body as string
            signature: X-Webhook-Signature header value
            secret: Webhook secret

        Returns:
            True if signature is valid
        """
        expected = sign_webhook_payload(payload, secret)
        return hmac.compare_digest(signature, expected)


# Webhook event types
class WebhookEvents:
    """Webhook event constants."""

    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    USAGE_LIMIT_REACHED = "usage.limit_reached"
    USAGE_LIMIT_WARNING = "usage.limit_warning"

    @classmethod
    def all(cls) -> list[str]:
        """Get all available events."""
        return [
            cls.JOB_COMPLETED,
            cls.JOB_FAILED,
            cls.USAGE_LIMIT_REACHED,
            cls.USAGE_LIMIT_WARNING,
        ]

