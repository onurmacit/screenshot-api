"""
Core module - Configuration, security, and infrastructure components
"""

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis

__all__ = ["settings", "get_db", "get_redis"]

