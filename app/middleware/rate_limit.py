"""
Rate limiting middleware
"""

import time
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.redis import redis_context
from app.utils.logger import logger


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    IP-based rate limiting middleware.

    This middleware applies basic IP-based rate limiting before authentication.
    User-based rate limiting is applied in the API dependencies after auth.
    """

    def __init__(self, app):
        super().__init__(app)
        self.limit_per_minute = settings.IP_RATE_LIMIT_PER_MINUTE

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request and apply rate limiting."""

        # Skip rate limiting for health checks
        if request.url.path.startswith("/api/v1/health"):
            return await call_next(request)

        # Skip if rate limiting is disabled
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Get client IP
        client_ip = self._get_client_ip(request)

        # Check rate limit
        try:
            is_allowed, remaining, reset_at = await self._check_rate_limit(client_ip)

            if not is_allowed:
                retry_after = max(1, reset_at - int(time.time()))
                logger.warning(
                    "IP rate limit exceeded",
                    client_ip=client_ip,
                    path=request.url.path,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests. Please slow down.",
                            "details": {
                                "retry_after": retry_after,
                                "limit": self.limit_per_minute,
                            },
                        }
                    },
                    headers={
                        "X-RateLimit-Limit": str(self.limit_per_minute),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(reset_at),
                        "Retry-After": str(retry_after),
                    },
                )

            # Process request
            response = await call_next(request)

            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = str(self.limit_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_at)

            return response

        except Exception as exc:
            # If rate limiting fails, allow the request through
            logger.error("Rate limit check failed", error=str(exc))
            return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Check for forwarded headers (behind proxy/load balancer)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Get the first IP in the chain (original client)
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct connection IP
        if request.client:
            return request.client.host

        return "unknown"

    async def _check_rate_limit(
        self,
        client_ip: str,
    ) -> tuple[bool, int, int]:
        """
        Check if request is within rate limit.

        Args:
            client_ip: Client IP address

        Returns:
            Tuple of (is_allowed, remaining, reset_timestamp)
        """
        current_minute = int(time.time() // 60)
        reset_at = (current_minute + 1) * 60
        key = f"rl:ip:{client_ip}:min:{current_minute}"

        async with redis_context("rate_limit") as redis:
            # Increment counter
            pipe = redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, 60)
            results = await pipe.execute()

            current_count = results[0]
            remaining = max(0, self.limit_per_minute - current_count)
            is_allowed = current_count <= self.limit_per_minute

        return is_allowed, remaining, reset_at

