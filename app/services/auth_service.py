"""
Authentication Service

Handles user registration, login, JWT tokens, and API key management.
"""

from datetime import datetime, timedelta
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
    verify_refresh_token,
)
from app.models import APIKey, Plan, RefreshToken, User
from app.utils.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.utils.helpers import hash_string, utc_now
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # User Registration & Login
    # =========================================================================

    async def register_user(
        self,
        email: str,
        password: str,
        full_name: str | None = None,
    ) -> tuple[User, str, str]:
        """
        Register a new user.

        Args:
            email: User email address
            password: Plain text password
            full_name: User's full name (optional)

        Returns:
            Tuple of (user, access_token, refresh_token)

        Raises:
            ConflictError: If email already exists
        """
        # Check if email exists
        existing = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        if existing.scalar_one_or_none():
            raise ConflictError("Email already registered")

        # Get free plan
        result = await self.db.execute(
            select(Plan).where(Plan.name == "free")
        )
        free_plan = result.scalar_one_or_none()

        # Create user
        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            full_name=full_name,
            plan_id=free_plan.id if free_plan else None,
            is_active=True,
            email_verified=False,
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info("User registered", user_id=str(user.id), email=email)

        # Generate tokens
        access_token = self._create_user_access_token(user)
        refresh_token = await self._create_refresh_token(user)

        return user, access_token, refresh_token

    async def login(
        self,
        email: str,
        password: str,
        ip_address: str | None = None,
        device_info: str | None = None,
    ) -> tuple[User, str, str, int]:
        """
        Authenticate user and return tokens.

        Args:
            email: User email
            password: Plain text password
            ip_address: Client IP address
            device_info: Client device information

        Returns:
            Tuple of (user, access_token, refresh_token, expires_in)

        Raises:
            AuthenticationError: If credentials are invalid
        """
        # Find user
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            logger.warning(
                "Failed login attempt", 
                email=email, 
                ip_address=ip_address,
                device_info=device_info
            )
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        logger.info("User logged in", user_id=str(user.id))

        # Generate tokens
        access_token = self._create_user_access_token(user)
        refresh_token = await self._create_refresh_token(
            user,
            ip_address=ip_address,
            device_info=device_info,
        )

        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        return user, access_token, refresh_token, expires_in

    async def social_login(
        self,
        provider: str,
        token: str,
        full_name: str | None = None,
        ip_address: str | None = None,
        device_info: str | None = None,
    ) -> tuple[User, str, str, int]:
        """
        Authenticate user via social provider and return tokens.
        """
        email = None
        
        # NOTE: This is where we would verify the token with the provider
        # For Google: verify ID token
        # For GitHub: call /user endpoint with access token
        
        if provider == "google":
            async with httpx.AsyncClient() as client:
                res = await client.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={token}")
                if res.status_code != 200:
                    logger.error("Invalid Google token", status_code=res.status_code, response=res.text)
                    raise AuthenticationError("Invalid Google token")
                data = res.json()
                email = data.get("email")
                full_name = data.get("name", full_name)
        elif provider == "github":
            async with httpx.AsyncClient() as client:
                # GitHub token verification
                res = await client.get("https://api.github.com/user", headers={"Authorization": f"token {token}"})
                if res.status_code != 200:
                    logger.error("Invalid GitHub token", status_code=res.status_code, response=res.text)
                    raise AuthenticationError("Invalid GitHub token")
                data = res.json()
                email = data.get("email")
                if not email:
                    # Fetch emails if not in public profile
                    res_emails = await client.get("https://api.github.com/user/emails", headers={"Authorization": f"token {token}"})
                    if res_emails.status_code == 200:
                        emails = res_emails.json()
                        primary_email = next((e["email"] for e in emails if e.get("primary")), None)
                        email = primary_email or (emails[0]["email"] if emails else None)
                full_name = data.get("name", full_name)
        else:
            raise ValidationError(f"Unsupported provider: {provider}")

        if not email:
            raise AuthenticationError("Could not retrieve email from provider")

        # Find or create user
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        user = result.scalar_one_or_none()

        if not user:
            # Get free plan
            plan_result = await self.db.execute(
                select(Plan).where(Plan.name == "free")
            )
            free_plan = plan_result.scalar_one_or_none()

            user = User(
                email=email.lower(),
                password_hash="social_auth_no_password", # Unique marker
                full_name=full_name,
                plan_id=free_plan.id if free_plan else None,
                is_active=True,
                email_verified=True, # Social emails are typically verified
            )
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            logger.info("New social user created", user_id=str(user.id), provider=provider)
        else:
            if not user.is_active:
                raise AuthenticationError("Account is deactivated")
            logger.info("Existing social user logged in", user_id=str(user.id), provider=provider)

        # Generate tokens
        access_token = self._create_user_access_token(user)
        refresh_token = await self._create_refresh_token(
            user,
            ip_address=ip_address,
            device_info=device_info,
        )

        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        return user, access_token, refresh_token, expires_in

    async def refresh_access_token(
        self,
        refresh_token: str,
    ) -> tuple[str, str, int]:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: The refresh token

        Returns:
            Tuple of (new_access_token, new_refresh_token, expires_in)

        Raises:
            AuthenticationError: If refresh token is invalid
        """
        # Verify token
        payload = verify_refresh_token(refresh_token)
        if not payload:
            raise AuthenticationError("Invalid refresh token")

        user_id = payload.get("sub")
        token_hash = hash_string(refresh_token)

        # Find token in database
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.user_id == UUID(user_id),
                RefreshToken.is_revoked == False,
            )
        )
        db_token = result.scalar_one_or_none()

        if not db_token or db_token.is_expired:
            raise AuthenticationError("Invalid or expired refresh token")

        # Get user
        result = await self.db.execute(
            select(User).where(User.id == UUID(user_id))
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        # Revoke old token (token rotation)
        db_token.is_revoked = True

        # Generate new tokens
        new_access_token = self._create_user_access_token(user)
        new_refresh_token = await self._create_refresh_token(user)

        await self.db.commit()

        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        return new_access_token, new_refresh_token, expires_in

    async def logout(self, refresh_token: str) -> bool:
        """
        Logout user by revoking refresh token.

        Args:
            refresh_token: The refresh token to revoke

        Returns:
            True if successfully logged out
        """
        token_hash = hash_string(refresh_token)

        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        db_token = result.scalar_one_or_none()

        if db_token:
            db_token.is_revoked = True
            await self.db.commit()

        return True

    # =========================================================================
    # API Key Management
    # =========================================================================

    async def create_api_key(
        self,
        user_id: UUID,
        name: str,
        scopes: list[str],
        expires_at: datetime | None = None,
    ) -> tuple[str, APIKey]:
        """
        Create a new API key for user.

        Args:
            user_id: User UUID
            name: Name for the API key
            scopes: Permission scopes
            expires_at: Expiration timestamp (optional)

        Returns:
            Tuple of (full_api_key, api_key_model)
            Note: full_api_key is only returned once!

        Raises:
            ValidationError: If user has too many API keys
        """
        # Check API key count
        result = await self.db.execute(
            select(APIKey).where(
                APIKey.user_id == user_id,
                APIKey.is_active == True,
            )
        )
        existing_keys = result.scalars().all()

        if len(existing_keys) >= 10:
            raise ValidationError(
                "Maximum API keys reached (10 per user)",
                details={"current_count": len(existing_keys), "max": 10},
            )

        # Generate API key
        full_key, key_prefix, key_hash = generate_api_key()

        # Create API key record
        api_key = APIKey(
            user_id=user_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=name,
            scopes=scopes,
            is_active=True,
            expires_at=expires_at,
        )

        self.db.add(api_key)
        await self.db.commit()
        await self.db.refresh(api_key)

        logger.info(
            "API key created",
            user_id=str(user_id),
            key_id=str(api_key.id),
            key_prefix=key_prefix,
        )

        return full_key, api_key

    async def validate_api_key(
        self,
        api_key: str,
    ) -> tuple[User, APIKey]:
        """
        Validate API key and return user and key.

        Args:
            api_key: The full API key

        Returns:
            Tuple of (user, api_key_model)

        Raises:
            AuthenticationError: If API key is invalid
        """
        key_hash = hash_api_key(api_key)

        # Find API key
        result = await self.db.execute(
            select(APIKey)
            .where(APIKey.key_hash == key_hash)
            .options()
        )
        db_key = result.scalar_one_or_none()

        if not db_key:
            raise AuthenticationError("Invalid API key")

        if not db_key.is_active:
            raise AuthenticationError("API key is deactivated")

        if db_key.is_expired:
            raise AuthenticationError("API key has expired")

        # Get user
        result = await self.db.execute(
            select(User).where(User.id == db_key.user_id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        # Update last used
        db_key.last_used_at = utc_now()
        await self.db.commit()

        return user, db_key

    async def list_api_keys(self, user_id: UUID) -> list[APIKey]:
        """
        List all API keys for a user.

        Args:
            user_id: User UUID

        Returns:
            List of API keys
        """
        result = await self.db.execute(
            select(APIKey)
            .where(APIKey.user_id == user_id)
            .order_by(APIKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_api_key(
        self,
        user_id: UUID,
        key_id: UUID,
    ) -> bool:
        """
        Delete an API key.

        Args:
            user_id: User UUID
            key_id: API key UUID

        Returns:
            True if deleted

        Raises:
            NotFoundError: If key not found
        """
        result = await self.db.execute(
            select(APIKey).where(
                APIKey.id == key_id,
                APIKey.user_id == user_id,
            )
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            raise NotFoundError(
                "API key not found",
                resource_type="api_key",
                resource_id=str(key_id),
            )

        await self.db.delete(api_key)
        await self.db.commit()

        logger.info(
            "API key deleted",
            user_id=str(user_id),
            key_id=str(key_id),
        )

        return True

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _create_user_access_token(self, user: User) -> str:
        """Create access token for user."""
        return create_access_token(
            subject=str(user.id),
            additional_claims={
                "email": user.email,
                "plan_id": user.plan_id,
            },
        )

    async def _create_refresh_token(
        self,
        user: User,
        ip_address: str | None = None,
        device_info: str | None = None,
    ) -> str:
        """Create and store refresh token."""
        token = create_refresh_token(subject=str(user.id))
        token_hash = hash_string(token)

        expires_at = utc_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            ip_address=ip_address,
            device_info=device_info,
            expires_at=expires_at,
            is_revoked=False,
        )

        self.db.add(refresh_token)
        await self.db.commit()

        return token

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

