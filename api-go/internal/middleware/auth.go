package middleware

import (
	"strings"

	"github.com/gofiber/fiber/v2"
	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/services"
	"github.com/onurmacit/screenshot-api/api-go/internal/utils"
)

func APIKeyAuth(authService *services.AuthService, cfg *config.Config) fiber.Handler {
	return func(c *fiber.Ctx) error {
		// 1. Check API Key (X-API-Key or Query)
		apiKey := c.Get("X-API-Key")
		if apiKey == "" {
			apiKey = c.Query("api_key")
		}

		// 2. Check Authorization Header (Bearer)
		token := ""
		auth := c.Get("Authorization")
		if strings.HasPrefix(auth, "Bearer ") {
			val := strings.TrimPrefix(auth, "Bearer ")
			if strings.HasPrefix(val, "sk_") {
				// Treat as API Key
				apiKey = val
			} else {
				// Treat as JWT
				token = val
			}
		}

		// Flow A: API Key Authentication
		if apiKey != "" {
			user, key, err := authService.ValidateAPIKey(c.Context(), apiKey)
			if err != nil {
				if appErr, ok := err.(*utils.AppError); ok {
					return c.Status(appErr.Code).JSON(fiber.Map{
						"error":   true,
						"message": appErr.Message,
					})
				}
				return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{
					"error":   true,
					"message": "Invalid API key",
				})
			}
			c.Locals("user", user)
			c.Locals("apiKey", key)
			return c.Next()
		}

		// Flow B: JWT Authentication
		if token != "" {
			claims, err := utils.ValidateToken(token, cfg.JWTSecretKey)
			if err != nil {
				return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{
					"error":   true,
					"message": "Invalid token",
				})
			}

			// Get User
			user, err := authService.GetUserByID(c.Context(), claims.UserID)
			if err != nil {
				return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{
					"error":   true,
					"message": "User not found",
				})
			}

			c.Locals("user", user)
			return c.Next()
		}

		// No credentials provided
		return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{
			"error":   true,
			"message": "Authentication required (API Key or Bearer Token)",
		})
	}
}
