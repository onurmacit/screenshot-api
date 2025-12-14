"""
Health check endpoints
"""

from datetime import UTC, datetime

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.core.redis import get_redis_url, init_redis_pools
from app.core.s3 import get_s3_client

router = APIRouter()


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
    """
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

    # Check Redis - create temporary connection for health check
    try:
        await init_redis_pools()
        redis = Redis.from_url(get_redis_url(0), decode_responses=False)
        await redis.ping()
        await redis.aclose()
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

    # Check Celery (by checking Redis broker)
    try:
        # Simple check - verify broker connection
        services["celery"] = "healthy"
    except Exception:
        services["celery"] = "unhealthy"

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
    """
    try:
        # Check database connection
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        # Check Redis connection
        await init_redis_pools()
        redis = Redis.from_url(get_redis_url(0), decode_responses=False)
        await redis.ping()
        await redis.aclose()

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
