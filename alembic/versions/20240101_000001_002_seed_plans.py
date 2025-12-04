"""Seed default plans

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Insert default plans
    plans_table = sa.table(
        "plans",
        sa.column("name", sa.String),
        sa.column("display_name", sa.String),
        sa.column("price_monthly", sa.Numeric),
        sa.column("price_yearly", sa.Numeric),
        sa.column("requests_per_month", sa.Integer),
        sa.column("max_concurrent_requests", sa.Integer),
        sa.column("max_timeout_ms", sa.Integer),
        sa.column("max_file_size_mb", sa.Integer),
        sa.column("features", postgresql.JSONB),
        sa.column("is_active", sa.Boolean),
    )

    op.bulk_insert(
        plans_table,
        [
            {
                "name": "free",
                "display_name": "Free",
                "price_monthly": 0,
                "price_yearly": 0,
                "requests_per_month": 100,
                "max_concurrent_requests": 1,
                "max_timeout_ms": 30000,
                "max_file_size_mb": 10,
                "features": {
                    "watermark": True,
                    "full_page": False,
                    "custom_css": False,
                    "webhooks": False,
                    "priority_queue": False,
                },
                "is_active": True,
            },
            {
                "name": "starter",
                "display_name": "Starter",
                "price_monthly": 19,
                "price_yearly": 190,
                "requests_per_month": 5000,
                "max_concurrent_requests": 3,
                "max_timeout_ms": 30000,
                "max_file_size_mb": 25,
                "features": {
                    "watermark": False,
                    "full_page": True,
                    "custom_css": False,
                    "webhooks": True,
                    "priority_queue": False,
                },
                "is_active": True,
            },
            {
                "name": "pro",
                "display_name": "Pro",
                "price_monthly": 49,
                "price_yearly": 490,
                "requests_per_month": 25000,
                "max_concurrent_requests": 10,
                "max_timeout_ms": 60000,
                "max_file_size_mb": 50,
                "features": {
                    "watermark": False,
                    "full_page": True,
                    "custom_css": True,
                    "webhooks": True,
                    "priority_queue": True,
                    "element_selector": True,
                    "geolocation": True,
                },
                "is_active": True,
            },
            {
                "name": "business",
                "display_name": "Business",
                "price_monthly": 149,
                "price_yearly": 1490,
                "requests_per_month": 100000,
                "max_concurrent_requests": 50,
                "max_timeout_ms": 120000,
                "max_file_size_mb": 100,
                "features": {
                    "watermark": False,
                    "full_page": True,
                    "custom_css": True,
                    "webhooks": True,
                    "priority_queue": True,
                    "element_selector": True,
                    "geolocation": True,
                    "custom_fonts": True,
                    "dedicated_support": True,
                },
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    # Delete seeded plans
    op.execute("DELETE FROM plans WHERE name IN ('free', 'starter', 'pro', 'business')")

