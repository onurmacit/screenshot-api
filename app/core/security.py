"""
Security utilities - JWT, password hashing, API key generation
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


# =============================================================================
# Password Hashing
# =============================================================================


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    # Encode password to bytes and hash
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        password_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


# =============================================================================
# JWT Token Management
# =============================================================================


def create_access_token(
    subject: str | Any,
    expires_delta: timedelta | None = None,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        subject: The subject of the token (usually user_id)
        expires_delta: Optional custom expiration time
        additional_claims: Additional claims to include in the token

    Returns:
        Encoded JWT token string
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }

    if additional_claims:
        to_encode.update(additional_claims)

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(
    subject: str | Any,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT refresh token.

    Args:
        subject: The subject of the token (usually user_id)
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT refresh token string
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
    }

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Args:
        token: The JWT token to decode

    Returns:
        Decoded token payload

    Raises:
        JWTError: If token is invalid or expired
    """
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


def verify_access_token(token: str) -> dict[str, Any] | None:
    """
    Verify an access token and return its payload.

    Args:
        token: The JWT token to verify

    Returns:
        Token payload if valid, None otherwise
    """
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def verify_refresh_token(token: str) -> dict[str, Any] | None:
    """
    Verify a refresh token and return its payload.

    Args:
        token: The JWT refresh token to verify

    Returns:
        Token payload if valid, None otherwise
    """
    try:
        payload = decode_token(token)
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None


# =============================================================================
# API Key Management
# =============================================================================


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new API key.

    Returns:
        Tuple of (full_key, key_prefix, key_hash)
        - full_key: The complete API key (sk_live_xxxx...) - only returned once
        - key_prefix: First 8 chars after prefix for identification
        - key_hash: SHA256 hash of the full key for storage
    """
    # Generate 32 random bytes and encode as hex
    random_part = secrets.token_hex(32)
    full_key = f"{settings.API_KEY_PREFIX}{random_part}"

    # Extract prefix for display (first 8 chars of random part)
    key_prefix = random_part[:8]

    # Hash the full key for secure storage
    key_hash = hash_api_key(full_key)

    return full_key, key_prefix, key_hash


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key using SHA256.

    Args:
        api_key: The full API key to hash

    Returns:
        SHA256 hash of the API key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key_format(api_key: str) -> bool:
    """
    Verify that an API key has the correct format.

    Args:
        api_key: The API key to verify

    Returns:
        True if format is valid, False otherwise
    """
    if not api_key:
        return False
    if not api_key.startswith(settings.API_KEY_PREFIX):
        return False
    # sk_live_ (8 chars) + 64 hex chars = 72 total
    expected_length = len(settings.API_KEY_PREFIX) + 64
    return len(api_key) == expected_length


# =============================================================================
# Webhook Signature
# =============================================================================


def generate_webhook_secret() -> str:
    """Generate a secret for webhook signature verification."""
    return secrets.token_hex(32)


def sign_webhook_payload(payload: str, secret: str) -> str:
    """
    Create HMAC-SHA256 signature for webhook payload.

    Args:
        payload: The webhook payload as string
        secret: The webhook secret

    Returns:
        HMAC-SHA256 signature as hex string
    """
    import hmac

    return hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_webhook_signature(payload: str, signature: str, secret: str) -> bool:
    """
    Verify webhook signature.

    Args:
        payload: The webhook payload
        signature: The provided signature
        secret: The webhook secret

    Returns:
        True if signature is valid, False otherwise
    """
    expected_signature = sign_webhook_payload(payload, secret)
    return secrets.compare_digest(signature, expected_signature)

