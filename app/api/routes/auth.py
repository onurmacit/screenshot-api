"""
Authentication endpoints
"""

from uuid import UUID

from fastapi import APIRouter, Request, status

from app.api.dependencies import DBSession, JWTUser
from app.schemas.auth import (
    APIKeyCreate,
    APIKeyCreateResponse,
    APIKeyResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    SocialLoginRequest,
    TokenRefreshRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account and return access tokens.",
)
async def register(
    request: RegisterRequest,
    db: DBSession,
) -> RegisterResponse:
    """
    Register a new user.

    - **email**: Valid email address (must be unique)
    - **password**: Password (min 8 chars, 1 uppercase, 1 lowercase, 1 digit)
    - **full_name**: Optional full name
    """
    auth_service = AuthService(db)

    user, access_token, refresh_token = await auth_service.register_user(
        email=request.email,
        password=request.password,
        full_name=request.full_name,
    )

    return RegisterResponse(
        user_id=user.id,
        email=user.email,
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login",
    description="Authenticate with email and password to get access tokens.",
)
async def login(
    request: LoginRequest,
    req: Request,
    db: DBSession,
) -> LoginResponse:
    """
    Login and get access tokens.

    - **email**: User email address
    - **password**: User password
    """
    auth_service = AuthService(db)

    # Get client info
    ip_address = req.client.host if req.client else None
    device_info = req.headers.get("User-Agent")

    user, access_token, refresh_token, expires_in = await auth_service.login(
        email=request.email,
        password=request.password,
        ip_address=ip_address,
        device_info=device_info,
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.post(
    "/social-login",
    response_model=LoginResponse,
    summary="Social Login",
    description="Authenticate via a social provider (Google/GitHub) and get access tokens.",
)
async def social_login(
    request: SocialLoginRequest,
    req: Request,
    db: DBSession,
) -> LoginResponse:
    """
    Login via social provider.
    """
    auth_service = AuthService(db)

    # Get client info
    ip_address = req.client.host if req.client else None
    device_info = req.headers.get("User-Agent")

    user, access_token, refresh_token, expires_in = await auth_service.social_login(
        provider=request.provider,
        token=request.token,
        full_name=request.full_name,
        ip_address=ip_address,
        device_info=device_info,
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Get a new access token using a refresh token.",
)
async def refresh_token(
    request: TokenRefreshRequest,
    db: DBSession,
) -> TokenResponse:
    """
    Refresh access token.

    - **refresh_token**: Valid refresh token
    """
    auth_service = AuthService(db)

    access_token, new_refresh_token, expires_in = await auth_service.refresh_access_token(
        refresh_token=request.refresh_token,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout",
    description="Logout and invalidate the refresh token.",
)
async def logout(
    request: TokenRefreshRequest,
    db: DBSession,
) -> None:
    """
    Logout and invalidate refresh token.

    - **refresh_token**: Refresh token to invalidate
    """
    auth_service = AuthService(db)
    await auth_service.logout(refresh_token=request.refresh_token)


@router.post(
    "/api-keys",
    response_model=APIKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create API key",
    description="Create a new API key for the authenticated user.",
)
async def create_api_key(
    request: APIKeyCreate,
    current_user: JWTUser,
    db: DBSession,
) -> APIKeyCreateResponse:
    """
    Create a new API key.

    **Requires JWT authentication.**

    - **name**: Name for the API key
    - **scopes**: Permission scopes (renders:read, renders:write, webhooks:manage)
    - **expires_at**: Optional expiration timestamp

    Returns the access_key and secret_key (secret only shown once!).
    """
    auth_service = AuthService(db)

    access_key, secret_key, api_key = await auth_service.create_api_key(
        user_id=current_user.user_id,
        name=request.name,
        scopes=request.scopes,
        expires_at=request.expires_at,
        enforce_signing=request.enforce_signing,
    )

    return APIKeyCreateResponse(
        access_key=access_key,
        secret_key=secret_key,
        enforce_signing=api_key.enforce_signing,
        key_id=api_key.id,
        name=api_key.name,
        scopes=api_key.scopes or [],
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        is_active=api_key.is_active,
    )


@router.get(
    "/api-keys",
    response_model=list[APIKeyResponse],
    summary="List API keys",
    description="List all API keys for the authenticated user.",
)
async def list_api_keys(
    current_user: JWTUser,
    db: DBSession,
) -> list[APIKeyResponse]:
    """
    List all API keys.

    **Requires JWT authentication.**

    Returns a list of API keys (without the full key, only prefix).
    """
    auth_service = AuthService(db)
    api_keys = await auth_service.list_api_keys(user_id=current_user.user_id)

    return [
        APIKeyResponse(
            key_id=key.id,
            name=key.name,
            access_key=key.access_key,
            key_prefix=key.key_prefix,
            enforce_signing=key.enforce_signing,
            scopes=key.scopes or [],
            last_used_at=key.last_used_at,
            created_at=key.created_at,
            expires_at=key.expires_at,
            is_active=key.is_active,
        )
        for key in api_keys
    ]


@router.delete(
    "/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete API key",
    description="Delete an API key.",
)
async def delete_api_key(
    key_id: UUID,
    current_user: JWTUser,
    db: DBSession,
) -> None:
    """
    Delete an API key.

    **Requires JWT authentication.**

    - **key_id**: UUID of the API key to delete
    """
    auth_service = AuthService(db)
    await auth_service.delete_api_key(
        user_id=current_user.user_id,
        key_id=key_id,
    )


@router.patch(
    "/api-keys/{key_id}/enforce-signing",
    response_model=APIKeyResponse,
    summary="Toggle enforce signing",
    description="Enable or disable signature enforcement for an API key.",
)
async def toggle_enforce_signing(
    key_id: UUID,
    enforce: bool,
    current_user: JWTUser,
    db: DBSession,
) -> APIKeyResponse:
    """
    Toggle signature enforcement for an API key.

    **Requires JWT authentication.**

    - **key_id**: UUID of the API key
    - **enforce**: True to require signatures, False to make optional
    """
    from sqlalchemy import select
    from app.models import APIKey
    from app.utils.exceptions import NotFoundError
    
    # Find key owned by user
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.user_id == current_user.user_id,
        )
    )
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise NotFoundError(
            "API key not found",
            resource_type="api_key",
            resource_id=str(key_id),
        )
    
    api_key.enforce_signing = enforce
    await db.commit()
    await db.refresh(api_key)
    
    return APIKeyResponse(
        key_id=api_key.id,
        name=api_key.name,
        access_key=api_key.access_key,
        key_prefix=api_key.key_prefix,
        enforce_signing=api_key.enforce_signing,
        scopes=api_key.scopes or [],
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        is_active=api_key.is_active,
    )
