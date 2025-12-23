"""
Health check endpoints

Optimized for minimal Redis commands - uses in-memory caching
to avoid hitting Redis on every health check request.
"""

import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.core.redis import redis_context
from app.core.s3 import get_s3_client

router = APIRouter()

# =============================================================================
# Health Check Cache - Reduces Redis commands significantly
# =============================================================================
_health_cache: dict[str, Any] = {}
_health_cache_ttl = 10  # Cache health status for 10 seconds


def _get_cached_health() -> dict | None:
    """Get cached health status if still valid."""
    if "data" in _health_cache and "expires" in _health_cache:
        if time.time() < _health_cache["expires"]:
            return _health_cache["data"]
    return None


def _set_cached_health(data: dict) -> None:
    """Cache health status."""
    _health_cache["data"] = data
    _health_cache["expires"] = time.time() + _health_cache_ttl


@router.get(
    "",
    summary="Health check",
    description="Comprehensive health check of all services.",
)
@router.get(
    "/",
    include_in_schema=False,
)
async def health_check() -> dict:
    """
    Comprehensive health check endpoint.

    Returns status of all critical services:
    - Database (PostgreSQL)
    - Cache (Redis)
    - Storage (S3)
    - Queue (Celery/Redis)
    
    **Optimized:** Results are cached for 10 seconds to reduce Redis commands.
    """
    # Check cache first - avoid Redis hit on every request
    cached = _get_cached_health()
    if cached:
        # Update timestamp but use cached service status
        cached["timestamp"] = datetime.now(UTC).isoformat()
        return JSONResponse(
            status_code=status.HTTP_200_OK if cached["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE,
            content=cached,
        )
    
    services = {}
    status_code = status.HTTP_200_OK

    # Check database - use direct connection to avoid dependency injection issues
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        services["database"] = "healthy"
    except Exception:
        services["database"] = "unhealthy"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    # Check Redis - use connection pool (no new connection!)
    try:
        async with redis_context("main") as redis:
            await redis.ping()
        services["redis"] = "healthy"
    except Exception:
        services["redis"] = "unhealthy"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    # Check S3
    try:
        async with get_s3_client() as s3:
            await s3.head_bucket(Bucket=settings.AWS_S3_BUCKET)
        services["s3"] = "healthy"
    except Exception:
        services["s3"] = "unhealthy"
        # S3 failure is not critical for health

    # Celery health is inferred from Redis connectivity
    services["celery"] = services["redis"]

    # Determine overall status
    unhealthy_services = [k for k, v in services.items() if v == "unhealthy"]
    critical_services = ["database", "redis"]
    critical_unhealthy = [s for s in unhealthy_services if s in critical_services]

    if not unhealthy_services:
        overall_status = "healthy"
    elif critical_unhealthy:
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    response_data = {
        "status": overall_status,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "timestamp": datetime.now(UTC).isoformat(),
        "services": services,
    }

    # Cache the result
    _set_cached_health(response_data)

    return JSONResponse(
        status_code=status_code,
        content=response_data,
    )


@router.get(
    "/ready",
    summary="Readiness probe",
    description="Kubernetes readiness probe endpoint.",
)
async def readiness_check() -> dict:
    """
    Kubernetes readiness probe.

    Returns 200 if the service is ready to accept traffic.
    Returns 503 if critical services are unavailable.
    
    **Optimized:** Uses connection pool instead of creating new connections.
    """
    try:
        # Check database connection
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        # Check Redis connection using pool (no new connection!)
        async with redis_context("main") as redis:
            await redis.ping()

        return {"ready": True}

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"ready": False, "error": str(e)},
        )


@router.get(
    "/live",
    summary="Liveness probe",
    description="Kubernetes liveness probe endpoint.",
)
async def liveness_check() -> dict:
    """
    Kubernetes liveness probe.

    Returns 200 if the service process is alive.
    This should be a very lightweight check.
    """
    return {"alive": True}


@router.get(
    "/version",
    summary="Version info",
    description="Get API version information.",
)
async def version_info() -> dict:
    """
    Get version information.

    Returns the current API version and environment.
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
    }
