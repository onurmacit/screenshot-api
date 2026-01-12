"""
Unit tests for Dual-Key API Authentication System

Tests cover:
- Key pair generation (access_key, secret_key)
- Secret key encryption/decryption
- Signature generation and verification
- Access key lookup
- Enforce signing logic
"""

import pytest
import time
import os
from unittest.mock import patch, MagicMock


class TestKeyGeneration:
    """Test dual-key pair generation."""
    
    def test_generate_key_pair_format(self):
        """Test that generated keys have correct format."""
        from app.utils.crypto import generate_key_pair
        
        access_key, secret_key = generate_key_pair()
        
        # Access key should start with ak_
        assert access_key.startswith("ak_")
        # Secret key should start with sk_
        assert secret_key.startswith("sk_")
        # Keys should have reasonable length
        assert len(access_key) >= 20
        assert len(secret_key) >= 32
    
    def test_generate_key_pair_uniqueness(self):
        """Test that each call generates unique keys."""
        from app.utils.crypto import generate_key_pair
        
        pairs = [generate_key_pair() for _ in range(10)]
        access_keys = [p[0] for p in pairs]
        secret_keys = [p[1] for p in pairs]
        
        # All keys should be unique
        assert len(set(access_keys)) == 10
        assert len(set(secret_keys)) == 10


class TestSecretKeyEncryption:
    """Test secret key encryption/decryption."""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings with a test encryption key."""
        with patch("app.utils.crypto.settings") as mock:
            # Valid Fernet key (base64 encoded 32 bytes)
            mock.SECRET_KEY_ENCRYPTION_KEY = "qi-cAnWCnI6g34GAKNO041xPADKJwBZJQzK2HT2uIGc="
            yield mock
    
    def test_encrypt_decrypt_roundtrip(self, mock_settings):
        """Test that encryption and decryption work correctly."""
        from app.utils.crypto import encrypt_secret_key, decrypt_secret_key
        
        original_secret = "sk_test_secret_key_12345"
        
        encrypted = encrypt_secret_key(original_secret)
        decrypted = decrypt_secret_key(encrypted)
        
        assert decrypted == original_secret
        assert encrypted != original_secret  # Should be different
    
    def test_encrypted_value_is_different_each_time(self, mock_settings):
        """Test that encryption produces different ciphertexts (due to IV)."""
        from app.utils.crypto import encrypt_secret_key
        
        secret = "sk_test_secret"
        
        encrypted1 = encrypt_secret_key(secret)
        encrypted2 = encrypt_secret_key(secret)
        
        # Fernet uses random IV, so ciphertexts should differ
        assert encrypted1 != encrypted2
    
    def test_decrypt_with_wrong_key_fails(self, mock_settings):
        """Test that decryption fails with wrong key."""
        from app.utils.crypto import encrypt_secret_key, decrypt_secret_key, get_fernet
        from cryptography.fernet import InvalidToken
        
        # Encrypt with mock key
        encrypted = encrypt_secret_key("test_secret")
        
        # Try to decrypt with different key
        with patch("app.utils.crypto.settings") as wrong_mock:
            wrong_mock.SECRET_KEY_ENCRYPTION_KEY = "xyzABCDEFGHIJKLMNOPQRSTUVWXYZ123456789abc="
            
            # Clear cached fernet
            import app.utils.crypto as crypto_module
            crypto_module._fernet = None
            
            with pytest.raises(Exception):  # InvalidToken or similar
                decrypt_secret_key(encrypted)


class TestSignatureVerification:
    """Test HMAC-SHA256 signature verification."""
    
    def test_verify_valid_signature(self):
        """Test signature verification with valid signature."""
        from app.utils.signature import generate_signature, verify_signature
        
        access_key = "ak_test123"
        secret_key = "sk_secret456"
        params = {"url": "https://example.com", "width": 1920}
        
        # Generate signed params
        signed = generate_signature(access_key, params, secret_key, expires_in=3600)
        
        # Verify
        is_valid, error = verify_signature(
            params={**params, "expires": signed["expires"]},
            signature=signed["signature"],
            secret_key=secret_key,
        )
        
        assert is_valid is True
        assert error is None
    
    def test_verify_invalid_signature(self):
        """Test signature verification with invalid signature."""
        from app.utils.signature import verify_signature
        
        params = {"url": "https://example.com", "expires": int(time.time()) + 3600}
        
        is_valid, error = verify_signature(
            params=params,
            signature="invalid_signature_abc123",
            secret_key="sk_secret",
        )
        
        assert is_valid is False
        assert error is not None
    
    def test_verify_expired_signature(self):
        """Test signature verification with expired timestamp."""
        from app.utils.signature import generate_signature, verify_signature
        
        access_key = "ak_test"
        secret_key = "sk_secret"
        params = {"url": "https://example.com"}
        
        # Generate with already expired timestamp
        with patch("time.time", return_value=1000):
            signed = generate_signature(access_key, params, secret_key, expires_in=1)
        
        # Now verify (time has passed)
        is_valid, error = verify_signature(
            params={**params, "expires": signed["expires"]},
            signature=signed["signature"],
            secret_key=secret_key,
        )
        
        assert is_valid is False
        assert "expired" in error.lower()
    
    def test_signature_with_wrong_secret_fails(self):
        """Test that signature verification fails with wrong secret."""
        from app.utils.signature import generate_signature, verify_signature
        
        access_key = "ak_test"
        correct_secret = "sk_correct"
        wrong_secret = "sk_wrong"
        params = {"url": "https://example.com"}
        
        signed = generate_signature(access_key, params, correct_secret)
        
        is_valid, error = verify_signature(
            params={**params, "expires": signed["expires"]},
            signature=signed["signature"],
            secret_key=wrong_secret,
        )
        
        assert is_valid is False


class TestAPIKeyModel:
    """Test APIKey model with dual-key fields."""
    
    def test_model_has_dual_key_fields(self):
        """Test that APIKey model has required dual-key fields."""
        from app.models.api_key import APIKey
        
        # Check field existence via mapper
        columns = [c.name for c in APIKey.__table__.columns]
        
        assert "access_key" in columns
        assert "secret_key_encrypted" in columns
        assert "enforce_signing" in columns
        assert "is_legacy" in columns
    
    def test_model_defaults(self):
        """Test APIKey model default values."""
        from app.models.api_key import APIKey
        
        # Create instance without dual-key fields to check defaults
        key = APIKey(
            user_id=None,  # Will be set properly in real usage
            name="Test Key",
        )
        
        assert key.enforce_signing is False
        assert key.is_legacy is False


class TestEnforceSigningLogic:
    """Test enforce_signing behavior."""
    
    def test_enforce_signing_requires_signature(self):
        """When enforce_signing=True, requests without signature should fail."""
        # This is an integration test that would need actual endpoint testing
        # Here we just document the expected behavior
        pass
    
    def test_optional_signing_allows_unsigned(self):
        """When enforce_signing=False, unsigned requests should succeed."""
        pass


# Integration test placeholder
class TestDualKeyIntegration:
    """Integration tests for dual-key authentication flow."""
    
    @pytest.mark.asyncio
    async def test_create_api_key_returns_dual_keys(self):
        """Test that API key creation returns both access and secret keys."""
        # This would require database and full service setup
        pass
    
    @pytest.mark.asyncio
    async def test_access_key_lookup(self):
        """Test looking up API key by access_key."""
        pass
    
    @pytest.mark.asyncio
    async def test_signed_request_flow(self):
        """Test complete signed request authentication flow."""
        pass
