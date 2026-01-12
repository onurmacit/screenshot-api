"""
API Key Service

Handles creation, validation, and management of dual-key API authentication.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import APIKey
from app.utils.crypto import (
    encrypt_secret_key,
    decrypt_secret_key,
    generate_key_pair,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def create_api_key(
    db: AsyncSession,
    user_id: UUID,
    name: str | None = None,
    scopes: list[str] | None = None,
) -> dict:
    """
    Create a new dual-key API key pair.
    
    Args:
        db: Database session
        user_id: Owner user ID
        name: Optional key name
        scopes: Optional permission scopes
        
    Returns:
        Dict with access_key, secret_key (show once!), and metadata
    """
    access_key, secret_key = generate_key_pair()
    
    api_key = APIKey(
        user_id=user_id,
        access_key=access_key,
        secret_key_encrypted=encrypt_secret_key(secret_key),
        name=name or "Default",
        scopes=scopes or [],
        enforce_signing=False,
        is_legacy=False,
        is_active=True,
    )
    
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    
    logger.info("Created new API key", user_id=str(user_id), key_id=str(api_key.id))
    
    return {
        "id": str(api_key.id),
        "access_key": access_key,
        "secret_key": secret_key,  # Show ONCE at creation!
        "name": api_key.name,
        "enforce_signing": api_key.enforce_signing,
        "created_at": api_key.created_at.isoformat() if api_key.created_at else None,
    }


async def get_api_key_by_access_key(
    db: AsyncSession,
    access_key: str,
) -> APIKey | None:
    """
    Look up an API key by its public access key.
    
    Args:
        db: Database session
        access_key: Public access key (e.g., ak_xxx)
        
    Returns:
        APIKey record or None
    """
    result = await db.scalar(
        select(APIKey).where(
            APIKey.access_key == access_key,
            APIKey.is_active == True,
        )
    )
    return result


async def get_secret_key(api_key_record: APIKey) -> str:
    """
    Decrypt and return the secret key for an API key record.
    
    Args:
        api_key_record: APIKey model instance
        
    Returns:
        Decrypted secret key
        
    Raises:
        ValueError: If decryption fails
    """
    if not api_key_record.secret_key_encrypted:
        raise ValueError("API key has no secret key (legacy key?)")
    return decrypt_secret_key(api_key_record.secret_key_encrypted)


async def toggle_enforce_signing(
    db: AsyncSession,
    api_key_id: UUID,
    enforce: bool,
) -> bool:
    """
    Toggle signature enforcement for an API key.
    
    Args:
        db: Database session
        api_key_id: API key UUID
        enforce: Whether to enforce signing
        
    Returns:
        True if updated successfully
    """
    api_key = await db.get(APIKey, api_key_id)
    if not api_key:
        return False
    
    api_key.enforce_signing = enforce
    await db.commit()
    
    logger.info(
        "Updated enforce_signing",
        key_id=str(api_key_id),
        enforce_signing=enforce,
    )
    return True


async def regenerate_secret_key(
    db: AsyncSession,
    api_key_id: UUID,
) -> str | None:
    """
    Generate a new secret key for an existing API key.
    Invalidates the old secret key immediately.
    
    Args:
        db: Database session
        api_key_id: API key UUID
        
    Returns:
        New secret key (show once!) or None if not found
    """
    api_key = await db.get(APIKey, api_key_id)
    if not api_key:
        return None
    
    _, new_secret = generate_key_pair()
    api_key.secret_key_encrypted = encrypt_secret_key(new_secret)
    await db.commit()
    
    logger.warning(
        "Regenerated secret key",
        key_id=str(api_key_id),
    )
    return new_secret


async def update_last_used(
    db: AsyncSession,
    api_key_record: APIKey,
) -> None:
    """
    Update the last_used_at timestamp for an API key.
    
    Args:
        db: Database session
        api_key_record: APIKey to update
    """
    api_key_record.last_used_at = datetime.utcnow()
    await db.commit()
