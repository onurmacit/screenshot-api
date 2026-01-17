package middleware

import (
	"fmt"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/models"
	rpkg "github.com/onurmacit/screenshot-api/api-go/pkg/redis"
)

func RateLimit(cfg *config.Config) fiber.Handler {
	return func(c *fiber.Ctx) error {
		if !cfg.RateLimitEnabled {
			return c.Next()
		}

		user, ok := c.Locals("user").(*models.User)
		var key string
		var limit int64

		if ok && user != nil {
			// Authenticated user
			key = fmt.Sprintf("ratelimit:user:%s", user.ID)
			// Use plan limit or default?
			// Ideally we could add a RateLimit per minute to the Plan model
			// For now, let's assume a generous limit for authenticated users
			limit = 60 // 60 requests per minute by default

			// If plan has high concurrency, maybe allow more
			if user.Plan.MaxConcurrentRequests > 5 {
				limit = 300 // Pro users gets more
			}
		} else {
			// Anonymous - limit by IP
			key = fmt.Sprintf("ratelimit:ip:%s", c.IP())
			limit = 20 // 20 requests per minute for anonymous
		}

		client := rpkg.Get()
		if client == nil {
			// If redis is down, fail open
			return c.Next()
		}

		ctx := c.Context()

		// Simple fixed window counter
		// Key expires every minute
		window := time.Now().Format("2006-01-02-15:04")
		finalKey := fmt.Sprintf("%s:%s", key, window)

		pipe := client.Pipeline()
		incr := pipe.Incr(ctx, finalKey)
		pipe.Expire(ctx, finalKey, 1*time.Minute)
		_, err := pipe.Exec(ctx)

		if err != nil {
			// Redis error, fail open
			return c.Next()
		}

		current := incr.Val()

		// Set headers
		c.Set("X-RateLimit-Limit", fmt.Sprintf("%d", limit))
		c.Set("X-RateLimit-Remaining", fmt.Sprintf("%d", limit-current))
		c.Set("X-RateLimit-Reset", fmt.Sprintf("%d", time.Now().Truncate(time.Minute).Add(time.Minute).Unix()))

		if current > limit {
			return c.Status(fiber.StatusTooManyRequests).JSON(fiber.Map{
				"error":   true,
				"message": "Too many requests. Please try again later.",
			})
		}

		return c.Next()
	}
}
