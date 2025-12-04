#!/usr/bin/env python3
"""
Database seeding script

Seeds the database with initial data including plans and optionally test users.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine
from app.core.security import hash_password
from app.models import Plan, User


async def seed_plans(session: AsyncSession) -> None:
    """Seed default plans if they don't exist."""
    print("Checking plans...")

    # Check if plans already exist
    result = await session.execute(select(Plan).limit(1))
    if result.scalar_one_or_none():
        print("Plans already exist, skipping...")
        return

    plans = [
        Plan(
            name="free",
            display_name="Free",
            price_monthly=0,
            price_yearly=0,
            requests_per_month=100,
            max_concurrent_requests=1,
            max_timeout_ms=30000,
            max_file_size_mb=10,
            features={
                "watermark": True,
                "full_page": False,
                "custom_css": False,
                "webhooks": False,
                "priority_queue": False,
            },
            is_active=True,
        ),
        Plan(
            name="starter",
            display_name="Starter",
            price_monthly=19,
            price_yearly=190,
            requests_per_month=5000,
            max_concurrent_requests=3,
            max_timeout_ms=30000,
            max_file_size_mb=25,
            features={
                "watermark": False,
                "full_page": True,
                "custom_css": False,
                "webhooks": True,
                "priority_queue": False,
            },
            is_active=True,
        ),
        Plan(
            name="pro",
            display_name="Pro",
            price_monthly=49,
            price_yearly=490,
            requests_per_month=25000,
            max_concurrent_requests=10,
            max_timeout_ms=60000,
            max_file_size_mb=50,
            features={
                "watermark": False,
                "full_page": True,
                "custom_css": True,
                "webhooks": True,
                "priority_queue": True,
                "element_selector": True,
                "geolocation": True,
            },
            is_active=True,
        ),
        Plan(
            name="business",
            display_name="Business",
            price_monthly=149,
            price_yearly=1490,
            requests_per_month=100000,
            max_concurrent_requests=50,
            max_timeout_ms=120000,
            max_file_size_mb=100,
            features={
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
            is_active=True,
        ),
    ]

    for plan in plans:
        session.add(plan)
        print(f"  Created plan: {plan.name}")

    await session.commit()
    print("Plans seeded successfully!")


async def seed_test_user(session: AsyncSession) -> None:
    """Seed a test user for development."""
    print("Checking test user...")

    # Check if test user exists
    result = await session.execute(
        select(User).where(User.email == "test@example.com")
    )
    if result.scalar_one_or_none():
        print("Test user already exists, skipping...")
        return

    # Get free plan
    result = await session.execute(select(Plan).where(Plan.name == "free"))
    free_plan = result.scalar_one_or_none()

    test_user = User(
        email="test@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="Test User",
        plan_id=free_plan.id if free_plan else None,
        is_active=True,
        email_verified=True,
    )

    session.add(test_user)
    await session.commit()
    print(f"Test user created: {test_user.email}")


async def main() -> None:
    """Main seeding function."""
    print("=" * 50)
    print("Screenshot API - Database Seeder")
    print("=" * 50)

    async with AsyncSessionLocal() as session:
        # Test database connection
        try:
            await session.execute(text("SELECT 1"))
            print("Database connection: OK")
        except Exception as e:
            print(f"Database connection failed: {e}")
            return

        # Seed data
        await seed_plans(session)
        await seed_test_user(session)

    print("=" * 50)
    print("Seeding complete!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())

