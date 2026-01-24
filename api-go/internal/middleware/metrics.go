package middleware

import (
	"strconv"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	httpRequestsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total number of HTTP requests",
		},
		[]string{"method", "endpoint", "status"},
	)

	httpRequestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "HTTP request duration in seconds",
			Buckets: []float64{.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10},
		},
		[]string{"method", "endpoint"},
	)

	activeConnections = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "http_active_connections",
			Help: "Number of active HTTP connections",
		},
	)

	screenshotRequestsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "screenshot_requests_total",
			Help: "Total number of screenshot requests",
		},
		[]string{"status", "format"},
	)

	screenshotDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "screenshot_duration_seconds",
			Help:    "Screenshot capture duration in seconds",
			Buckets: []float64{0.5, 1, 2, 5, 10, 30, 60},
		},
		[]string{"format"},
	)
)

// PrometheusMiddleware tracks HTTP metrics
func PrometheusMiddleware() fiber.Handler {
	return func(c *fiber.Ctx) error {
		activeConnections.Inc()
		defer activeConnections.Dec()

		start := time.Now()

		err := c.Next()

		duration := time.Since(start).Seconds()
		status := strconv.Itoa(c.Response().StatusCode())
		method := c.Method()
		path := c.Route().Path // Use route path to avoid high cardinality

		httpRequestsTotal.WithLabelValues(method, path, status).Inc()
		httpRequestDuration.WithLabelValues(method, path).Observe(duration)

		return err
	}
}

// RecordScreenshotMetrics records screenshot-specific metrics
func RecordScreenshotMetrics(success bool, format string, duration time.Duration) {
	status := "success"
	if !success {
		status = "failure"
	}

	screenshotRequestsTotal.WithLabelValues(status, format).Inc()
	screenshotDuration.WithLabelValues(format).Observe(duration.Seconds())
}
