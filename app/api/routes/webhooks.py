"""
Webhook management endpoints

Includes HMAC signature validation for secure webhook verification.
"""

import hashlib
import hmac
import secrets
from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.dependencies import DBSession, JWTUser
from app.models import Webhook
from app.schemas.webhook import (
    WebhookCreate,
    WebhookResponse,
    WebhookSecretResponse,
    WebhooksListResponse,
    WebhookUpdate,
    WebhookVerifyRequest,
    WebhookVerifyResponse,
)
from app.services.webhook_service import WebhookEvents, WebhookService
from app.utils.exceptions import NotFoundError
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


# =============================================================================
# Webhook Signature Verification Helpers
# =============================================================================

def generate_webhook_signature(payload: str, secret: str) -> str:
    """
    Generate HMAC-SHA256 signature for webhook payload.
    
    Args:
        payload: JSON payload string
        secret: Webhook secret key
        
    Returns:
        Hex-encoded HMAC signature prefixed with 'sha256='
    """
    signature = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"sha256={signature}"


def verify_webhook_signature(
    payload: str,
    signature: str,
    secret: str,
    tolerance_seconds: int = 300,
) -> bool:
    """
    Verify HMAC-SHA256 signature of webhook payload.
    
    Args:
        payload: JSON payload string
        signature: Received signature (with or without 'sha256=' prefix)
        secret: Webhook secret key
        tolerance_seconds: Maximum age of webhook in seconds (default 5 minutes)
        
    Returns:
        True if signature is valid
    """
    # Remove prefix if present
    if signature.startswith("sha256="):
        received_sig = signature[7:]
    else:
        received_sig = signature

    # Calculate expected signature
    expected_sig = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected_sig, received_sig)


def generate_webhook_secret() -> str:
    """
    Generate a secure random webhook secret.
    
    Returns:
        64-character hex string prefixed with 'whsec_'
    """
    return f"whsec_{secrets.token_hex(32)}"


# =============================================================================
# Webhook Management Endpoints
# =============================================================================

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

    - **url**: Webhook endpoint URL (HTTPS only in production)
    - **events**: Events to subscribe to
    - **is_active**: Whether webhook is active

    Returns the webhook with its secret for signature verification.
    
    **Important**: Save the secret securely! It is only shown once on creation.
    Use it to verify webhook signatures on your server.
    """
    webhook_service = WebhookService(db)

    webhook = await webhook_service.create_webhook(
        user_id=current_user.user_id,
        url=request.url,
        events=request.events,
    )

    await db.commit()

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

    await db.commit()

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

    await db.commit()


@router.post(
    "/{webhook_id}/rotate-secret",
    response_model=WebhookSecretResponse,
    summary="Rotate webhook secret",
    description="Generate a new secret for a webhook.",
)
async def rotate_webhook_secret(
    webhook_id: UUID,
    current_user: JWTUser,
    db: DBSession,
) -> WebhookSecretResponse:
    """
    Rotate (regenerate) the webhook secret.
    
    **Requires JWT authentication.**
    
    This will invalidate the old secret immediately.
    Make sure to update your webhook receiver with the new secret.
    
    - **webhook_id**: UUID of the webhook
    
    Returns the new secret. Save it securely - it won't be shown again!
    """
    # Get webhook
    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.user_id == current_user.user_id,
        )
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise NotFoundError(
            "Webhook not found",
            resource_type="webhook",
            resource_id=str(webhook_id),
        )

    # Generate new secret
    new_secret = generate_webhook_secret()
    webhook.secret = new_secret
    webhook.failure_count = 0  # Reset failure count on secret rotation

    await db.commit()

    logger.info(
        "Webhook secret rotated",
        webhook_id=str(webhook_id),
        user_id=str(current_user.user_id),
    )

    return WebhookSecretResponse(
        webhook_id=webhook.id,
        secret=new_secret,
    )


@router.post(
    "/verify-signature",
    response_model=WebhookVerifyResponse,
    summary="Verify webhook signature",
    description="Test webhook signature verification.",
)
async def verify_signature(
    request: WebhookVerifyRequest,
) -> WebhookVerifyResponse:
    """
    Verify a webhook signature.
    
    **No authentication required.**
    
    Use this endpoint to test your signature verification logic.
    
    - **payload**: The raw payload string
    - **signature**: The signature from X-Webhook-Signature header
    - **secret**: Your webhook secret
    
    Returns whether the signature is valid.
    """
    is_valid = verify_webhook_signature(
        payload=request.payload,
        signature=request.signature,
        secret=request.secret,
    )

    return WebhookVerifyResponse(
        valid=is_valid,
        message="Signature is valid" if is_valid else "Signature is invalid",
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
