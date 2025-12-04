#!/usr/bin/env python3
"""
CLI tool for generating API keys

Usage:
    python scripts/generate_api_key.py --email user@example.com --name "My API Key"
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import generate_api_key
from app.models import APIKey, User


async def create_api_key(
    email: str,
    name: str,
    scopes: list[str] | None = None,
) -> None:
    """Create an API key for a user."""
    print(f"Creating API key for: {email}")

    async with AsyncSessionLocal() as session:
        # Find user
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if not user:
            print(f"Error: User with email '{email}' not found")
            return

        # Generate API key
        full_key, key_prefix, key_hash = generate_api_key()

        # Default scopes
        if scopes is None:
            scopes = ["renders:read", "renders:write"]

        # Create API key record
        api_key = APIKey(
            user_id=user.id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=name,
            scopes=scopes,
            is_active=True,
        )

        session.add(api_key)
        await session.commit()

        print("\n" + "=" * 60)
        print("API Key Created Successfully!")
        print("=" * 60)
        print(f"Name: {name}")
        print(f"Key Prefix: {key_prefix}...")
        print(f"Scopes: {', '.join(scopes)}")
        print("\n⚠️  IMPORTANT: Save this key - it won't be shown again!")
        print("=" * 60)
        print(f"\n{full_key}\n")
        print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate API key for a user"
    )
    parser.add_argument(
        "--email",
        required=True,
        help="User email address",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Name for the API key",
    )
    parser.add_argument(
        "--scopes",
        nargs="+",
        default=None,
        help="Scopes for the API key (default: renders:read renders:write)",
    )

    args = parser.parse_args()
    asyncio.run(create_api_key(args.email, args.name, args.scopes))


if __name__ == "__main__":
    main()

