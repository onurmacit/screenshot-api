"""
Application configuration using pydantic-settings
"""

from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ==========================================================================
    # Application
    # ==========================================================================
    APP_NAME: str = "ScreenshotAPI"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"

    # Admin emails (comma-separated in env)
    ADMIN_EMAILS: list[str] = ["onurmaciit@gmail.com"]

    # ==========================================================================
    # Server
    # ==========================================================================
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # ==========================================================================
    # Security
    # ==========================================================================
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12
    API_KEY_PREFIX: str = "sk_live_"
    SECRET_KEY_ENCRYPTION_KEY: str = ""  # Fernet key for encrypting API secret keys

    # ==========================================================================
    # Database
    # ==========================================================================
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/screenshot_api"
    # Supabase Session Mode limit: ~15 connections, use smaller pool
    # Keep total connections (pool_size + max_overflow) under 15
    DATABASE_POOL_SIZE: int = 8
    DATABASE_MAX_OVERFLOW: int = 4
    DATABASE_POOL_TIMEOUT: int = 30

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Return sync database URL for Alembic migrations."""
        # Remove asyncpg driver and asyncpg-specific query parameters
        url = self.DATABASE_URL.replace("+asyncpg", "")
        # Remove asyncpg-specific query parameters (statement_cache_size)
        if "?" in url:
            base_url, query_string = url.split("?", 1)
            # Filter out asyncpg-specific parameters
            params = []
            for param in query_string.split("&"):
                # Check if parameter name (before =) is statement_cache_size
                param_name = param.split("=")[0] if "=" in param else param
                if param_name != "statement_cache_size":
                    params.append(param)
            if params:
                url = f"{base_url}?{'&'.join(params)}"
            else:
                url = base_url
        return url

    # ==========================================================================
    # Redis
    # ==========================================================================
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_DB: int = 1
    REDIS_RATE_LIMIT_DB: int = 2
    # Reduced from 100 to 20 - we don't need that many connections
    # Each connection = potential commands, lower = fewer idle pings
    REDIS_MAX_CONNECTIONS: int = 20

    # ==========================================================================
    # Celery
    # ==========================================================================
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CELERY_TASK_TIME_LIMIT: int = 300
    CELERY_TASK_SOFT_TIME_LIMIT: int = 270

    # ==========================================================================
    # AWS S3
    # ==========================================================================
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = "screenshot-api-renders"
    AWS_S3_ENDPOINT_URL: str | None = None  # For MinIO compatibility (internal)
    AWS_S3_PUBLIC_URL: str | None = None  # Public URL for presigned URLs (external)

    # ==========================================================================
    # Stripe
    # ==========================================================================
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""

    # ==========================================================================
    # Email (SMTP)
    # ==========================================================================
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@screenshotapi.com"
    SMTP_FROM_NAME: str = "Screenshot API"

    # ==========================================================================
    # Go Renderer Microservice
    # ==========================================================================
    GO_RENDERER_URL: str = "http://go-renderer:8001"
    GO_RENDERER_TIMEOUT: int = 60  # seconds
    USE_GO_RENDERER: bool = True  # Toggle between Go and Playwright

    # ==========================================================================
    # Playwright / Browser (Legacy - used if USE_GO_RENDERER=False)
    # ==========================================================================
    BROWSER_POOL_SIZE: int = 2
    BROWSER_TIMEOUT_MS: int = 30000
    BROWSER_MAX_RENDERS_PER_CONTEXT: int = 100

    # ==========================================================================
    # Rate Limiting
    # ==========================================================================
    RATE_LIMIT_ENABLED: bool = True
    IP_RATE_LIMIT_PER_MINUTE: int = 60

    # Trusted proxies for X-Forwarded-For header
    # Only trust X-Forwarded-For from these IPs/CIDR ranges
    # Examples: ["10.0.0.1", "172.16.0.0/12", "192.168.1.0/24"]
    # Empty list = don't trust any forwarded headers (use direct IP only)
    TRUSTED_PROXIES: list[str] = []

    @field_validator("TRUSTED_PROXIES", mode="before")
    @classmethod
    def parse_trusted_proxies(cls, v: Any) -> list[str]:
        """Parse trusted proxies from string or list."""
        if isinstance(v, str):
            if not v.strip():
                return []
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [proxy.strip() for proxy in v.split(",") if proxy.strip()]
        return v if v else []

    # ==========================================================================
    # Storage
    # ==========================================================================
    RENDER_EXPIRY_DAYS: int = 90
    SIGNED_URL_EXPIRY_SECONDS: int = 3600
    MAX_FILE_SIZE_MB: int = 50

    # ==========================================================================
    # Monitoring
    # ==========================================================================
    SENTRY_DSN: str | None = None
    DATADOG_API_KEY: str | None = None

    # ==========================================================================
    # CORS
    # ==========================================================================
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # ==========================================================================
    # Frontend / Dashboard
    # ==========================================================================
    DASHBOARD_URL: str = "https://screenshotbeam.com"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v

    # ==========================================================================
    # Webhook Settings
    # ==========================================================================
    WEBHOOK_TIMEOUT_SECONDS: int = 10
    WEBHOOK_MAX_RETRIES: int = 5

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.APP_ENV == "development"

    @property
    def is_testing(self) -> bool:
        """Check if running in test environment."""
        return self.APP_ENV == "test"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
