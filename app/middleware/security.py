"""
Security headers middleware for protecting against common web vulnerabilities.
"""

from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to all responses.
    
    Implements mitigations for:
    - Clickjacking (X-Frame-Options)
    - MIME Sniffing (X-Content-Type-Options)
    - XSS (X-XSS-Protection, Content-Security-Policy)
    - Protocol Downgrade (HSTS)
    - Information Leakage (Referrer-Policy)
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request and add security headers to response."""
        response = await call_next(request)

        # 1. Prevent Clickjacking
        # DENY: Site cannot be displayed in a frame
        response.headers["X-Frame-Options"] = "DENY"

        # 2. Prevent MIME Sniffing
        # nosniff: Browser must use the Content-Type header provided by the server
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 3. Content Security Policy (CSP)
        # Restrict where resources can be loaded from.
        # This is a strict policy that may need adjustment if external scripts are added.
        csp_parts = [
            "default-src 'self'",
            "img-src 'self' data: https:",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # unsafe-inline for Swagger/Redoc
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com",
            "connect-src 'self' https://api.screenshotbeam.com",
            "frame-ancestors 'none'",
            "object-src 'none'",
            "base-uri 'self'",
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_parts)

        # 4. Strict Transport Security (HSTS)
        # Force HTTPS for subsequent requests. Only in production.
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # 5. Referrer Policy
        # Control how much referrer information is sent with requests.
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 6. X-XSS-Protection
        # Although deprecated in modern browsers, it still offers protection for older ones.
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # 7. Permissions Policy
        # Disable unused powerful features
        permissions = [
            "geolocation=()",
            "microphone=()",
            "camera=()",
            "payment=()",
            "usb=()",
        ]
        response.headers["Permissions-Policy"] = ", ".join(permissions)

        return response
