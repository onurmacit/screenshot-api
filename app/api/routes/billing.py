"""
Billing and subscription endpoints
"""

from typing import Optional

from fastapi import APIRouter, Header, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import DBSession, JWTUser, OptionalUser
from app.models import Plan, User
from app.schemas.billing import (
    InvoiceResponse,
    InvoicesListResponse,
    PlanResponse,
    PlansListResponse,
    SubscribeRequest,
    SubscriptionResponse,
)
from app.services.billing_service import BillingService
from app.utils.exceptions import NotFoundError, PaymentError

router = APIRouter()


@router.get(
    "/plans",
    response_model=PlansListResponse,
    summary="List plans",
    description="List all available subscription plans.",
)
async def list_plans(
    db: DBSession,
    current_user: OptionalUser = None,
) -> PlansListResponse:
    """
    List available subscription plans.

    No authentication required.
    """
    billing_service = BillingService(db)
    plans = await billing_service.list_plans(active_only=True)

    return PlansListResponse(
        plans=[
            PlanResponse(
                id=plan.id,
                name=plan.name,
                display_name=plan.display_name,
                price_monthly=plan.price_monthly,
                price_yearly=plan.price_yearly,
                requests_per_month=plan.requests_per_month,
                max_concurrent_requests=plan.max_concurrent_requests,
                max_timeout_ms=plan.max_timeout_ms,
                max_file_size_mb=plan.max_file_size_mb,
                features=plan.features or {},
                is_active=plan.is_active,
            )
            for plan in plans
        ]
    )


@router.get(
    "/plans/{plan_id}",
    response_model=PlanResponse,
    summary="Get plan",
    description="Get details of a specific plan.",
)
async def get_plan(
    plan_id: int,
    db: DBSession,
) -> PlanResponse:
    """
    Get plan details.

    No authentication required.
    """
    billing_service = BillingService(db)
    plan = await billing_service.get_plan(plan_id)

    if not plan:
        raise NotFoundError(
            "Plan not found",
            resource_type="plan",
            resource_id=str(plan_id),
        )

    return PlanResponse(
        id=plan.id,
        name=plan.name,
        display_name=plan.display_name,
        price_monthly=plan.price_monthly,
        price_yearly=plan.price_yearly,
        requests_per_month=plan.requests_per_month,
        max_concurrent_requests=plan.max_concurrent_requests,
        max_timeout_ms=plan.max_timeout_ms,
        max_file_size_mb=plan.max_file_size_mb,
        features=plan.features or {},
        is_active=plan.is_active,
    )


@router.post(
    "/subscribe",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subscribe to plan",
    description="Subscribe to a plan using Stripe.",
)
async def subscribe(
    request: SubscribeRequest,
    current_user: JWTUser,
    db: DBSession,
) -> SubscriptionResponse:
    """
    Subscribe to a plan.

    **Requires JWT authentication.**

    - **plan_id**: ID of the plan to subscribe to
    - **payment_method_id**: Stripe payment method ID
    - **billing_cycle**: Billing cycle (monthly or yearly)
    """
    # Get user from database
    result = await db.execute(
        select(User).where(User.id == current_user.user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError("User not found", resource_type="user")

    billing_service = BillingService(db)

    subscription = await billing_service.create_subscription(
        user=user,
        plan_id=request.plan_id,
        payment_method_id=request.payment_method_id,
        billing_cycle=request.billing_cycle,
    )

    return SubscriptionResponse(
        subscription_id=subscription["subscription_id"],
        status=subscription["status"],
        plan_id=subscription["plan_id"],
        plan_name=subscription["plan_name"],
        current_period_start=subscription["current_period_start"],
        current_period_end=subscription["current_period_end"],
    )


@router.post(
    "/cancel",
    response_model=dict,
    summary="Cancel subscription",
    description="Cancel the current subscription.",
)
async def cancel_subscription(
    current_user: JWTUser,
    db: DBSession,
    at_period_end: bool = Query(
        True,
        description="Cancel at end of billing period (default) or immediately",
    ),
) -> dict:
    """
    Cancel subscription.

    **Requires JWT authentication.**

    - **at_period_end**: If true, cancel at end of current period. If false, cancel immediately.
    """
    # Get user
    result = await db.execute(
        select(User).where(User.id == current_user.user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError("User not found", resource_type="user")

    billing_service = BillingService(db)

    result = await billing_service.cancel_subscription(
        user=user,
        at_period_end=at_period_end,
    )

    return result


@router.get(
    "/invoices",
    response_model=InvoicesListResponse,
    summary="List invoices",
    description="List invoices for the authenticated user.",
)
async def list_invoices(
    current_user: JWTUser,
    db: DBSession,
    limit: int = Query(20, ge=1, le=100, description="Number of invoices"),
) -> InvoicesListResponse:
    """
    List invoices.

    **Requires JWT authentication.**
    """
    billing_service = BillingService(db)
    invoices = await billing_service.list_invoices(
        user_id=current_user.user_id,
        limit=limit,
    )

    return InvoicesListResponse(
        invoices=[
            InvoiceResponse(
                id=invoice.id,
                stripe_invoice_id=invoice.stripe_invoice_id,
                amount=invoice.amount,
                currency=invoice.currency,
                status=invoice.status,
                period_start=invoice.period_start,
                period_end=invoice.period_end,
                paid_at=invoice.paid_at,
                created_at=invoice.created_at,
            )
            for invoice in invoices
        ],
        total=len(invoices),
    )


@router.post(
    "/webhook/stripe",
    status_code=status.HTTP_200_OK,
    summary="Stripe webhook",
    description="Handle Stripe webhook events.",
    include_in_schema=False,
)
async def stripe_webhook(
    request: Request,
    db: DBSession,
    stripe_signature: str = Header(alias="Stripe-Signature"),
) -> dict:
    """
    Handle Stripe webhook events.

    This endpoint is called by Stripe to notify of subscription events.
    """
    payload = await request.body()

    billing_service = BillingService(db)

    try:
        result = await billing_service.handle_webhook_event(
            payload=payload,
            signature=stripe_signature,
        )
        return result
    except PaymentError as e:
        return {"error": str(e), "processed": False}
