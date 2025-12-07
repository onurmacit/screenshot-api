"""
FastAPI dependencies for authentication, rate limiting, etc.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_rate_limit_redis, get_redis
from app.core.security import hash_api_key, verify_access_token, verify_api_key_format
from app.models import APIKey, User
from app.services.cache_service import cache_service
from app.services.rate_limit_service import rate_limit_service
from app.utils.exceptions import (
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
)
from app.utils.helpers import utc_now
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser:
    """Current authenticated user data."""

    def __init__(
        self,
        user_id: UUID,
        email: str | None = None,
        plan_id: int | None = None,
        plan_name: str | None = None,
        plan_features: dict | None = None,
        api_key_id: UUID | None = None,
        scopes: list[str] | None = None,
    ):
        self.user_id = user_id
        self.email = email
        self.plan_id = plan_id
        self.plan_name = plan_name or "free"
        self.plan_features = plan_features or {}
        self.api_key_id = api_key_id
        self.scopes = scopes or []

    def has_scope(self, scope: str) -> bool:
        """Check if user has a specific scope."""
        return scope in self.scopes

    def has_feature(self, feature: str) -> bool:
        """Check if user's plan has a specific feature."""
        return self.plan_features.get(feature, False)


async def get_current_user_from_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    """
    Dependency to get current user from JWT token.

    Used for endpoints that require JWT authentication.
    """
    if not credentials:
        raise AuthenticationError("Missing authorization header")

    token = credentials.credentials
    payload = verify_access_token(token)

    if not payload:
        raise AuthenticationError("Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token payload")

    # Fetch user from database
    result = await db.execute(
        select(User).where(User.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationError("User not found")

    if not user.is_active:
        raise AuthenticationError("User account is deactivated")

    # Get plan info
    plan_name = "free"
    plan_features = {}
    if user.plan:
        plan_name = user.plan.name
        plan_features = user.plan.features or {}

    return CurrentUser(
        user_id=user.id,
        email=user.email,
        plan_id=user.plan_id,
        plan_name=plan_name,
        plan_features=plan_features,
    )


async def get_current_user_from_api_key(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    redis: Annotated[Redis, Depends(get_redis)] = None,
) -> CurrentUser:
    """
    Dependency to get current user from API key.

    Used for endpoints that require API key authentication.
    """
    if not x_api_key:
        raise AuthenticationError("Missing X-API-Key header")

    if not verify_api_key_format(x_api_key):
        raise AuthenticationError("Invalid API key format")

    # Hash the API key for lookup
    key_hash = hash_api_key(x_api_key)

    # Check cache first
    cached = await cache_service.get_api_key_cache(key_hash)
    if cached:
        return CurrentUser(
            user_id=UUID(cached["user_id"]),
            email=cached.get("email"),
            plan_id=cached.get("plan_id"),
            plan_name=cached.get("plan_name", "free"),
            plan_features=cached.get("plan_features", {}),
            api_key_id=UUID(cached["api_key_id"]),
            scopes=cached.get("scopes", []),
        )

    # Look up API key in database
    result = await db.execute(
        select(APIKey).where(APIKey.key_hash == key_hash)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise AuthenticationError("Invalid API key")

    if not api_key.is_active:
        raise AuthenticationError("API key is deactivated")

    if api_key.is_expired:
        raise AuthenticationError("API key has expired")

    # Get user
    result = await db.execute(
        select(User).where(User.id == api_key.user_id)
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise AuthenticationError("User not found or inactive")

    # Get plan info
    plan_name = "free"
    plan_features = {}
    if user.plan:
        plan_name = user.plan.name
        plan_features = user.plan.features or {}

    # Update last used
    api_key.last_used_at = utc_now()
    await db.commit()

    # Cache the result
    cache_data = {
        "user_id": str(user.id),
        "email": user.email,
        "plan_id": user.plan_id,
        "plan_name": plan_name,
        "plan_features": plan_features,
        "api_key_id": str(api_key.id),
        "scopes": api_key.scopes or [],
    }
    await cache_service.set_api_key_cache(key_hash, cache_data)

    return CurrentUser(
        user_id=user.id,
        email=user.email,
        plan_id=user.plan_id,
        plan_name=plan_name,
        plan_features=plan_features,
        api_key_id=api_key.id,
        scopes=api_key.scopes or [],
    )


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> CurrentUser | None:
    """
    Dependency to optionally get current user.

    Returns None if no authentication is provided.
    """
    if credentials:
        payload = verify_access_token(credentials.credentials)
        if payload:
            user_id = payload.get("sub")
            if user_id:
                result = await db.execute(
                    select(User).where(User.id == UUID(user_id))
                )
                user = result.scalar_one_or_none()
                if user and user.is_active:
                    plan_name = "free"
                    plan_features = {}
                    if user.plan:
                        plan_name = user.plan.name
                        plan_features = user.plan.features or {}
                    return CurrentUser(
                        user_id=user.id,
                        email=user.email,
                        plan_id=user.plan_id,
                        plan_name=plan_name,
                        plan_features=plan_features,
                    )

    return None


def require_scope(required_scope: str):
    """
    Dependency factory to require a specific scope.

    Usage:
        @router.post("/", dependencies=[Depends(require_scope("renders:write"))])
    """

    async def scope_checker(
        current_user: Annotated[CurrentUser, Depends(get_current_user_from_api_key)],
    ) -> CurrentUser:
        if not current_user.has_scope(required_scope):
            raise AuthorizationError(
                f"Missing required scope: {required_scope}",
                details={"required_scope": required_scope},
            )
        return current_user

    return scope_checker


async def check_rate_limit(
    current_user: Annotated[CurrentUser, Depends(get_current_user_from_api_key)],
) -> CurrentUser:
    """
    Dependency to check rate limits.

    Raises RateLimitError if user has exceeded their limits.
    """
    if not settings.RATE_LIMIT_ENABLED:
        return current_user

    try:
        await rate_limit_service.check_rate_limit(
            user_id=current_user.user_id,
            plan_name=current_user.plan_name,
            api_key_id=current_user.api_key_id,
        )
    except RateLimitError:
        raise

    return current_user


# Type aliases for cleaner dependency injection
DBSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]
RateLimitRedis = Annotated[Redis, Depends(get_rate_limit_redis)]
JWTUser = Annotated[CurrentUser, Depends(get_current_user_from_token)]
APIKeyUser = Annotated[CurrentUser, Depends(get_current_user_from_api_key)]
RateLimitedUser = Annotated[CurrentUser, Depends(check_rate_limit)]
OptionalUser = Annotated[CurrentUser | None, Depends(get_optional_user)]
