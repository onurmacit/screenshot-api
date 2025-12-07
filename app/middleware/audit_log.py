"""
Audit logging middleware
"""

import time
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.logger import logger


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Audit logging middleware for tracking all API requests.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request and log audit information."""

        # Generate request ID
        request_id = str(uuid4())
        request.state.request_id = request_id

        # Start timer
        start_time = time.time()

        # Extract request info
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "")

        # Log request start
        logger.info(
            "Request started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log request completion
            logger.info(
                "Request completed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                client_ip=client_ip,
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as exc:
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log error
            logger.error(
                "Request failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error=str(exc),
                duration_ms=duration_ms,
                client_ip=client_ip,
            )

            raise

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        if request.client:
            return request.client.host

        return "unknown"


async def log_audit_event(
    user_id: str | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Log an audit event.

    This can be called from anywhere in the application to log
    specific audit events beyond just HTTP requests.

    Args:
        user_id: User ID (if authenticated)
        action: Action performed (e.g., "api_key.created")
        resource_type: Type of resource affected
        resource_id: ID of the affected resource
        ip_address: Client IP address
        user_agent: Client user agent
        metadata: Additional metadata
    """
    logger.info(
        "Audit event",
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata=metadata,
    )

