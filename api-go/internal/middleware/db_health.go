package middleware

import (
	"github.com/gofiber/fiber/v2"
	"gorm.io/gorm"
)

// DatabaseHealthCheck middleware checks if database is accessible
// If DB is down, returns 503 Service Unavailable (EDGE-005)
func DatabaseHealthCheck(db *gorm.DB) fiber.Handler {
	return func(c *fiber.Ctx) error {
		// Skip health check endpoints to avoid infinite loop
		path := c.Path()
		if path == "/health" || path == "/api/v1/health" {
			return c.Next()
		}

		// Quick connectivity check using raw SQL
		sqlDB, err := db.DB()
		if err != nil {
			return c.Status(fiber.StatusServiceUnavailable).JSON(fiber.Map{
				"detail": "Database connection unavailable",
				"code":   "DB_UNAVAILABLE",
			})
		}

		// Ping with short timeout
		if err := sqlDB.Ping(); err != nil {
			return c.Status(fiber.StatusServiceUnavailable).JSON(fiber.Map{
				"detail": "Database temporarily unavailable",
				"code":   "DB_UNAVAILABLE",
			})
		}

		return c.Next()
	}
}
