"""
Billing Tasks

Celery tasks for Stripe synchronization and billing operations.
Uses sync Celery tasks with asyncio.run for async operations.
"""

from typing import Any
from uuid import UUID

import stripe
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import Plan, User
from app.services.rate_limit_service import RATE_LIMITS, rate_limit_service
from app.utils.logger import get_logger
from app.workers.celery_app import celery_app, run_async

logger = get_logger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


@celery_app.task(
    name="app.workers.billing_tasks.sync_stripe_subscriptions",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(stripe.StripeError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=300,
)
def sync_stripe_subscriptions() -> dict[str, Any]:
    """
    Synchronize subscription status from Stripe.

    Runs every 6 hours to ensure local subscription state matches Stripe.

    Returns:
        Sync statistics
    """
    logger.info("Starting Stripe subscription sync")
    return run_async(_sync_stripe_subscriptions_async())


async def _sync_stripe_subscriptions_async() -> dict[str, Any]:
    """Async implementation of Stripe sync."""
    async with AsyncSessionLocal() as db:
        # Get all users with Stripe customer IDs
        result = await db.execute(
            select(User).where(User.stripe_customer_id.isnot(None))
        )
        users = result.scalars().all()

        synced = 0
        errors = 0
        updated = 0

        for user in users:
            try:
                # Get subscriptions from Stripe
                subscriptions = stripe.Subscription.list(
                    customer=user.stripe_customer_id,
                    status="all",
                    limit=1,
                )

                if subscriptions.data:
                    subscription = subscriptions.data[0]

                    # Get plan from subscription
                    if subscription.status == "active":
                        plan_id = subscription.metadata.get("plan_id")
                        if plan_id and int(plan_id) != user.plan_id:
                            user.plan_id = int(plan_id)
                            updated += 1

                    elif subscription.status in ("canceled", "unpaid"):
                        # Downgrade to free plan
                        free_plan_result = await db.execute(
                            select(Plan).where(Plan.name == "free")
                        )
                        free_plan = free_plan_result.scalar_one_or_none()
                        if free_plan and user.plan_id != free_plan.id:
                            user.plan_id = free_plan.id
                            updated += 1

                synced += 1

            except stripe.StripeError as e:
                logger.warning(
                    "Failed to sync user subscription",
                    user_id=str(user.id),
                    error=str(e),
                )
                errors += 1

        await db.commit()

        logger.info(
            "Stripe subscription sync completed",
            synced=synced,
            updated=updated,
            errors=errors,
        )

        return {
            "synced": synced,
            "updated": updated,
            "errors": errors,
        }


@celery_app.task(
    name="app.workers.billing_tasks.check_usage_limits",
    max_retries=2,
    default_retry_delay=30,
)
def check_usage_limits() -> dict[str, Any]:
    """
    Check users approaching usage limits.

    Runs every 15 minutes to trigger warning webhooks.

    Returns:
        Check statistics
    """
    logger.info("Starting usage limits check")
    return run_async(_check_usage_limits_async())


async def _check_usage_limits_async() -> dict[str, Any]:
    """Async implementation of usage limits check."""
    async with AsyncSessionLocal() as db:
        # Get all active users with plans
        result = await db.execute(
            select(User)
            .where(User.is_active == True)
        )
        users = result.scalars().all()

        warnings_sent = 0
        limits_reached = 0

        for user in users:
            try:
                # Get plan limits
                plan_name = "free"
                if user.plan:
                    plan_name = user.plan.name

                limits = RATE_LIMITS.get(plan_name, RATE_LIMITS["free"])
                monthly_limit = limits.get("per_month", 100)

                # Get current usage
                usage = await rate_limit_service.get_usage(user.id, "month")
                current_usage = usage.get("count", 0)

                # Calculate percentage
                percentage = (current_usage / monthly_limit * 100) if monthly_limit > 0 else 0

                # Trigger warnings
                if percentage >= 100:
                    # Limit reached
                    limits_reached += 1
                    from app.workers.webhook_tasks import trigger_event_webhooks

                    trigger_event_webhooks.delay(
                        str(user.id),
                        "usage.limit_reached",
                        {
                            "current_usage": current_usage,
                            "limit": monthly_limit,
                            "percentage": round(percentage, 2),
                        },
                    )

                elif percentage >= 90:
                    # Warning at 90%
                    warnings_sent += 1
                    from app.workers.webhook_tasks import trigger_event_webhooks

                    trigger_event_webhooks.delay(
                        str(user.id),
                        "usage.limit_warning",
                        {
                            "current_usage": current_usage,
                            "limit": monthly_limit,
                            "percentage": round(percentage, 2),
                            "warning_level": 90,
                        },
                    )

                elif percentage >= 80:
                    # Warning at 80%
                    warnings_sent += 1
                    from app.workers.webhook_tasks import trigger_event_webhooks

                    trigger_event_webhooks.delay(
                        str(user.id),
                        "usage.limit_warning",
                        {
                            "current_usage": current_usage,
                            "limit": monthly_limit,
                            "percentage": round(percentage, 2),
                            "warning_level": 80,
                        },
                    )

            except Exception as e:
                logger.warning(
                    "Failed to check usage for user",
                    user_id=str(user.id),
                    error=str(e),
                )

        logger.info(
            "Usage limits check completed",
            warnings_sent=warnings_sent,
            limits_reached=limits_reached,
        )

        return {
            "checked": len(users),
            "warnings_sent": warnings_sent,
            "limits_reached": limits_reached,
        }


@celery_app.task(
    name="app.workers.billing_tasks.process_overage_billing",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(stripe.StripeError, ConnectionError),
    retry_backoff=True,
)
def process_overage_billing(user_id: str) -> dict[str, Any]:
    """
    Process overage billing for a user.

    Called when a user exceeds their monthly limit.

    Args:
        user_id: User UUID string

    Returns:
        Billing result
    """
    logger.info("Processing overage billing", user_id=user_id)
    return run_async(_process_overage_billing_async(user_id))


async def _process_overage_billing_async(user_id: str) -> dict[str, Any]:
    """Async implementation of overage billing."""
    from decimal import Decimal

    async with AsyncSessionLocal() as db:
        # Get user
        result = await db.execute(
            select(User).where(User.id == UUID(user_id))
        )
        user = result.scalar_one_or_none()

        if not user:
            return {"error": "User not found"}

        if not user.stripe_customer_id:
            return {"error": "User has no Stripe customer"}

        # Get plan limits
        plan_name = "free"
        if user.plan:
            plan_name = user.plan.name

        limits = RATE_LIMITS.get(plan_name, RATE_LIMITS["free"])
        monthly_limit = limits.get("per_month", 100)

        # Get current usage
        usage = await rate_limit_service.get_usage(user.id, "month")
        current_usage = usage.get("count", 0)

        # Calculate overage
        overage_count = max(0, current_usage - monthly_limit)

        if overage_count == 0:
            return {"overage": 0}

        # Overage rate: $0.01 per request
        overage_rate = Decimal("0.01")
        overage_amount = overage_count * overage_rate

        try:
            # Create invoice item for overage
            stripe.InvoiceItem.create(
                customer=user.stripe_customer_id,
                amount=int(overage_amount * 100),  # Convert to cents
                currency="usd",
                description=f"API overage: {overage_count} requests over limit",
            )

            logger.info(
                "Overage billing created",
                user_id=user_id,
                overage_count=overage_count,
                overage_amount=float(overage_amount),
            )

            return {
                "overage_count": overage_count,
                "overage_amount": float(overage_amount),
                "status": "billed",
            }

        except stripe.StripeError as e:
            logger.error(
                "Failed to create overage billing",
                user_id=user_id,
                error=str(e),
            )
            raise  # Re-raise for retry


@celery_app.task(
    name="app.workers.billing_tasks.retry_failed_payments",
    max_retries=2,
    default_retry_delay=60,
)
def retry_failed_payments() -> dict[str, Any]:
    """
    Retry failed payment invoices.

    Attempts to retry payment for invoices in 'open' state.

    Returns:
        Retry statistics
    """
    logger.info("Starting failed payments retry")

    try:
        # Get open invoices
        invoices = stripe.Invoice.list(status="open", limit=100)

        retried = 0
        errors = 0

        for invoice in invoices.auto_paging_iter():
            try:
                # Attempt to pay
                invoice.pay()
                retried += 1
                logger.info("Invoice payment retried", invoice_id=invoice.id)
            except stripe.StripeError as e:
                logger.warning(
                    "Failed to retry invoice",
                    invoice_id=invoice.id,
                    error=str(e),
                )
                errors += 1

        logger.info(
            "Failed payments retry completed",
            retried=retried,
            errors=errors,
        )

        return {
            "retried": retried,
            "errors": errors,
        }

    except stripe.StripeError as e:
        logger.error("Failed to list invoices", error=str(e))
        return {"error": str(e)}
