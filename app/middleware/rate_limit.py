"""
Rate limiting middleware

IP-based rate limiting with spoofing protection.
Only trusts X-Forwarded-For headers from configured trusted proxies.

Optimized with local LRU cache to reduce Redis commands.
"""

import ipaddress
import time
from collections import OrderedDict
from collections.abc import Callable
from threading import Lock

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.redis import redis_context
from app.utils.logger import logger


# =============================================================================
# Local LRU Cache for Rate Limiting
# Reduces Redis commands by caching recent rate limit checks
# =============================================================================
class RateLimitCache:
    """Thread-safe LRU cache for rate limit results."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: float = 1.0):
        self._cache: OrderedDict[str, tuple[int, int, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = Lock()
    
    def get(self, key: str) -> tuple[int, int] | None:
        """Get cached count and remaining for a key."""
        with self._lock:
            if key not in self._cache:
                return None
            
            count, remaining, expires = self._cache[key]
            if time.time() > expires:
                del self._cache[key]
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return count, remaining
    
    def set(self, key: str, count: int, remaining: int) -> None:
        """Cache rate limit result."""
        with self._lock:
            # Remove oldest if at capacity
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            
            self._cache[key] = (count, remaining, time.time() + self._ttl)


# Global rate limit cache
_rate_limit_cache = RateLimitCache(max_size=1000, ttl_seconds=5.0)


def is_ip_in_networks(ip: str, networks: list[str]) -> bool:
    """
    Check if an IP address is in any of the given networks.
    
    Args:
        ip: IP address to check
        networks: List of IP addresses or CIDR ranges
        
    Returns:
        True if IP is in any network
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
        for network in networks:
            try:
                if "/" in network:
                    # CIDR notation
                    if ip_obj in ipaddress.ip_network(network, strict=False):
                        return True
                else:
                    # Single IP
                    if ip_obj == ipaddress.ip_address(network):
                        return True
            except ValueError:
                continue
        return False
    except ValueError:
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    IP-based rate limiting middleware.

    This middleware applies basic IP-based rate limiting before authentication.
    User-based rate limiting is applied in the API dependencies after auth.
    
    Security: Only trusts X-Forwarded-For from configured TRUSTED_PROXIES.
    """

    def __init__(self, app):
        super().__init__(app)
        self.limit_per_minute = settings.IP_RATE_LIMIT_PER_MINUTE
        self.trusted_proxies = settings.TRUSTED_PROXIES

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

        # Get client IP (with spoofing protection)
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
        """
        Extract client IP from request with spoofing protection.
        
        Only trusts X-Forwarded-For headers if the direct connection
        is from a trusted proxy.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Client IP address string
        """
        # Get direct connection IP
        direct_ip: str | None = None
        if request.client:
            direct_ip = request.client.host

        # If no trusted proxies configured or direct IP is not trusted,
        # always use direct connection IP
        if not self.trusted_proxies or not direct_ip:
            return direct_ip or "unknown"

        # Check if direct connection is from a trusted proxy
        if not is_ip_in_networks(direct_ip, self.trusted_proxies):
            # Direct connection is NOT from a trusted proxy
            # Do not trust any forwarded headers - could be spoofed
            return direct_ip

        # Direct connection IS from a trusted proxy
        # Now we can trust X-Forwarded-For header
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # X-Forwarded-For format: client, proxy1, proxy2, ...
            # Parse from right to left, finding the first non-trusted IP
            ips = [ip.strip() for ip in forwarded.split(",")]

            # Iterate from right to left (most recent proxies first)
            for ip in reversed(ips):
                if not is_ip_in_networks(ip, self.trusted_proxies):
                    # This is the original client IP
                    return ip

            # All IPs are trusted proxies, use the leftmost (original client)
            return ips[0]

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip and not is_ip_in_networks(real_ip, self.trusted_proxies):
            return real_ip

        # Fall back to direct connection IP
        return direct_ip

    async def _check_rate_limit(
        self,
        client_ip: str,
    ) -> tuple[bool, int, int]:
        """
        Check if request is within rate limit using atomic Redis operation.
        
        **Optimized:** Uses local LRU cache to reduce Redis commands.
        Same IP within 1 second uses cached result (incremented locally).

        Args:
            client_ip: Client IP address

        Returns:
            Tuple of (is_allowed, remaining, reset_timestamp)
        """
        current_minute = int(time.time() // 60)
        reset_at = (current_minute + 1) * 60
        key = f"rl:ip:{client_ip}:min:{current_minute}"

        # Check local cache first - saves Redis roundtrip
        cached = _rate_limit_cache.get(key)
        if cached is not None:
            count, remaining = cached
            # Increment locally
            new_count = count + 1
            new_remaining = max(0, remaining - 1)
            is_allowed = new_count <= self.limit_per_minute
            
            # Update cache
            _rate_limit_cache.set(key, new_count, new_remaining)
            
            return is_allowed, new_remaining, reset_at

        # Cache miss - hit Redis
        # Lua script for atomic check-and-increment
        lua_script = """
        local key = KEYS[1]
        local limit = tonumber(ARGV[1])
        
        -- Increment counter
        local current = redis.call('INCR', key)
        
        -- Set expiry on first increment
        if current == 1 then
            redis.call('EXPIRE', key, 60)
        end
        
        -- Check limit
        if current <= limit then
            return {1, limit - current, current}  -- allowed, remaining, count
        else
            return {0, 0, current}  -- not allowed, remaining, count
        end
        """

        async with redis_context("rate_limit") as redis:
            result = await redis.eval(
                lua_script,
                1,  # number of keys
                key,
                self.limit_per_minute,
            )

            is_allowed = result[0] == 1
            remaining = result[1]
            count = result[2] if len(result) > 2 else 1

        # Cache the result
        _rate_limit_cache.set(key, count, remaining)

        return is_allowed, remaining, reset_at
