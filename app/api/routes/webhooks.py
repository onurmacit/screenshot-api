"""
Webhook management endpoints
"""

from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import DBSession, JWTUser
from app.schemas.webhook import (
    WebhookCreate,
    WebhookResponse,
    WebhooksListResponse,
    WebhookUpdate,
)
from app.services.webhook_service import WebhookEvents, WebhookService
from app.utils.exceptions import NotFoundError

router = APIRouter()


@router.post(
    "",
    response_model=WebhookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create webhook",
    description="Create a new webhook endpoint.",
)
async def create_webhook(
    request: WebhookCreate,
    current_user: JWTUser,
    db: DBSession,
) -> WebhookResponse:
    """
    Create a new webhook.

    **Requires JWT authentication.**

    - **url**: Webhook endpoint URL (HTTPS only)
    - **events**: Events to subscribe to
    - **is_active**: Whether webhook is active

    Returns the webhook with its secret for signature verification.
    """
    webhook_service = WebhookService(db)

    webhook = await webhook_service.create_webhook(
        user_id=current_user.user_id,
        url=request.url,
        events=request.events,
    )

    return WebhookResponse(
        webhook_id=webhook.id,
        url=webhook.url,
        secret=webhook.secret,  # Only returned on creation
        events=webhook.events,
        is_active=webhook.is_active,
        last_triggered_at=webhook.last_triggered_at,
        failure_count=webhook.failure_count,
        created_at=webhook.created_at,
    )


@router.get(
    "",
    response_model=WebhooksListResponse,
    summary="List webhooks",
    description="List all webhooks for the authenticated user.",
)
async def list_webhooks(
    current_user: JWTUser,
    db: DBSession,
) -> WebhooksListResponse:
    """
    List all webhooks.

    **Requires JWT authentication.**

    Returns a list of webhooks (without secrets).
    """
    webhook_service = WebhookService(db)
    webhooks = await webhook_service.list_webhooks(user_id=current_user.user_id)

    return WebhooksListResponse(
        webhooks=[
            WebhookResponse(
                webhook_id=webhook.id,
                url=webhook.url,
                secret=None,  # Don't return secret on list
                events=webhook.events,
                is_active=webhook.is_active,
                last_triggered_at=webhook.last_triggered_at,
                failure_count=webhook.failure_count,
                created_at=webhook.created_at,
            )
            for webhook in webhooks
        ]
    )


@router.get(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Get webhook",
    description="Get a specific webhook.",
)
async def get_webhook(
    webhook_id: UUID,
    current_user: JWTUser,
    db: DBSession,
) -> WebhookResponse:
    """
    Get a specific webhook.

    **Requires JWT authentication.**

    - **webhook_id**: UUID of the webhook
    """
    webhook_service = WebhookService(db)
    webhook = await webhook_service.get_webhook(
        webhook_id=webhook_id,
        user_id=current_user.user_id,
    )

    if not webhook:
        raise NotFoundError(
            "Webhook not found",
            resource_type="webhook",
            resource_id=str(webhook_id),
        )

    return WebhookResponse(
        webhook_id=webhook.id,
        url=webhook.url,
        secret=None,  # Don't return secret on get
        events=webhook.events,
        is_active=webhook.is_active,
        last_triggered_at=webhook.last_triggered_at,
        failure_count=webhook.failure_count,
        created_at=webhook.created_at,
    )


@router.patch(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Update webhook",
    description="Update a webhook.",
)
async def update_webhook(
    webhook_id: UUID,
    request: WebhookUpdate,
    current_user: JWTUser,
    db: DBSession,
) -> WebhookResponse:
    """
    Update a webhook.

    **Requires JWT authentication.**

    - **webhook_id**: UUID of the webhook
    - **url**: New URL (optional)
    - **events**: New events list (optional)
    - **is_active**: New active status (optional)
    """
    webhook_service = WebhookService(db)

    webhook = await webhook_service.update_webhook(
        webhook_id=webhook_id,
        user_id=current_user.user_id,
        url=request.url,
        events=request.events,
        is_active=request.is_active,
    )

    if not webhook:
        raise NotFoundError(
            "Webhook not found",
            resource_type="webhook",
            resource_id=str(webhook_id),
        )

    return WebhookResponse(
        webhook_id=webhook.id,
        url=webhook.url,
        secret=None,
        events=webhook.events,
        is_active=webhook.is_active,
        last_triggered_at=webhook.last_triggered_at,
        failure_count=webhook.failure_count,
        created_at=webhook.created_at,
    )


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete webhook",
    description="Delete a webhook.",
)
async def delete_webhook(
    webhook_id: UUID,
    current_user: JWTUser,
    db: DBSession,
) -> None:
    """
    Delete a webhook.

    **Requires JWT authentication.**

    - **webhook_id**: UUID of the webhook
    """
    webhook_service = WebhookService(db)

    deleted = await webhook_service.delete_webhook(
        webhook_id=webhook_id,
        user_id=current_user.user_id,
    )

    if not deleted:
        raise NotFoundError(
            "Webhook not found",
            resource_type="webhook",
            resource_id=str(webhook_id),
        )


@router.get(
    "/events/available",
    response_model=list[str],
    summary="List available events",
    description="List all available webhook events.",
)
async def list_available_events() -> list[str]:
    """
    List available webhook events.

    No authentication required.
    """
    return WebhookEvents.all()
