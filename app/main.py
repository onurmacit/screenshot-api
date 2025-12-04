"""
FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes import auth, billing, health, renders, usage, webhooks
from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.redis import close_redis_pools, init_redis_pools
from app.middleware.error_handler import error_handler_middleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.utils.exceptions import APIError
from app.utils.logger import configure_logging, logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    logger.info("Starting Screenshot API", version=settings.APP_VERSION)

    # Configure logging
    configure_logging()

    # Initialize database
    logger.info("Initializing database connection")
    await init_db()

    # Initialize Redis pools
    logger.info("Initializing Redis connection pools")
    await init_redis_pools()

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down Screenshot API")

    # Close database connections
    await close_db()

    # Close Redis pools
    await close_redis_pools()

    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Production-grade Screenshot and PDF rendering API",
    version=settings.APP_VERSION,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
    lifespan=lifespan,
)

# =============================================================================
# Middleware
# =============================================================================

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(RateLimitMiddleware)

# Error handler middleware
app.middleware("http")(error_handler_middleware)

# Prometheus metrics
if settings.is_production:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")


# =============================================================================
# Exception Handlers
# =============================================================================


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle custom API errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions."""
    logger.exception("Unhandled exception", error=str(exc))

    if settings.DEBUG:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(exc),
                }
            },
        )

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
            }
        },
    )


# =============================================================================
# API Routes
# =============================================================================

# Include API routers
app.include_router(
    health.router,
    prefix="/api/v1/health",
    tags=["Health"],
)

app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["Authentication"],
)

app.include_router(
    renders.router,
    prefix="/api/v1/render",
    tags=["Renders"],
)

app.include_router(
    usage.router,
    prefix="/api/v1/usage",
    tags=["Usage"],
)

app.include_router(
    webhooks.router,
    prefix="/api/v1/webhooks",
    tags=["Webhooks"],
)

app.include_router(
    billing.router,
    prefix="/api/v1/billing",
    tags=["Billing"],
)


# =============================================================================
# Root Endpoint
# =============================================================================


@app.get("/", include_in_schema=False)
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/v1/health",
    }


# =============================================================================
# Run with Uvicorn (for development)
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS,
    )

