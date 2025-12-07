"""
Unit Tests - Security Module
=============================
Tests for JWT tokens, password hashing, and API key management.
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from jose import jwt, JWTError

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    hash_password,
    hash_api_key,
    verify_api_key,
    verify_password,
    verify_access_token,
    verify_refresh_token,
    verify_api_key_format,
)


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "SecurePassword123!"
        hashed = hash_password(password)
        
        assert hashed is not None
        assert hashed != password
        assert len(hashed) > 0

    def test_verify_password_correct(self):
        """Test verifying correct password."""
        password = "SecurePassword123!"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test verifying incorrect password."""
        password = "SecurePassword123!"
        hashed = hash_password(password)
        
        assert verify_password("WrongPassword", hashed) is False

    def test_different_hashes_for_same_password(self):
        """Test that same password produces different hashes (salt)."""
        password = "SecurePassword123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        # Hashes should be different due to salt
        assert hash1 != hash2
        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestJWTTokens:
    """Tests for JWT token functions."""

    def test_create_access_token_with_subject(self):
        """Test creating access token with subject."""
        user_id = str(uuid.uuid4())
        
        token = create_access_token(subject=user_id)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_with_data(self):
        """Test creating access token with data dict."""
        user_id = str(uuid.uuid4())
        email = "test@example.com"
        
        token = create_access_token(subject=user_id, data={"sub": user_id, "email": email})
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_access_token(self):
        """Test decoding access token."""
        user_id = str(uuid.uuid4())
        email = "test@example.com"
        
        token = create_access_token(subject=user_id, data={"sub": user_id, "email": email})
        payload = decode_token(token)
        
        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["type"] == "access"

    def test_verify_access_token(self):
        """Test verifying access token."""
        user_id = str(uuid.uuid4())
        
        token = create_access_token(subject=user_id)
        payload = verify_access_token(token)
        
        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["type"] == "access"

    def test_create_refresh_token(self):
        """Test creating refresh token."""
        user_id = str(uuid.uuid4())
        
        token = create_refresh_token(subject=user_id)
        
        assert token is not None
        assert isinstance(token, str)

    def test_decode_refresh_token(self):
        """Test decoding refresh token."""
        user_id = str(uuid.uuid4())
        
        token = create_refresh_token(subject=user_id)
        payload = decode_token(token)
        
        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"

    def test_verify_refresh_token(self):
        """Test verifying refresh token."""
        user_id = str(uuid.uuid4())
        
        token = create_refresh_token(subject=user_id)
        payload = verify_refresh_token(token)
        
        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"

    def test_token_expiration(self):
        """Test token with custom expiration."""
        user_id = str(uuid.uuid4())
        
        # Create token that expires in 1 minute
        token = create_access_token(
            subject=user_id,
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
        """Test decoding invalid token raises JWTError."""
        with pytest.raises(JWTError):
            decode_token("invalid.token.here")

    def test_verify_access_token_invalid(self):
        """Test verify_access_token returns None for invalid token."""
        result = verify_access_token("invalid.token.here")
        assert result is None

    def test_verify_refresh_token_invalid(self):
        """Test verify_refresh_token returns None for invalid token."""
        result = verify_refresh_token("invalid.token.here")
        assert result is None

    def test_verify_access_token_with_refresh_token(self):
        """Test that access token verifier rejects refresh tokens."""
        user_id = str(uuid.uuid4())
        refresh_token = create_refresh_token(subject=user_id)
        
        # Should return None because token type is "refresh", not "access"
        result = verify_access_token(refresh_token)
        assert result is None

    def test_verify_refresh_token_with_access_token(self):
        """Test that refresh token verifier rejects access tokens."""
        user_id = str(uuid.uuid4())
        access_token = create_access_token(subject=user_id)
        
        # Should return None because token type is "access", not "refresh"
        result = verify_refresh_token(access_token)
        assert result is None


class TestAPIKey:
    """Tests for API key functions."""

    def test_generate_api_key(self):
        """Test generating API key returns tuple."""
        full_key, prefix, key_hash = generate_api_key()
        
        assert full_key is not None
        assert prefix is not None
        assert key_hash is not None
        assert full_key.startswith(settings.API_KEY_PREFIX)
        assert len(prefix) == 8

    def test_generate_api_key_hash(self):
        """Test generated API key hash is correct length."""
        full_key, prefix, key_hash = generate_api_key()
        
        # SHA-256 hex digest length is 64 characters
        assert len(key_hash) == 64

    def test_hash_api_key(self):
        """Test hashing API key."""
        full_key, _, _ = generate_api_key()
        hashed = hash_api_key(full_key)
        
        assert hashed is not None
        assert hashed != full_key
        assert len(hashed) == 64  # SHA-256 hex digest length

    def test_verify_api_key_correct(self):
        """Test verifying correct API key."""
        full_key, _, key_hash = generate_api_key()
        
        assert verify_api_key(full_key, key_hash) is True

    def test_verify_api_key_incorrect(self):
        """Test verifying incorrect API key."""
        _, _, key_hash = generate_api_key()
        
        assert verify_api_key("wrong_key", key_hash) is False

    def test_verify_api_key_format_valid(self):
        """Test verifying valid API key format."""
        full_key, _, _ = generate_api_key()
        
        assert verify_api_key_format(full_key) is True

    def test_verify_api_key_format_invalid(self):
        """Test verifying invalid API key format."""
        assert verify_api_key_format("invalid_key") is False
        assert verify_api_key_format("") is False
        assert verify_api_key_format("sk_live_tooshort") is False

    def test_api_key_uniqueness(self):
        """Test that generated API keys are unique."""
        keys = [generate_api_key()[0] for _ in range(100)]
        unique_keys = set(keys)
        
        assert len(keys) == len(unique_keys)

    def test_api_key_hash_consistency(self):
        """Test that hashing same key produces same hash."""
        full_key, _, _ = generate_api_key()
        
        hash1 = hash_api_key(full_key)
        hash2 = hash_api_key(full_key)
        
        assert hash1 == hash2
