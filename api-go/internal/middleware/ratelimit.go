package middleware

import (
	"fmt"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/models"
	rpkg "github.com/onurmacit/screenshot-api/api-go/pkg/redis"
)

// IPRateLimit provides global IP-based rate limiting (Phase 2.1)
func IPRateLimit(cfg *config.Config) fiber.Handler {
	return func(c *fiber.Ctx) error {
		if !cfg.RateLimitEnabled {
			return c.Next()
		}

		limit := int64(120) // 120 requests per minute per IP globally
		key := fmt.Sprintf("ratelimit:ip:%s", c.IP())

		client := rpkg.Get()
		if client == nil {
			return c.Next()
		}

		ctx := c.Context()
		window := time.Now().Format("2006-01-02-15:04")
		finalKey := fmt.Sprintf("%s:%s", key, window)

		pipe := client.Pipeline()
		incr := pipe.Incr(ctx, finalKey)
		pipe.Expire(ctx, finalKey, 1*time.Minute)
		_, err := pipe.Exec(ctx)

		if err != nil {
			return c.Next()
		}

		if incr.Val() > limit {
			return c.Status(fiber.StatusTooManyRequests).JSON(fiber.Map{
				"detail": "Too many requests from this IP. Please try again later.",
			})
		}

		return c.Next()
	}
}

// UserRateLimit provides per-user quota and concurrency limiting
func UserRateLimit(cfg *config.Config) fiber.Handler {
	return func(c *fiber.Ctx) error {
		if !cfg.RateLimitEnabled {
			return c.Next()
		}

		user, ok := c.Locals("user").(*models.User)
		if !ok || user == nil {
			// If no user (e.g. public route that reached here), skip or fallback to IP
			// But IPRateLimit should have caught pure IP spikes already.
			return c.Next()
		}

		key := fmt.Sprintf("ratelimit:user:%s", user.ID)
		limit := int64(60) // 60 requests per minute by default

		if user.Plan.MaxConcurrentRequests > 5 {
			limit = 300 // Pro users get more
		}

		client := rpkg.Get()
		if client == nil {
			return c.Next()
		}

		ctx := c.Context()
		window := time.Now().Format("2006-01-02-15:04")
		finalKey := fmt.Sprintf("%s:%s", key, window)

		pipe := client.Pipeline()
		incr := pipe.Incr(ctx, finalKey)
		pipe.Expire(ctx, finalKey, 1*time.Minute)
		_, err := pipe.Exec(ctx)

		if err != nil {
			return c.Next()
		}

		current := incr.Val()

		// Set headers
		c.Set("X-RateLimit-Limit", fmt.Sprintf("%d", limit))
		c.Set("X-RateLimit-Remaining", fmt.Sprintf("%d", limit-current))
		c.Set("X-RateLimit-Reset", fmt.Sprintf("%d", time.Now().Truncate(time.Minute).Add(time.Minute).Unix()))

		if current > limit {
			return c.Status(fiber.StatusTooManyRequests).JSON(fiber.Map{
				"detail": "Plan rate limit exceeded. Please upgrade for more throughput.",
			})
		}

		return c.Next()
	}
}
