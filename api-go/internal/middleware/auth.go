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
		// 1. Check API Key (X-API-Key header or query param)
		// Priority: X-API-Key header > access_key query > api_key query (legacy)
		apiKey := c.Get("X-API-Key")
		if apiKey == "" {
			apiKey = c.Query("access_key") // ScreenshotOne style
		}
		if apiKey == "" {
			apiKey = c.Query("api_key") // Legacy support
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
						"detail": appErr.Message,
					})
				}
				return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{
					"detail": "Invalid API key",
				})
			}

			// Signature Verification Logic
			signature := c.Query("signature")
			if signature != "" {
				// 1. Check if we have the Secret Key (required for verification)
				if key.SecretKey == "" {
					// We can't verify. This could happen if decryption failed or key type doesn't support signing.
					// If signature is provided, we MUST verify it. So we fail.
					return c.Status(fiber.StatusForbidden).JSON(fiber.Map{
						"detail": "Signature provided but verification impossible (Internal configuration error)",
					})
				}

				// 2. Prepare params for verification (Exclude signature)
				params := c.Queries()
				delete(params, "signature")

				// 3. Verify
				if !utils.VerifySignature(params, key.SecretKey, signature) {
					return c.Status(fiber.StatusForbidden).JSON(fiber.Map{
						"detail": "Invalid signature",
					})
				}
			} else {
				// No signature provided. Check if Enforced.
				// Exception: Dashboard requests? We don't have dashboard exception logic here yet.
				// We assume key.EnforceSigning applies to ALL usages of this key.
				if key.EnforceSigning {
					return c.Status(fiber.StatusForbidden).JSON(fiber.Map{
						"detail": "Signed requests are required for this API Key",
					})
				}
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
					"detail": "Invalid token",
				})
			}

			// Get User
			user, err := authService.GetUserByID(c.Context(), claims.UserID)
			if err != nil {
				return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{
					"detail": "User not found",
				})
			}

			c.Locals("user", user)
			return c.Next()
		}

		// No credentials provided
		return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{
			"detail": "Authentication required (API Key or Bearer Token)",
		})
	}
}
