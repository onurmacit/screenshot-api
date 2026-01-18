package middleware

import (
	"fmt"
	"regexp"
	"strings"
	"time"

	"github.com/getsentry/sentry-go"
	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
)

// Sensitive data patterns to redact (Q016)
var sensitivePatterns = []*regexp.Regexp{
	regexp.MustCompile(`(?i)(password|passwd|pwd)["']?\s*[:=]\s*["']?[^"'\s]+`),
	regexp.MustCompile(`(?i)(sk_live_|sk_test_|pk_live_|pk_test_)[a-zA-Z0-9]+`),
	regexp.MustCompile(`(?i)(api[_-]?key|apikey)["']?\s*[:=]\s*["']?[^"'\s]+`),
	regexp.MustCompile(`(?i)(secret[_-]?key|secretkey)["']?\s*[:=]\s*["']?[^"'\s]+`),
	regexp.MustCompile(`(?i)(bearer\s+)[a-zA-Z0-9._-]+`),
	regexp.MustCompile(`(?i)(authorization)["']?\s*[:=]\s*["']?[^"'\s]+`),
}

// sanitizeForLog redacts sensitive data from log output
func sanitizeForLog(input string) string {
	result := input
	for _, pattern := range sensitivePatterns {
		result = pattern.ReplaceAllStringFunc(result, func(match string) string {
			// Keep prefix, redact the value
			parts := strings.SplitN(match, ":", 2)
			if len(parts) == 2 {
				return parts[0] + ": [REDACTED]"
			}
			parts = strings.SplitN(match, "=", 2)
			if len(parts) == 2 {
				return parts[0] + "=[REDACTED]"
			}
			// For API keys, show only last 4 chars
			if len(match) > 8 {
				return match[:4] + "..." + match[len(match)-4:]
			}
			return "[REDACTED]"
		})
	}
	return result
}

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

		// Add error if present (sanitized for security - Q016)
		if err != nil {
			logLine += fmt.Sprintf(" | %s", sanitizeForLog(err.Error()))
		} else if status >= 400 {
			// Log response body for errors (sanitized)
			body := string(c.Response().Body())
			if len(body) > 100 {
				body = body[:100] + "..."
			}
			logLine += fmt.Sprintf(" | %s", sanitizeForLog(body))
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

				// Log panic (sanitized - Q016)
				panicMsg := fmt.Sprintf("%v", r)
				fmt.Printf("PANIC | %s | %s | %s | %s\n",
					c.IP(),
					c.Method(),
					c.Path(),
					sanitizeForLog(panicMsg),
				)

				// Return error response with 'detail' key for consistency
				c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
					"detail": "Internal server error",
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
