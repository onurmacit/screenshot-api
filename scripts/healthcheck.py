#!/usr/bin/env python3
"""
Screenshot API - Health Check Script
=====================================
Performs comprehensive health checks for the application.
"""

import asyncio
import sys
from typing import Optional

import httpx
import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def check_database(database_url: str) -> tuple[bool, str]:
    """Check database connectivity."""
    try:
        engine = create_async_engine(database_url)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True, "Database is healthy"
    except Exception as e:
        return False, f"Database error: {e}"


async def check_redis(redis_url: str) -> tuple[bool, str]:
    """Check Redis connectivity."""
    try:
        client = redis.from_url(redis_url)
        await client.ping()
        await client.close()
        return True, "Redis is healthy"
    except Exception as e:
        return False, f"Redis error: {e}"


async def check_api(api_url: str) -> tuple[bool, str]:
    """Check API health endpoint."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_url}/api/v1/health", timeout=5.0)
            if response.status_code == 200:
                return True, "API is healthy"
            return False, f"API returned status {response.status_code}"
    except Exception as e:
        return False, f"API error: {e}"


async def main(
    database_url: Optional[str] = None,
    redis_url: Optional[str] = None,
    api_url: Optional[str] = None,
) -> int:
    """Run all health checks."""
    import os

    database_url = database_url or os.getenv("DATABASE_URL")
    redis_url = redis_url or os.getenv("REDIS_URL")
    api_url = api_url or os.getenv("API_URL", "http://localhost:8000")

    results = []

    if database_url:
        success, message = await check_database(database_url)
        results.append(("Database", success, message))
        print(f"{'✓' if success else '✗'} {message}")

    if redis_url:
        success, message = await check_redis(redis_url)
        results.append(("Redis", success, message))
        print(f"{'✓' if success else '✗'} {message}")

    if api_url:
        success, message = await check_api(api_url)
        results.append(("API", success, message))
        print(f"{'✓' if success else '✗'} {message}")

    # Return exit code
    all_healthy = all(result[1] for result in results)
    return 0 if all_healthy else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

