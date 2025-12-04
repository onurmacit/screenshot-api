"""
Screenshot API - Test Configuration
====================================
Pytest fixtures and test configuration.
"""

import asyncio
import os
import uuid
from datetime import datetime, timedelta
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.redis import get_redis
from app.core.security import create_access_token, get_password_hash, hash_api_key
from app.main import app
from app.models.api_key import APIKey
from app.models.plan import Plan
from app.models.render_job import RenderJob, RenderStatus, RenderType
from app.models.user import User


# =============================================================================
# Test Settings
# =============================================================================

# Use SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Override settings for tests
os.environ["APP_ENV"] = "test"
os.environ["TESTING"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async database engine for testing."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for each test."""
    async_session_maker = sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database session override."""
    
    async def override_get_db():
        yield db_session
    
    async def override_get_redis():
        # Return mock Redis for testing
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True
        mock_redis.delete.return_value = 1
        mock_redis.pipeline.return_value = mock_redis
        mock_redis.execute.return_value = [1, True]
        mock_redis.__aenter__ = AsyncMock(return_value=mock_redis)
        mock_redis.__aexit__ = AsyncMock(return_value=None)
        yield mock_redis
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


# =============================================================================
# Model Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def test_plan(db_session: AsyncSession) -> Plan:
    """Create a test plan."""
    plan = Plan(
        id=uuid.uuid4(),
        name="free",
        display_name="Free",
        price_monthly=0,
        price_yearly=0,
        requests_per_month=100,
        requests_per_minute=10,
        max_resolution_width=1280,
        max_resolution_height=720,
        features=["screenshot", "basic_formats"],
        is_active=True,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


@pytest_asyncio.fixture
async def test_pro_plan(db_session: AsyncSession) -> Plan:
    """Create a test pro plan."""
    plan = Plan(
        id=uuid.uuid4(),
        name="pro",
        display_name="Pro",
        price_monthly=2900,
        price_yearly=29000,
        requests_per_month=10000,
        requests_per_minute=100,
        max_resolution_width=1920,
        max_resolution_height=1080,
        features=["screenshot", "pdf", "all_formats", "priority_queue", "webhook"],
        is_active=True,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_plan: Plan) -> User:
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash=get_password_hash("TestPassword123!"),
        plan_id=test_plan.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_pro_user(db_session: AsyncSession, test_pro_plan: Plan) -> User:
    """Create a test pro user."""
    user = User(
        id=uuid.uuid4(),
        email="pro@example.com",
        password_hash=get_password_hash("ProPassword123!"),
        plan_id=test_pro_plan.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_api_key(db_session: AsyncSession, test_user: User) -> tuple[APIKey, str]:
    """Create a test API key and return both the model and raw key."""
    raw_key = f"sk_test_{uuid.uuid4().hex}"
    key_hash = hash_api_key(raw_key)
    
    api_key = APIKey(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Test API Key",
        key_hash=key_hash,
        key_prefix=raw_key[:12],
        scopes=["render:read", "render:write"],
        is_active=True,
    )
    db_session.add(api_key)
    await db_session.commit()
    await db_session.refresh(api_key)
    return api_key, raw_key


@pytest_asyncio.fixture
async def test_render_job(db_session: AsyncSession, test_user: User) -> RenderJob:
    """Create a test render job."""
    job = RenderJob(
        id=uuid.uuid4(),
        user_id=test_user.id,
        type=RenderType.SCREENSHOT,
        status=RenderStatus.COMPLETED,
        url="https://example.com",
        options={
            "width": 1280,
            "height": 720,
            "format": "png",
            "full_page": False,
        },
        s3_key=f"renders/{test_user.id}/test-screenshot.png",
        file_size=12345,
        render_time_ms=1500,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


# =============================================================================
# Authentication Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict[str, str]:
    """Create authorization headers with JWT token."""
    token = create_access_token(
        data={"sub": str(test_user.id), "email": test_user.email}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def api_key_headers(test_api_key: tuple[APIKey, str]) -> dict[str, str]:
    """Create authorization headers with API key."""
    _, raw_key = test_api_key
    return {"X-API-Key": raw_key}


@pytest_asyncio.fixture
async def pro_auth_headers(test_pro_user: User) -> dict[str, str]:
    """Create authorization headers for pro user."""
    token = create_access_token(
        data={"sub": str(test_pro_user.id), "email": test_pro_user.email}
    )
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_s3_client():
    """Mock S3 client."""
    with patch("app.services.storage_service.StorageService") as mock:
        instance = mock.return_value
        instance.upload_file = AsyncMock(return_value="renders/test/file.png")
        instance.get_signed_url = AsyncMock(return_value="https://s3.example.com/signed-url")
        instance.delete_file = AsyncMock(return_value=True)
        instance.file_exists = AsyncMock(return_value=True)
        yield instance


@pytest.fixture
def mock_playwright():
    """Mock Playwright browser."""
    with patch("app.services.render_service.async_playwright") as mock:
        browser = AsyncMock()
        context = AsyncMock()
        page = AsyncMock()
        
        page.screenshot = AsyncMock(return_value=b"fake-image-data")
        page.pdf = AsyncMock(return_value=b"fake-pdf-data")
        page.goto = AsyncMock()
        page.wait_for_load_state = AsyncMock()
        page.set_viewport_size = AsyncMock()
        
        context.new_page = AsyncMock(return_value=page)
        context.close = AsyncMock()
        
        browser.new_context = AsyncMock(return_value=context)
        browser.close = AsyncMock()
        
        playwright_instance = AsyncMock()
        playwright_instance.chromium.launch = AsyncMock(return_value=browser)
        
        mock.return_value.__aenter__ = AsyncMock(return_value=playwright_instance)
        mock.return_value.__aexit__ = AsyncMock(return_value=None)
        
        yield {
            "playwright": mock,
            "browser": browser,
            "context": context,
            "page": page,
        }


@pytest.fixture
def mock_stripe():
    """Mock Stripe client."""
    with patch("stripe.Customer") as mock_customer, \
         patch("stripe.Subscription") as mock_subscription, \
         patch("stripe.Invoice") as mock_invoice:
        
        mock_customer.create.return_value = MagicMock(id="cus_test123")
        mock_customer.retrieve.return_value = MagicMock(
            id="cus_test123",
            email="test@example.com",
        )
        
        mock_subscription.create.return_value = MagicMock(
            id="sub_test123",
            status="active",
            current_period_end=int((datetime.utcnow() + timedelta(days=30)).timestamp()),
        )
        mock_subscription.retrieve.return_value = MagicMock(
            id="sub_test123",
            status="active",
        )
        mock_subscription.modify.return_value = MagicMock(
            id="sub_test123",
            status="active",
        )
        
        mock_invoice.list.return_value = MagicMock(
            data=[
                MagicMock(
                    id="inv_test123",
                    amount_paid=2900,
                    status="paid",
                    created=int(datetime.utcnow().timestamp()),
                ),
            ]
        )
        
        yield {
            "customer": mock_customer,
            "subscription": mock_subscription,
            "invoice": mock_invoice,
        }


@pytest.fixture
def mock_celery():
    """Mock Celery tasks."""
    with patch("app.workers.render_tasks.process_screenshot_task") as mock_screenshot, \
         patch("app.workers.render_tasks.process_pdf_task") as mock_pdf, \
         patch("app.workers.webhook_tasks.send_webhook_task") as mock_webhook:
        
        mock_screenshot.delay.return_value = MagicMock(id="task-123")
        mock_pdf.delay.return_value = MagicMock(id="task-456")
        mock_webhook.delay.return_value = MagicMock(id="task-789")
        
        yield {
            "screenshot": mock_screenshot,
            "pdf": mock_pdf,
            "webhook": mock_webhook,
        }


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def sample_screenshot_request() -> dict:
    """Sample screenshot request payload."""
    return {
        "url": "https://example.com",
        "options": {
            "width": 1280,
            "height": 720,
            "format": "png",
            "full_page": False,
            "delay": 0,
        },
    }


@pytest.fixture
def sample_pdf_request() -> dict:
    """Sample PDF request payload."""
    return {
        "url": "https://example.com",
        "options": {
            "format": "A4",
            "landscape": False,
            "print_background": True,
            "margin": {
                "top": "10mm",
                "right": "10mm",
                "bottom": "10mm",
                "left": "10mm",
            },
        },
    }


@pytest.fixture
def sample_webhook_payload() -> dict:
    """Sample webhook creation payload."""
    return {
        "url": "https://webhook.example.com/callback",
        "events": ["render.completed", "render.failed"],
        "is_active": True,
    }
