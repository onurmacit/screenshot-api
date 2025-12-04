"""
Integration Tests - Billing API
================================
Tests for billing and subscription endpoints.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient


class TestPlansEndpoint:
    """Tests for plans listing endpoint."""

    @pytest.mark.asyncio
    async def test_list_plans(
        self,
        client: AsyncClient,
        test_plan,
        test_pro_plan,
    ):
        """Test listing available plans."""
        response = await client.get("/api/v1/billing/plans")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    @pytest.mark.asyncio
    async def test_list_plans_only_active(
        self,
        client: AsyncClient,
        db_session,
    ):
        """Test that only active plans are listed."""
        from app.models.plan import Plan
        
        # Create inactive plan
        inactive_plan = Plan(
            id=uuid.uuid4(),
            name="inactive",
            display_name="Inactive Plan",
            price_monthly=999,
            price_yearly=9999,
            requests_per_month=100,
            requests_per_minute=10,
            max_resolution_width=1280,
            max_resolution_height=720,
            features=[],
            is_active=False,
        )
        db_session.add(inactive_plan)
        await db_session.commit()
        
        response = await client.get("/api/v1/billing/plans")
        
        assert response.status_code == 200
        data = response.json()
        # Inactive plan should not be in the list
        assert all(plan["name"] != "inactive" for plan in data)


class TestSubscriptionEndpoints:
    """Tests for subscription management endpoints."""

    @pytest.mark.asyncio
    async def test_get_current_subscription(
        self,
        client: AsyncClient,
        auth_headers,
        test_user,
        test_plan,
    ):
        """Test getting current subscription."""
        response = await client.get(
            "/api/v1/billing/subscription",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "plan" in data
        assert data["plan"]["name"] == test_plan.name

    @pytest.mark.asyncio
    async def test_subscribe_to_plan(
        self,
        client: AsyncClient,
        auth_headers,
        test_pro_plan,
        mock_stripe,
    ):
        """Test subscribing to a plan."""
        response = await client.post(
            "/api/v1/billing/subscribe",
            headers=auth_headers,
            json={
                "plan_id": str(test_pro_plan.id),
                "payment_method_id": "pm_test_123",
                "billing_period": "monthly",
            },
        )
        
        # Should redirect to Stripe checkout or return success
        assert response.status_code in [200, 201, 303]

    @pytest.mark.asyncio
    async def test_cancel_subscription(
        self,
        client: AsyncClient,
        pro_auth_headers,
        mock_stripe,
    ):
        """Test canceling subscription."""
        response = await client.post(
            "/api/v1/billing/subscription/cancel",
            headers=pro_auth_headers,
        )
        
        assert response.status_code in [200, 204]

    @pytest.mark.asyncio
    async def test_cancel_subscription_free_user(
        self,
        client: AsyncClient,
        auth_headers,  # Free user
    ):
        """Test canceling subscription for free user."""
        response = await client.post(
            "/api/v1/billing/subscription/cancel",
            headers=auth_headers,
        )
        
        # Free users can't cancel (no subscription)
        assert response.status_code in [400, 404]


class TestInvoicesEndpoint:
    """Tests for invoices endpoint."""

    @pytest.mark.asyncio
    async def test_list_invoices(
        self,
        client: AsyncClient,
        auth_headers,
    ):
        """Test listing invoices."""
        response = await client.get(
            "/api/v1/billing/invoices",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_invoice(
        self,
        client: AsyncClient,
        auth_headers,
        db_session,
        test_user,
    ):
        """Test getting specific invoice."""
        from app.models.invoice import Invoice
        
        invoice = Invoice(
            id=uuid.uuid4(),
            user_id=test_user.id,
            stripe_invoice_id="inv_test_123",
            amount=2900,
            currency="usd",
            status="paid",
        )
        db_session.add(invoice)
        await db_session.commit()
        
        response = await client.get(
            f"/api/v1/billing/invoices/{invoice.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(invoice.id)
        assert data["status"] == "paid"


class TestStripeWebhook:
    """Tests for Stripe webhook endpoint."""

    @pytest.mark.asyncio
    async def test_stripe_webhook_valid_signature(
        self,
        client: AsyncClient,
    ):
        """Test Stripe webhook with valid signature."""
        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_construct.return_value = {
                "type": "invoice.paid",
                "data": {
                    "object": {
                        "id": "inv_test_123",
                        "customer": "cus_test_123",
                        "amount_paid": 2900,
                    }
                }
            }
            
            response = await client.post(
                "/api/v1/billing/webhook/stripe",
                content=b'{"type": "invoice.paid"}',
                headers={
                    "Stripe-Signature": "test_signature",
                    "Content-Type": "application/json",
                },
            )
            
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_stripe_webhook_invalid_signature(
        self,
        client: AsyncClient,
    ):
        """Test Stripe webhook with invalid signature."""
        with patch("stripe.Webhook.construct_event") as mock_construct:
            from stripe.error import SignatureVerificationError
            mock_construct.side_effect = SignatureVerificationError(
                "Invalid signature",
                sig_header="invalid",
            )
            
            response = await client.post(
                "/api/v1/billing/webhook/stripe",
                content=b'{"type": "invoice.paid"}',
                headers={
                    "Stripe-Signature": "invalid_signature",
                    "Content-Type": "application/json",
                },
            )
            
            assert response.status_code == 400

