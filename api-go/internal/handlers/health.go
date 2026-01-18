package handlers

import (
	"context"
	"net/http"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	rpkg "github.com/onurmacit/screenshot-api/api-go/pkg/redis"
	"gorm.io/gorm"
)

type HealthHandler struct {
	db  *gorm.DB
	cfg *config.Config
}

func NewHealthHandler(db *gorm.DB, cfg *config.Config) *HealthHandler {
	return &HealthHandler{db: db, cfg: cfg}
}

// Health returns basic API health status
func (h *HealthHandler) Health(c *fiber.Ctx) error {
	return c.JSON(fiber.Map{
		"status":    "ok",
		"version":   "1.0.0",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}

// Ready is the Kubernetes readiness probe (Q018)
// Returns 200 if the service can accept traffic
func (h *HealthHandler) Ready(c *fiber.Ctx) error {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	checks := make(map[string]fiber.Map)
	allHealthy := true

	// 1. Database Check
	dbStatus, dbLatency := h.checkDatabase(ctx)
	checks["database"] = fiber.Map{
		"status":     dbStatus,
		"latency_ms": dbLatency,
	}
	if dbStatus != "healthy" {
		allHealthy = false
	}

	// 2. Redis Check
	redisStatus, redisLatency := h.checkRedis(ctx)
	checks["redis"] = fiber.Map{
		"status":     redisStatus,
		"latency_ms": redisLatency,
	}
	if redisStatus != "healthy" {
		allHealthy = false
	}

	// 3. Go Renderer Check (if configured)
	if h.cfg.GoRendererURL != "" {
		rendererStatus, rendererLatency := h.checkRenderer(ctx)
		checks["renderer"] = fiber.Map{
			"status":     rendererStatus,
			"latency_ms": rendererLatency,
		}
		// Renderer being down shouldn't block readiness (degraded mode)
	}

	status := fiber.StatusOK
	statusText := "ready"
	if !allHealthy {
		status = fiber.StatusServiceUnavailable
		statusText = "not_ready"
	}

	return c.Status(status).JSON(fiber.Map{
		"status":    statusText,
		"timestamp": time.Now().UTC().Format(time.RFC3339),
		"checks":    checks,
	})
}

// Live is the Kubernetes liveness probe (Q018)
// Returns 200 if the process is alive and should not be restarted
func (h *HealthHandler) Live(c *fiber.Ctx) error {
	// Liveness should be very simple - just verify the process is responding
	// Don't check dependencies here (that's what readiness is for)
	return c.JSON(fiber.Map{
		"status":    "alive",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}

// DetailedHealth returns comprehensive health information
func (h *HealthHandler) DetailedHealth(c *fiber.Ctx) error {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	checks := make(map[string]fiber.Map)

	// Database
	dbStatus, dbLatency := h.checkDatabase(ctx)
	checks["database"] = fiber.Map{
		"status":     dbStatus,
		"latency_ms": dbLatency,
	}

	// Redis
	redisStatus, redisLatency := h.checkRedis(ctx)
	checks["redis"] = fiber.Map{
		"status":     redisStatus,
		"latency_ms": redisLatency,
	}

	// Renderer
	rendererStatus, rendererLatency := h.checkRenderer(ctx)
	checks["renderer"] = fiber.Map{
		"status":     rendererStatus,
		"latency_ms": rendererLatency,
		"url":        h.cfg.GoRendererURL,
	}

	return c.JSON(fiber.Map{
		"status":    "ok",
		"version":   "1.0.0",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
		"services":  checks,
	})
}

// Helper: Check database connection
func (h *HealthHandler) checkDatabase(ctx context.Context) (string, int64) {
	sqlDB, err := h.db.DB()
	if err != nil {
		return "unhealthy", 0
	}

	start := time.Now()
	if err := sqlDB.PingContext(ctx); err != nil {
		return "unhealthy", time.Since(start).Milliseconds()
	}
	return "healthy", time.Since(start).Milliseconds()
}

// Helper: Check Redis connection
func (h *HealthHandler) checkRedis(ctx context.Context) (string, int64) {
	client := rpkg.Get()
	if client == nil {
		return "not_configured", 0
	}

	start := time.Now()
	if err := client.Ping(ctx).Err(); err != nil {
		return "unhealthy", time.Since(start).Milliseconds()
	}
	return "healthy", time.Since(start).Milliseconds()
}

// Helper: Check Go Renderer health
func (h *HealthHandler) checkRenderer(ctx context.Context) (string, int64) {
	if h.cfg.GoRendererURL == "" {
		return "not_configured", 0
	}

	healthURL := h.cfg.GoRendererURL + "/health"

	req, err := http.NewRequestWithContext(ctx, "GET", healthURL, nil)
	if err != nil {
		return "unhealthy", 0
	}

	client := &http.Client{Timeout: 3 * time.Second}
	start := time.Now()
	resp, err := client.Do(req)
	latency := time.Since(start).Milliseconds()

	if err != nil {
		return "unhealthy", latency
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusOK {
		return "healthy", latency
	}
	return "degraded", latency
}
