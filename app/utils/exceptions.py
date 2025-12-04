"""
Custom exceptions for the application
"""

from typing import Any


class APIError(Exception):
    """Base exception for API errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or "INTERNAL_ERROR"
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API response."""
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details,
            }
        }


class ValidationError(APIError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str = "Validation failed",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            status_code=400,
            error_code="VALIDATION_ERROR",
            details=details,
        )


class AuthenticationError(APIError):
    """Raised when authentication fails."""

    def __init__(
        self,
        message: str = "Authentication failed",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTHENTICATION_ERROR",
            details=details,
        )


class AuthorizationError(APIError):
    """Raised when user lacks required permissions."""

    def __init__(
        self,
        message: str = "Access denied",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            status_code=403,
            error_code="AUTHORIZATION_ERROR",
            details=details,
        )


class NotFoundError(APIError):
    """Raised when resource is not found."""

    def __init__(
        self,
        message: str = "Resource not found",
        resource_type: str | None = None,
        resource_id: str | None = None,
    ):
        details = {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id

        super().__init__(
            message=message,
            status_code=404,
            error_code="NOT_FOUND",
            details=details,
        )


class RateLimitError(APIError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
        limit: int | None = None,
        remaining: int = 0,
    ):
        details: dict[str, Any] = {"remaining": remaining}
        if retry_after:
            details["retry_after"] = retry_after
        if limit:
            details["limit"] = limit

        super().__init__(
            message=message,
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            details=details,
        )


class ConflictError(APIError):
    """Raised when there's a conflict (e.g., duplicate resource)."""

    def __init__(
        self,
        message: str = "Resource already exists",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            status_code=409,
            error_code="CONFLICT",
            details=details,
        )


class PaymentError(APIError):
    """Raised when payment processing fails."""

    def __init__(
        self,
        message: str = "Payment processing failed",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            status_code=402,
            error_code="PAYMENT_ERROR",
            details=details,
        )


class QuotaExceededError(APIError):
    """Raised when user exceeds their plan quota."""

    def __init__(
        self,
        message: str = "Usage quota exceeded",
        current_usage: int | None = None,
        limit: int | None = None,
    ):
        details: dict[str, Any] = {}
        if current_usage is not None:
            details["current_usage"] = current_usage
        if limit is not None:
            details["limit"] = limit

        super().__init__(
            message=message,
            status_code=403,
            error_code="QUOTA_EXCEEDED",
            details=details,
        )


class RenderError(APIError):
    """Raised when screenshot/PDF rendering fails."""

    def __init__(
        self,
        message: str = "Rendering failed",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            status_code=500,
            error_code="RENDER_ERROR",
            details=details,
        )


class ExternalServiceError(APIError):
    """Raised when external service call fails."""

    def __init__(
        self,
        message: str = "External service error",
        service: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        if details is None:
            details = {}
        if service:
            details["service"] = service

        super().__init__(
            message=message,
            status_code=502,
            error_code="EXTERNAL_SERVICE_ERROR",
            details=details,
        )


class ServiceUnavailableError(APIError):
    """Raised when service is temporarily unavailable."""

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        retry_after: int | None = None,
    ):
        details: dict[str, Any] = {}
        if retry_after:
            details["retry_after"] = retry_after

        super().__init__(
            message=message,
            status_code=503,
            error_code="SERVICE_UNAVAILABLE",
            details=details,
        )

