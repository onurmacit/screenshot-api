"""
Screenshot API - Test Factories
================================
Factory classes for generating test data.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from app.core.security import generate_api_key, get_password_hash, hash_api_key
from app.models.api_key import APIKey
from app.models.plan import Plan
from app.models.render_job import RenderJob, RenderStatus, RenderType
from app.models.usage_record import UsageRecord
from app.models.user import User
from app.models.webhook import Webhook


class PlanFactory:
    """Factory for creating Plan instances."""
    
    @staticmethod
    def create(
        name: str = "test_plan",
        display_name: str = "Test Plan",
        price_monthly: int = 0,
        price_yearly: int = 0,
        requests_per_month: int = 100,
        requests_per_minute: int = 10,
        max_resolution_width: int = 1280,
        max_resolution_height: int = 720,
        features: Optional[list[str]] = None,
        is_active: bool = True,
        **kwargs: Any,
    ) -> Plan:
        """Create a Plan instance."""
        return Plan(
            id=kwargs.get("id", uuid.uuid4()),
            name=name,
            display_name=display_name,
            price_monthly=price_monthly,
            price_yearly=price_yearly,
            requests_per_month=requests_per_month,
            requests_per_minute=requests_per_minute,
            max_resolution_width=max_resolution_width,
            max_resolution_height=max_resolution_height,
            features=features or ["screenshot"],
            is_active=is_active,
            **kwargs,
        )
    
    @classmethod
    def free(cls, **kwargs: Any) -> Plan:
        """Create a free tier plan."""
        return cls.create(
            name="free",
            display_name="Free",
            price_monthly=0,
            price_yearly=0,
            requests_per_month=100,
            features=["screenshot", "basic_formats"],
            **kwargs,
        )
    
    @classmethod
    def pro(cls, **kwargs: Any) -> Plan:
        """Create a pro tier plan."""
        return cls.create(
            name="pro",
            display_name="Pro",
            price_monthly=2900,
            price_yearly=29000,
            requests_per_month=10000,
            requests_per_minute=100,
            max_resolution_width=1920,
            max_resolution_height=1080,
            features=["screenshot", "pdf", "all_formats", "priority_queue", "webhook"],
            **kwargs,
        )
    
    @classmethod
    def business(cls, **kwargs: Any) -> Plan:
        """Create a business tier plan."""
        return cls.create(
            name="business",
            display_name="Business",
            price_monthly=9900,
            price_yearly=99000,
            requests_per_month=100000,
            requests_per_minute=500,
            max_resolution_width=3840,
            max_resolution_height=2160,
            features=[
                "screenshot", "pdf", "all_formats",
                "priority_queue", "webhook", "dedicated_support",
            ],
            **kwargs,
        )


class UserFactory:
    """Factory for creating User instances."""
    
    _counter = 0
    
    @classmethod
    def create(
        cls,
        email: Optional[str] = None,
        password: str = "TestPassword123!",
        plan_id: Optional[uuid.UUID] = None,
        is_active: bool = True,
        is_verified: bool = True,
        **kwargs: Any,
    ) -> User:
        """Create a User instance."""
        cls._counter += 1
        return User(
            id=kwargs.get("id", uuid.uuid4()),
            email=email or f"user{cls._counter}@example.com",
            password_hash=get_password_hash(password),
            plan_id=plan_id,
            is_active=is_active,
            is_verified=is_verified,
            **kwargs,
        )


class APIKeyFactory:
    """Factory for creating APIKey instances."""
    
    @staticmethod
    def create(
        user_id: uuid.UUID,
        name: str = "Test API Key",
        scopes: Optional[list[str]] = None,
        is_active: bool = True,
        expires_at: Optional[datetime] = None,
        **kwargs: Any,
    ) -> tuple[APIKey, str]:
        """Create an APIKey instance and return both model and raw key."""
        raw_key = generate_api_key(prefix="sk_test_")
        key_hash = hash_api_key(raw_key)
        
        api_key = APIKey(
            id=kwargs.get("id", uuid.uuid4()),
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            key_prefix=raw_key[:12],
            scopes=scopes or ["render:read", "render:write"],
            is_active=is_active,
            expires_at=expires_at,
            **kwargs,
        )
        
        return api_key, raw_key


class RenderJobFactory:
    """Factory for creating RenderJob instances."""
    
    @staticmethod
    def create(
        user_id: uuid.UUID,
        url: str = "https://example.com",
        render_type: RenderType = RenderType.SCREENSHOT,
        status: RenderStatus = RenderStatus.COMPLETED,
        options: Optional[dict] = None,
        s3_key: Optional[str] = None,
        **kwargs: Any,
    ) -> RenderJob:
        """Create a RenderJob instance."""
        job_id = kwargs.get("id", uuid.uuid4())
        return RenderJob(
            id=job_id,
            user_id=user_id,
            type=render_type,
            status=status,
            url=url,
            options=options or {
                "width": 1280,
                "height": 720,
                "format": "png",
            },
            s3_key=s3_key or f"renders/{user_id}/{job_id}.png",
            file_size=kwargs.get("file_size", 12345),
            render_time_ms=kwargs.get("render_time_ms", 1500),
            **{k: v for k, v in kwargs.items() if k not in ["id", "file_size", "render_time_ms"]},
        )
    
    @classmethod
    def screenshot(cls, user_id: uuid.UUID, **kwargs: Any) -> RenderJob:
        """Create a screenshot render job."""
        return cls.create(
            user_id=user_id,
            render_type=RenderType.SCREENSHOT,
            **kwargs,
        )
    
    @classmethod
    def pdf(cls, user_id: uuid.UUID, **kwargs: Any) -> RenderJob:
        """Create a PDF render job."""
        return cls.create(
            user_id=user_id,
            render_type=RenderType.PDF,
            options={
                "format": "A4",
                "landscape": False,
                "print_background": True,
            },
            **kwargs,
        )
    
    @classmethod
    def pending(cls, user_id: uuid.UUID, **kwargs: Any) -> RenderJob:
        """Create a pending render job."""
        return cls.create(
            user_id=user_id,
            status=RenderStatus.PENDING,
            s3_key=None,
            **kwargs,
        )
    
    @classmethod
    def failed(cls, user_id: uuid.UUID, error: str = "Test error", **kwargs: Any) -> RenderJob:
        """Create a failed render job."""
        return cls.create(
            user_id=user_id,
            status=RenderStatus.FAILED,
            s3_key=None,
            error_message=error,
            **kwargs,
        )


class UsageRecordFactory:
    """Factory for creating UsageRecord instances."""
    
    @staticmethod
    def create(
        user_id: uuid.UUID,
        api_key_id: Optional[uuid.UUID] = None,
        render_job_id: Optional[uuid.UUID] = None,
        endpoint: str = "/api/v1/renders/screenshot",
        method: str = "POST",
        credits_used: int = 1,
        timestamp: Optional[datetime] = None,
        **kwargs: Any,
    ) -> UsageRecord:
        """Create a UsageRecord instance."""
        return UsageRecord(
            id=kwargs.get("id", uuid.uuid4()),
            user_id=user_id,
            api_key_id=api_key_id,
            render_job_id=render_job_id,
            endpoint=endpoint,
            method=method,
            credits_used=credits_used,
            timestamp=timestamp or datetime.utcnow(),
            **kwargs,
        )
    
    @classmethod
    def bulk(
        cls,
        user_id: uuid.UUID,
        count: int = 10,
        days_back: int = 7,
        **kwargs: Any,
    ) -> list[UsageRecord]:
        """Create multiple usage records spread over time."""
        records = []
        for i in range(count):
            timestamp = datetime.utcnow() - timedelta(
                days=i * days_back // count,
                hours=i % 24,
            )
            records.append(cls.create(
                user_id=user_id,
                timestamp=timestamp,
                **kwargs,
            ))
        return records


class WebhookFactory:
    """Factory for creating Webhook instances."""
    
    _counter = 0
    
    @classmethod
    def create(
        cls,
        user_id: uuid.UUID,
        url: Optional[str] = None,
        events: Optional[list[str]] = None,
        is_active: bool = True,
        **kwargs: Any,
    ) -> Webhook:
        """Create a Webhook instance."""
        cls._counter += 1
        return Webhook(
            id=kwargs.get("id", uuid.uuid4()),
            user_id=user_id,
            url=url or f"https://webhook{cls._counter}.example.com/callback",
            secret=kwargs.get("secret", f"whsec_test_{uuid.uuid4().hex[:16]}"),
            events=events or ["render.completed", "render.failed"],
            is_active=is_active,
            **kwargs,
        )

