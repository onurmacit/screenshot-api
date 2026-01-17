package utils

import "github.com/gofiber/fiber/v2"

// AppError represents a standard application error
type AppError struct {
	Code    int
	Message string
}

func (e *AppError) Error() string {
	return e.Message
}

// Common errors
var (
	ErrUnauthorized    = &AppError{Code: fiber.StatusUnauthorized, Message: "Unauthorized access"}
	ErrForbidden       = &AppError{Code: fiber.StatusForbidden, Message: "Access denied"}
	ErrNotFound        = &AppError{Code: fiber.StatusNotFound, Message: "Resource not found"}
	ErrBadRequest      = &AppError{Code: fiber.StatusBadRequest, Message: "Invalid request"}
	ErrInternal        = &AppError{Code: fiber.StatusInternalServerError, Message: "Internal server error"}
	ErrInvalidAPIKey   = &AppError{Code: fiber.StatusUnauthorized, Message: "Invalid API key"}
	ErrAPIKeyExpired   = &AppError{Code: fiber.StatusUnauthorized, Message: "API key expired"}
	ErrRateLimit       = &AppError{Code: fiber.StatusTooManyRequests, Message: "Rate limit exceeded"}
	ErrPaymentRequired = &AppError{Code: fiber.StatusPaymentRequired, Message: "Subscription required"}
)

func NewError(code int, message string) *AppError {
	return &AppError{
		Code:    code,
		Message: message,
	}
}
