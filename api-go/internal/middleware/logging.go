package middleware

import (
	"fmt"
	"time"

	"github.com/getsentry/sentry-go"
	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
)

// RequestLogger provides structured logging for all API requests
func RequestLogger() fiber.Handler {
	return func(c *fiber.Ctx) error {
		start := time.Now()
		requestID := c.Get("X-Request-ID")
		if requestID == "" {
			requestID = uuid.New().String()[:8]
		}
		c.Set("X-Request-ID", requestID)

		// Process request
		err := c.Next()

		// Calculate latency
		latency := time.Since(start)

		// Get response status
		status := c.Response().StatusCode()

		// Log format: timestamp | status | latency | ip | method | path | request_id | error
		logLine := fmt.Sprintf("%s | %d | %12v | %s | %s | %s | %s",
			time.Now().Format("15:04:05"),
			status,
			latency,
			c.IP(),
			c.Method(),
			c.Path(),
			requestID,
		)

		// Add error if present
		if err != nil {
			logLine += fmt.Sprintf(" | %s", err.Error())
		} else if status >= 400 {
			// Log response body for errors
			body := string(c.Response().Body())
			if len(body) > 100 {
				body = body[:100] + "..."
			}
			logLine += fmt.Sprintf(" | %s", body)
		} else {
			logLine += " | -"
		}

		fmt.Println(logLine)

		return err
	}
}

// RecoverWithLog provides panic recovery with logging
func RecoverWithLog() fiber.Handler {
	return func(c *fiber.Ctx) error {
		defer func() {
			if r := recover(); r != nil {
				// Capture Sentry
				if hub := sentry.CurrentHub(); hub != nil {
					hub.Recover(r)
				}

				fmt.Printf("PANIC | %s | %s | %s | %v\n",
					c.IP(),
					c.Method(),
					c.Path(),
					r,
				)
				c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
					"error":   true,
					"message": "Internal server error",
				})
			}
		}()
		return c.Next()
	}
}

// Metrics tracks basic API metrics (can be extended for Prometheus)
type Metrics struct {
	TotalRequests  int64
	TotalErrors    int64
	AverageLatency float64
	RequestsByPath map[string]int64
	RequestsByCode map[int]int64
}

var metrics = &Metrics{
	RequestsByPath: make(map[string]int64),
	RequestsByCode: make(map[int]int64),
}

// MetricsCollector collects basic metrics
func MetricsCollector() fiber.Handler {
	return func(c *fiber.Ctx) error {
		err := c.Next()

		metrics.TotalRequests++
		path := c.Path()
		status := c.Response().StatusCode()

		metrics.RequestsByPath[path]++
		metrics.RequestsByCode[status]++

		if status >= 400 {
			metrics.TotalErrors++
		}

		return err
	}
}

// GetMetrics returns current metrics
func GetMetrics() *Metrics {
	return metrics
}
