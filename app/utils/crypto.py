"""
Cryptographic utilities for API key encryption/decryption.

Uses Fernet (AES-128-CBC) for symmetric encryption of secret keys.
"""

import secrets
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_fernet() -> Fernet:
    """Get Fernet instance with configured encryption key."""
    key = settings.SECRET_KEY_ENCRYPTION_KEY
    if not key:
        raise ValueError("SECRET_KEY_ENCRYPTION_KEY not configured")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret_key(raw_secret: str) -> str:
    """
    Encrypt a secret key for database storage.
    
    Args:
        raw_secret: The plain text secret key
        
    Returns:
        Base64-encoded encrypted string
    """
    fernet = get_fernet()
    encrypted = fernet.encrypt(raw_secret.encode())
    return encrypted.decode()


def decrypt_secret_key(encrypted: str) -> str:
    """
    Decrypt a secret key from database storage.
    
    Args:
        encrypted: Base64-encoded encrypted string
        
    Returns:
        Plain text secret key
        
    Raises:
        ValueError: If decryption fails
    """
    try:
        fernet = get_fernet()
        decrypted = fernet.decrypt(encrypted.encode())
        return decrypted.decode()
    except InvalidToken as e:
        logger.error("Failed to decrypt secret key", error=str(e))
        raise ValueError("Invalid encrypted secret key") from e


def generate_access_key() -> str:
    """
    Generate a public access key.
    
    Format: 14 URL-safe characters (no prefix, ScreenshotOne style)
    Example: nW73cIaO8Y2cZA
    
    Security: 80 bits of entropy (2^80 brute-force attempts needed)
    """
    return secrets.token_urlsafe(10)  # 10 bytes = ~14 chars


def generate_secret_key() -> str:
    """
    Generate a private secret key.
    
    Format: 14 URL-safe characters (no prefix, ScreenshotOne style)
    Example: v2M_6coMczGUNw
    
    Security: 80 bits of entropy, stored encrypted at rest
    """
    return secrets.token_urlsafe(10)  # 10 bytes = ~14 chars


def generate_key_pair() -> tuple[str, str]:
    """
    Generate an Access Key + Secret Key pair.
    
    Returns:
        Tuple of (access_key, secret_key)
    """
    return generate_access_key(), generate_secret_key()


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.
    
    Use this to generate SECRET_KEY_ENCRYPTION_KEY for .env
    
    Returns:
        Base64-encoded 32-byte key
    """
    return Fernet.generate_key().decode()
