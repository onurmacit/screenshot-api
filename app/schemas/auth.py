"""
Authentication Pydantic schemas
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="Password (min 8 chars)")
    full_name: str | None = Field(None, max_length=255, description="Full name")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class RegisterResponse(BaseModel):
    """User registration response."""

    user_id: UUID
    email: str
    access_token: str
    refresh_token: str

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class LoginResponse(BaseModel):
    """User login response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token expiration in seconds")

    model_config = {"from_attributes": True}


class SocialLoginRequest(BaseModel):
    """Social login request structure."""

    provider: str = Field(..., description="'google' or 'github'")
    token: str = Field(..., description="ID token for Google, access token for GitHub")
    full_name: str | None = Field(None, description="Optional full name from provider")


class TokenResponse(BaseModel):
    """Token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenRefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str = Field(..., description="Refresh token")


class APIKeyCreate(BaseModel):
    """API key creation request."""

    name: str = Field(..., max_length=100, description="Name for the API key")
    scopes: list[str] = Field(
        default=["renders:read", "renders:write"],
        description="Permission scopes",
    )
    expires_at: datetime | None = Field(
        None,
        description="Expiration timestamp (optional)",
    )
    enforce_signing: bool = Field(
        default=False,
        description="Require request signing with secret key",
    )

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: list[str]) -> list[str]:
        """Validate scopes."""
        allowed_scopes = {"renders:read", "renders:write", "webhooks:manage"}
        for scope in v:
            if scope not in allowed_scopes:
                raise ValueError(f"Invalid scope: {scope}")
        return v


class APIKeyResponse(BaseModel):
    """API key response."""

    key_id: UUID
    name: str | None
    # Dual-key system
    access_key: str | None = None
    key_prefix: str | None = None  # Legacy
    enforce_signing: bool = False
    # Other fields
    scopes: list[str]
    last_used_at: datetime | None
    created_at: datetime
    expires_at: datetime | None
    is_active: bool

    model_config = {"from_attributes": True}


class APIKeyCreateResponse(BaseModel):
    """API key creation response (includes full keys - shown once!)."""

    # Dual-key system
    access_key: str = Field(..., description="Public access key (safe to share)")
    secret_key: str = Field(..., description="Private secret key (ONLY shown once!)")
    enforce_signing: bool = False
    # Legacy compatibility
    api_key: str | None = Field(None, description="Legacy: Full API key")
    key_prefix: str | None = None
    # Other fields
    key_id: UUID
    name: str | None
    scopes: list[str]
    last_used_at: datetime | None
    created_at: datetime
    expires_at: datetime | None
    is_active: bool

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    """User response."""

    id: UUID
    email: str
    full_name: str | None
    plan_id: int | None
    is_active: bool
    email_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}

