"""
FastAPI Application Entry Point
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes import auth, billing, health, renders, usage, webhooks
from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.redis import close_redis_pools, init_redis_pools
from app.middleware.error_handler import error_handler_middleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security import SecurityHeadersMiddleware
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
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

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
    prefix="/api/v1/renders",
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
async def root(request: Request) -> Response:
    """
    Root endpoint.
    
    - Browser requests (Accept: text/html) -> Redirect to dashboard login
    - API requests (Accept: application/json) -> Return API information
    """
    accept_header = request.headers.get("Accept", "").lower()
    user_agent = request.headers.get("User-Agent", "").lower()
    
    # Check if it's a browser request
    has_html = "text/html" in accept_header
    has_json = "application/json" in accept_header
    
    # Browser detection logic:
    # 1. If HTML is accepted but JSON is not -> browser
    # 2. If accept header is empty/*/* and User-Agent indicates browser -> browser
    is_browser_request = (
        has_html and not has_json
    ) or (
        (not accept_header or accept_header == "*/*" or "*/*" in accept_header)
        and any(
            browser in user_agent
            for browser in ["mozilla", "chrome", "safari", "firefox", "edge", "opera"]
        )
    )
    
    # Redirect browser requests to login page
    if is_browser_request:
        login_url = f"{settings.DASHBOARD_URL}/login"
        logger.debug(
            "Browser request detected, redirecting to login",
            login_url=login_url,
            accept=accept_header,
            user_agent=user_agent[:50] if user_agent else None,
        )
        return RedirectResponse(url=login_url, status_code=302)
    
    # Return API information for API clients
    logger.debug("API request detected, returning JSON", accept=accept_header)
    return JSONResponse(
        {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/api/v1/health",
        }
    )


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

