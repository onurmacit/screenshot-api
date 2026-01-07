"""
Health check endpoints

Optimized for minimal Redis commands - uses in-memory caching
to avoid hitting Redis on every health check request.
"""

import os
import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.core.redis import redis_context
from app.core.s3 import get_s3_client

router = APIRouter()

# =============================================================================
# Startup Time and Health Cache
# =============================================================================
_startup_time = time.time()  # Track when service started
_health_cache: dict[str, Any] = {}
_health_cache_ttl = 10  # Cache health status for 10 seconds


def _get_uptime_seconds() -> float:
    """Get service uptime in seconds."""
    return time.time() - _startup_time


def _format_uptime(seconds: float) -> str:
    """Format uptime as human-readable string."""
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def _get_memory_usage() -> dict:
    """Get memory usage statistics."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        return {
            "rss_mb": round(memory_info.rss / 1024 / 1024, 2),
            "vms_mb": round(memory_info.vms / 1024 / 1024, 2),
            "percent": round(process.memory_percent(), 2),
        }
    except ImportError:
        # psutil not installed
        return {"error": "psutil not available"}
    except Exception:
        return {"error": "failed to get memory info"}


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
    Public health check endpoint.

    Returns basic status of service (no sensitive details).
    For detailed metrics, use /health/stats (admin-only).
    
    **Optimized:** Results are cached for 10 seconds to reduce Redis commands.
    """
    # Check cache first - avoid Redis hit on every request
    cached = _get_cached_health()
    if cached:
        # Return only public fields from cache
        return JSONResponse(
            status_code=status.HTTP_200_OK if cached["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": cached["status"],
                "timestamp": datetime.now(UTC).isoformat(),
            },
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

    # Get uptime and pool stats for internal cache (used by /stats endpoint)
    uptime_seconds = _get_uptime_seconds()
    
    from app.core.database import get_pool_stats
    pool_stats = {}
    try:
        pool_stats = get_pool_stats()
    except Exception:
        pool_stats = {"error": "failed to get pool stats"}
    
    # Full response for cache (used by /stats endpoint)
    full_response_data = {
        "status": overall_status,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "timestamp": datetime.now(UTC).isoformat(),
        "uptime": {
            "seconds": round(uptime_seconds, 2),
            "human": _format_uptime(uptime_seconds),
        },
        "memory": _get_memory_usage(),
        "db_pool": pool_stats,
        "services": services,
    }

    # Cache the full result (for /stats endpoint)
    _set_cached_health(full_response_data)

    # Return only public info
    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall_status,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


@router.get(
    "/stats",
    summary="Detailed health stats (Admin only)",
    description="Returns detailed system metrics including memory, db pool, and service status. Requires admin secret.",
)
async def health_stats(
    request: Request,
) -> dict:
    """
    Admin-only detailed health stats endpoint.
    
    Returns:
    - All service health statuses
    - Memory usage (RSS, VMS, percent)
    - Database connection pool stats
    - Uptime information
    - Version and environment info
    
    **Authentication:** Requires X-Admin-Key header with admin secret.
    """
    from app.core.config import settings as app_settings
    
    # For now, use SECRET_KEY as admin key
    admin_secret = app_settings.SECRET_KEY
    
    # Get admin key from header
    x_admin_key = request.headers.get("x-admin-key")
    
    if not x_admin_key or x_admin_key != admin_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Admin-Key header",
        )
    
    # Get cached health data (has all the details)
    cached = _get_cached_health()
    if cached:
        return JSONResponse(status_code=status.HTTP_200_OK, content=cached)
    
    # If no cache, trigger a fresh health check
    # This ensures stats are always available
    from app.core.database import get_pool_stats
    
    uptime_seconds = _get_uptime_seconds()
    pool_stats = {}
    try:
        pool_stats = get_pool_stats()
    except Exception:
        pool_stats = {"error": "failed to get pool stats"}
    
    response_data = {
        "status": "unknown",
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "timestamp": datetime.now(UTC).isoformat(),
        "uptime": {
            "seconds": round(uptime_seconds, 2),
            "human": _format_uptime(uptime_seconds),
        },
        "memory": _get_memory_usage(),
        "db_pool": pool_stats,
        "services": {"note": "Call /health first to get service status"},
    }
    
    return JSONResponse(status_code=status.HTTP_200_OK, content=response_data)


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


@router.get(
    "/sentry-debug",
    summary="Sentry debug",
    description="Trigger a test error for Sentry.",
    include_in_schema=False,
)
async def sentry_debug() -> dict:
    """
    Trigger a test error for Sentry integration verification.
    
    This endpoint intentionally raises a ZeroDivisionError.
    """
    division_by_zero = 1 / 0
    return {"message": "This will never be returned"}
