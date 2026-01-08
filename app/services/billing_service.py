"""
Billing Service

Handles Stripe integration for subscriptions and payments.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import BillingInvoice, Plan, User
from app.utils.exceptions import NotFoundError, PaymentError
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class BillingService:
    """Service for billing operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Plans
    # =========================================================================

    async def list_plans(self, active_only: bool = True) -> list[Plan]:
        """
        List available subscription plans.

        Args:
            active_only: Only return active plans

        Returns:
            List of plans
        """
        query = select(Plan).order_by(Plan.price_monthly)
        if active_only:
            query = query.where(Plan.is_active)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_plan(self, plan_id: int) -> Plan | None:
        """
        Get plan by ID.

        Args:
            plan_id: Plan ID

        Returns:
            Plan or None
        """
        result = await self.db.execute(
            select(Plan).where(Plan.id == plan_id)
        )
        return result.scalar_one_or_none()

    async def get_plan_by_name(self, name: str) -> Plan | None:
        """
        Get plan by name.

        Args:
            name: Plan name

        Returns:
            Plan or None
        """
        result = await self.db.execute(
            select(Plan).where(Plan.name == name)
        )
        return result.scalar_one_or_none()

    # =========================================================================
    # Stripe Customer
    # =========================================================================

    async def create_or_get_customer(
        self,
        user: User,
        payment_method_id: str | None = None,
    ) -> str:
        """
        Create or get Stripe customer for user.

        Args:
            user: User model
            payment_method_id: Stripe payment method ID (optional)

        Returns:
            Stripe customer ID
        """
        if user.stripe_customer_id:
            return user.stripe_customer_id

        try:
            # Create Stripe customer
            customer_params: dict[str, Any] = {
                "email": user.email,
                "name": user.full_name,
                "metadata": {
                    "user_id": str(user.id),
                },
            }

            if payment_method_id:
                customer_params["payment_method"] = payment_method_id
                customer_params["invoice_settings"] = {
                    "default_payment_method": payment_method_id,
                }

            customer = stripe.Customer.create(**customer_params)

            # Save customer ID to user
            user.stripe_customer_id = customer.id
            await self.db.commit()

            logger.info(
                "Stripe customer created",
                user_id=str(user.id),
                customer_id=customer.id,
            )

            return customer.id

        except stripe.StripeError as e:
            logger.error(
                "Failed to create Stripe customer",
                user_id=str(user.id),
                error=str(e),
            )
            raise PaymentError(f"Failed to create customer: {str(e)}")

    # =========================================================================
    # Subscriptions
    # =========================================================================

    async def create_subscription(
        self,
        user: User,
        plan_id: int,
        payment_method_id: str,
        billing_cycle: str = "monthly",
    ) -> dict[str, Any]:
        """
        Create a new subscription.

        Args:
            user: User model
            plan_id: Plan ID to subscribe to
            payment_method_id: Stripe payment method ID
            billing_cycle: Billing cycle (monthly or yearly)

        Returns:
            Subscription details

        Raises:
            NotFoundError: If plan not found
            PaymentError: If subscription creation fails
        """
        # Get plan
        plan = await self.get_plan(plan_id)
        if not plan:
            raise NotFoundError("Plan not found", resource_type="plan")

        if not plan.stripe_price_id:
            raise PaymentError("Plan is not configured for billing")

        try:
            # Get or create Stripe customer
            customer_id = await self.create_or_get_customer(user, payment_method_id)

            # Attach payment method to customer
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id,
            )

            # Set as default payment method
            stripe.Customer.modify(
                customer_id,
                invoice_settings={
                    "default_payment_method": payment_method_id,
                },
            )

            # Create subscription
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": plan.stripe_price_id}],
                metadata={
                    "user_id": str(user.id),
                    "plan_id": str(plan.id),
                },
                expand=["latest_invoice.payment_intent"],
            )

            # Update user's plan
            user.plan_id = plan.id
            await self.db.commit()

            logger.info(
                "Subscription created",
                user_id=str(user.id),
                plan_id=plan.id,
                subscription_id=subscription.id,
            )

            return {
                "subscription_id": subscription.id,
                "status": subscription.status,
                "plan_id": plan.id,
                "plan_name": plan.name,
                "current_period_start": datetime.fromtimestamp(
                    subscription.current_period_start, tz=UTC
                ),
                "current_period_end": datetime.fromtimestamp(
                    subscription.current_period_end, tz=UTC
                ),
            }

        except stripe.StripeError as e:
            logger.error(
                "Failed to create subscription",
                user_id=str(user.id),
                error=str(e),
            )
            raise PaymentError(f"Failed to create subscription: {str(e)}")

    async def cancel_subscription(
        self,
        user: User,
        at_period_end: bool = True,
    ) -> dict[str, Any]:
        """
        Cancel user's subscription.

        Args:
            user: User model
            at_period_end: Cancel at end of period (default) or immediately

        Returns:
            Cancellation details
        """
        if not user.stripe_customer_id:
            raise PaymentError("User has no active subscription")

        try:
            # Get active subscriptions
            subscriptions = stripe.Subscription.list(
                customer=user.stripe_customer_id,
                status="active",
            )

            if not subscriptions.data:
                raise PaymentError("No active subscription found")

            subscription = subscriptions.data[0]

            if at_period_end:
                # Cancel at period end
                updated = stripe.Subscription.modify(
                    subscription.id,
                    cancel_at_period_end=True,
                )
            else:
                # Cancel immediately
                updated = stripe.Subscription.delete(subscription.id)

                # Downgrade to free plan
                free_plan = await self.get_plan_by_name("free")
                if free_plan:
                    user.plan_id = free_plan.id
                    await self.db.commit()

            logger.info(
                "Subscription cancelled",
                user_id=str(user.id),
                subscription_id=subscription.id,
                at_period_end=at_period_end,
            )

            return {
                "subscription_id": subscription.id,
                "status": updated.status if hasattr(updated, "status") else "cancelled",
                "cancel_at_period_end": at_period_end,
            }

        except stripe.StripeError as e:
            logger.error(
                "Failed to cancel subscription",
                user_id=str(user.id),
                error=str(e),
            )
            raise PaymentError(f"Failed to cancel subscription: {str(e)}")

    # =========================================================================
    # Invoices
    # =========================================================================

    async def list_invoices(
        self,
        user_id: UUID,
        limit: int = 20,
    ) -> list[BillingInvoice]:
        """
        List invoices for a user.

        Args:
            user_id: User UUID
            limit: Maximum number of invoices

        Returns:
            List of invoices
        """
        result = await self.db.execute(
            select(BillingInvoice)
            .where(BillingInvoice.user_id == user_id)
            .order_by(BillingInvoice.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def sync_invoice_from_stripe(
        self,
        stripe_invoice: Any,
        user_id: UUID,
    ) -> BillingInvoice:
        """
        Sync invoice from Stripe webhook.

        Args:
            stripe_invoice: Stripe invoice object
            user_id: User UUID

        Returns:
            Synced invoice
        """
        # Check if invoice exists
        result = await self.db.execute(
            select(BillingInvoice).where(
                BillingInvoice.stripe_invoice_id == stripe_invoice.id
            )
        )
        invoice = result.scalar_one_or_none()

        if invoice:
            # Update existing
            invoice.status = stripe_invoice.status
            if stripe_invoice.status == "paid":
                invoice.paid_at = datetime.fromtimestamp(
                    stripe_invoice.status_transitions.paid_at, tz=UTC
                )
        else:
            # Create new
            invoice = BillingInvoice(
                user_id=user_id,
                stripe_invoice_id=stripe_invoice.id,
                amount=Decimal(stripe_invoice.amount_paid) / 100,
                currency=stripe_invoice.currency.upper(),
                status=stripe_invoice.status,
                period_start=date.fromtimestamp(stripe_invoice.period_start),
                period_end=date.fromtimestamp(stripe_invoice.period_end),
            )
            self.db.add(invoice)

        await self.db.commit()
        await self.db.refresh(invoice)

        return invoice

    # =========================================================================
    # Webhook Handling
    # =========================================================================

    async def handle_webhook_event(
        self,
        payload: bytes,
        signature: str,
    ) -> dict[str, Any]:
        """
        Handle Stripe webhook event.

        Args:
            payload: Raw webhook payload
            signature: Stripe signature header

        Returns:
            Processing result
        """
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                settings.STRIPE_WEBHOOK_SECRET,
            )
        except ValueError:
            raise PaymentError("Invalid payload")
        except stripe.SignatureVerificationError:
            raise PaymentError("Invalid signature")

        event_type = event.type
        data = event.data.object

        logger.info("Processing Stripe webhook", event_type=event_type)

        handlers = {
            "customer.subscription.created": self._handle_subscription_created,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.payment_succeeded": self._handle_payment_succeeded,
            "invoice.payment_failed": self._handle_payment_failed,
        }

        handler = handlers.get(event_type)
        if handler:
            await handler(data)

        return {"event_type": event_type, "processed": True}

    async def _handle_subscription_created(self, subscription: Any) -> None:
        """Handle subscription.created event."""
        user_id = subscription.metadata.get("user_id")
        if user_id:
            logger.info(
                "Subscription created via webhook",
                subscription_id=subscription.id,
                user_id=user_id,
            )

    async def _handle_subscription_updated(self, subscription: Any) -> None:
        """Handle subscription.updated event."""
        user_id = subscription.metadata.get("user_id")
        plan_id = subscription.metadata.get("plan_id")

        if user_id and plan_id:
            result = await self.db.execute(
                select(User).where(User.id == UUID(user_id))
            )
            user = result.scalar_one_or_none()
            if user:
                user.plan_id = int(plan_id)
                await self.db.commit()

            logger.info(
                "Subscription updated via webhook",
                subscription_id=subscription.id,
                user_id=user_id,
            )

    async def _handle_subscription_deleted(self, subscription: Any) -> None:
        """Handle subscription.deleted event."""
        user_id = subscription.metadata.get("user_id")

        if user_id:
            # Downgrade to free plan
            result = await self.db.execute(
                select(User).where(User.id == UUID(user_id))
            )
            user = result.scalar_one_or_none()
            if user:
                free_plan = await self.get_plan_by_name("free")
                if free_plan:
                    user.plan_id = free_plan.id
                    await self.db.commit()

            logger.info(
                "Subscription deleted via webhook",
                subscription_id=subscription.id,
                user_id=user_id,
            )

    async def _handle_payment_succeeded(self, invoice: Any) -> None:
        """Handle invoice.payment_succeeded event."""
        customer_id = invoice.customer

        # Find user by customer ID
        result = await self.db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()

        if user:
            await self.sync_invoice_from_stripe(invoice, user.id)

            logger.info(
                "Payment succeeded",
                invoice_id=invoice.id,
                user_id=str(user.id),
            )

    async def _handle_payment_failed(self, invoice: Any) -> None:
        """Handle invoice.payment_failed event."""
        customer_id = invoice.customer

        result = await self.db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()

        if user:
            logger.warning(
                "Payment failed",
                invoice_id=invoice.id,
                user_id=str(user.id),
            )
            # Could trigger notification here

    # =========================================================================
    # Usage & Overage
    # =========================================================================

    async def calculate_overage(
        self,
        user_id: UUID,
        current_usage: int,
        plan_limit: int,
    ) -> dict[str, Any]:
        """
        Calculate overage charges.

        Args:
            user_id: User UUID
            current_usage: Current usage count
            plan_limit: Plan's monthly limit

        Returns:
            Overage details
        """
        overage_count = max(0, current_usage - plan_limit)
        overage_rate = Decimal("0.01")  # $0.01 per request over limit
        overage_amount = overage_count * overage_rate

        return {
            "current_usage": current_usage,
            "plan_limit": plan_limit,
            "overage_count": overage_count,
            "overage_rate": float(overage_rate),
            "overage_amount": float(overage_amount),
        }

