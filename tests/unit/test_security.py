"""
Unit Tests - Security Module
=============================
Tests for JWT tokens, password hashing, and API key management.
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    get_password_hash,
    hash_api_key,
    verify_api_key,
    verify_password,
)


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "SecurePassword123!"
        hashed = get_password_hash(password)
        
        assert hashed is not None
        assert hashed != password
        assert len(hashed) > 0

    def test_verify_password_correct(self):
        """Test verifying correct password."""
        password = "SecurePassword123!"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test verifying incorrect password."""
        password = "SecurePassword123!"
        hashed = get_password_hash(password)
        
        assert verify_password("WrongPassword", hashed) is False

    def test_different_hashes_for_same_password(self):
        """Test that same password produces different hashes (salt)."""
        password = "SecurePassword123!"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        # Hashes should be different due to salt
        assert hash1 != hash2
        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestJWTTokens:
    """Tests for JWT token functions."""

    def test_create_access_token(self):
        """Test creating access token."""
        user_id = str(uuid.uuid4())
        email = "test@example.com"
        
        token = create_access_token(data={"sub": user_id, "email": email})
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_access_token(self):
        """Test decoding access token."""
        user_id = str(uuid.uuid4())
        email = "test@example.com"
        
        token = create_access_token(data={"sub": user_id, "email": email})
        payload = decode_token(token)
        
        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["email"] == email
        assert payload["type"] == "access"

    def test_create_refresh_token(self):
        """Test creating refresh token."""
        user_id = str(uuid.uuid4())
        
        token = create_refresh_token(data={"sub": user_id})
        
        assert token is not None
        assert isinstance(token, str)

    def test_decode_refresh_token(self):
        """Test decoding refresh token."""
        user_id = str(uuid.uuid4())
        
        token = create_refresh_token(data={"sub": user_id})
        payload = decode_token(token)
        
        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"

    def test_token_expiration(self):
        """Test token with custom expiration."""
        user_id = str(uuid.uuid4())
        
        # Create token that expires in 1 minute
        token = create_access_token(
            data={"sub": user_id},
            expires_delta=timedelta(minutes=1),
        )
        payload = decode_token(token)
        
        assert payload is not None
        # Check expiration is roughly 1 minute from now
        exp = datetime.utcfromtimestamp(payload["exp"])
        now = datetime.utcnow()
        diff = exp - now
        assert 50 <= diff.total_seconds() <= 70  # Allow some margin

    def test_decode_invalid_token(self):
        """Test decoding invalid token returns None."""
        payload = decode_token("invalid.token.here")
        assert payload is None

    def test_decode_expired_token(self):
        """Test decoding expired token returns None."""
        user_id = str(uuid.uuid4())
        
        # Create token that expired 1 hour ago
        token = create_access_token(
            data={"sub": user_id},
            expires_delta=timedelta(hours=-1),
        )
        payload = decode_token(token)
        
        assert payload is None


class TestAPIKey:
    """Tests for API key functions."""

    def test_generate_api_key(self):
        """Test generating API key."""
        api_key = generate_api_key()
        
        assert api_key is not None
        assert api_key.startswith("sk_live_") or api_key.startswith("sk_")
        assert len(api_key) > 20

    def test_generate_api_key_with_prefix(self):
        """Test generating API key with custom prefix."""
        api_key = generate_api_key(prefix="sk_test_")
        
        assert api_key.startswith("sk_test_")

    def test_hash_api_key(self):
        """Test hashing API key."""
        api_key = generate_api_key()
        hashed = hash_api_key(api_key)
        
        assert hashed is not None
        assert hashed != api_key
        assert len(hashed) == 64  # SHA-256 hex digest length

    def test_verify_api_key_correct(self):
        """Test verifying correct API key."""
        api_key = generate_api_key()
        hashed = hash_api_key(api_key)
        
        assert verify_api_key(api_key, hashed) is True

    def test_verify_api_key_incorrect(self):
        """Test verifying incorrect API key."""
        api_key = generate_api_key()
        hashed = hash_api_key(api_key)
        
        assert verify_api_key("wrong_key", hashed) is False

    def test_api_key_uniqueness(self):
        """Test that generated API keys are unique."""
        keys = [generate_api_key() for _ in range(100)]
        unique_keys = set(keys)
        
        assert len(keys) == len(unique_keys)

