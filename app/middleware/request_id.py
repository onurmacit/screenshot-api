"""
Request ID middleware for correlating logs and tracing requests.
"""

import contextvars
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Context variable to store request ID across async calls
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def get_request_id() -> str:
    """Get the current request ID from context."""
    return request_id_var.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that assigns a unique request ID to each request.
    
    The request ID is:
    - Taken from X-Request-ID header if provided (from Nginx)
    - Generated as a UUID if not provided
    - Stored in contextvars for access in logging
    - Added to response headers for client reference
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request with unique ID."""
        # Get request ID from header (set by Nginx) or generate new one
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())[:8]  # Short UUID for readability
        
        # Store in context variable for logging
        token = request_id_var.set(request_id)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
        finally:
            # Reset context
            request_id_var.reset(token)
