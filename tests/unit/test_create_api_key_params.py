
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4
from app.services.auth_service import AuthService
from app.models.api_key import APIKey

@pytest.mark.asyncio
async def test_create_api_key_with_enforce_signing():
    """Test creating API key with enforce_signing=True."""
    # Mock DB session
    mock_db = AsyncMock()
    # Mock result for existing keys (empty list)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result
    
    service = AuthService(mock_db)
    
    # Mock crypto utils
    with patch("app.utils.crypto.generate_key_pair") as mock_gen, \
         patch("app.utils.crypto.encrypt_secret_key") as mock_encrypt:
        
        mock_gen.return_value = ("ak_test", "sk_test")
        mock_encrypt.return_value = "encrypted_sk"
        
        # Call create_api_key with enforce_signing=True
        await service.create_api_key(
            user_id=uuid4(),
            name="Test Key",
            scopes=["renders:read"],
            enforce_signing=True
        )
        
        # Verify APIKey was created with correct params
        assert mock_db.add.called
        created_key = mock_db.add.call_args[0][0]
        assert isinstance(created_key, APIKey)
        assert created_key.enforce_signing is True

@pytest.mark.asyncio
async def test_create_api_key_default_enforce_signing():
    """Test creating API key with default enforce_signing (False)."""
    # Mock DB session
    mock_db = AsyncMock()
    # Mock result for existing keys
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result
    
    service = AuthService(mock_db)
    
    # Mock crypto utils
    with patch("app.utils.crypto.generate_key_pair") as mock_gen, \
         patch("app.utils.crypto.encrypt_secret_key") as mock_encrypt:
        
        mock_gen.return_value = ("ak_test", "sk_test")
        mock_encrypt.return_value = "encrypted_sk"
        
        # Call create_api_key without enforce_signing (default)
        await service.create_api_key(
            user_id=uuid4(),
            name="Test Key",
            scopes=["renders:read"]
        )
        
        # Verify APIKey was created with enforce_signing=False
        assert mock_db.add.called
        created_key = mock_db.add.call_args[0][0]
        assert isinstance(created_key, APIKey)
        assert created_key.enforce_signing is False
