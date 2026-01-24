package handlers

import (
	"os"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"gorm.io/gorm"
)

type HealthHandler struct {
	db  *gorm.DB
	cfg *config.Config
}

type HealthResponse struct {
	Status       string            `json:"status"`
	Version      string            `json:"version"`
	CommitSHA    string            `json:"commit_sha"`
	Instance     string            `json:"instance"`
	Timestamp    time.Time         `json:"timestamp"`
	Uptime       float64           `json:"uptime_seconds"`
	Dependencies map[string]string `json:"dependencies,omitempty"`
}

var startTime = time.Now()

func NewHealthHandler(db *gorm.DB, cfg *config.Config) *HealthHandler {
	return &HealthHandler{
		db:  db,
		cfg: cfg,
	}
}

// Health - Basic health check (for Docker healthcheck)
func (h *HealthHandler) Health(c *fiber.Ctx) error {
	// Quick database check
	if db, err := h.db.DB(); err != nil {
		return c.Status(503).JSON(fiber.Map{"status": "unhealthy", "error": "database connection failed"})
	} else if err := db.Ping(); err != nil {
		return c.Status(503).JSON(fiber.Map{"status": "unhealthy", "error": "database ping failed"})
	}

	return c.JSON(HealthResponse{
		Status:    "healthy",
		Version:   os.Getenv("VERSION"),
		CommitSHA: os.Getenv("COMMIT_SHA"),
		Instance:  os.Getenv("INSTANCE_COLOR"),
		Timestamp: time.Now(),
		Uptime:    time.Since(startTime).Seconds(),
	})
}

// DetailedHealth - Detailed health check with all dependencies
func (h *HealthHandler) DetailedHealth(c *fiber.Ctx) error {
	deps := make(map[string]string)
	allHealthy := true

	// Check database
	if db, err := h.db.DB(); err != nil {
		deps["database"] = "unhealthy: " + err.Error()
		allHealthy = false
	} else if err := db.Ping(); err != nil {
		deps["database"] = "unhealthy: ping failed"
		allHealthy = false
	} else {
		deps["database"] = "healthy"
	}

	// Check Redis via config (if available)
	if h.cfg.RedisURL != "" {
		deps["redis"] = "configured"
	} else {
		deps["redis"] = "not configured"
	}

	// Check renderer
	if h.cfg.GoRendererURL != "" {
		deps["renderer"] = "configured: " + h.cfg.GoRendererURL
	} else {
		deps["renderer"] = "not configured"
	}

	status := "healthy"
	if !allHealthy {
		status = "unhealthy"
	}

	response := HealthResponse{
		Status:       status,
		Version:      os.Getenv("VERSION"),
		CommitSHA:    os.Getenv("COMMIT_SHA"),
		Instance:     os.Getenv("INSTANCE_COLOR"),
		Timestamp:    time.Now(),
		Uptime:       time.Since(startTime).Seconds(),
		Dependencies: deps,
	}

	if !allHealthy {
		return c.Status(503).JSON(response)
	}

	return c.JSON(response)
}

// Ready - Kubernetes readiness probe
func (h *HealthHandler) Ready(c *fiber.Ctx) error {
	// Check if app can handle traffic
	if db, err := h.db.DB(); err != nil {
		return c.Status(503).SendString("not ready: database unavailable")
	} else if err := db.Ping(); err != nil {
		return c.Status(503).SendString("not ready: database ping failed")
	}

	return c.SendString("ready")
}

// Live - Kubernetes liveness probe
func (h *HealthHandler) Live(c *fiber.Ctx) error {
	// Simple check - is the app running?
	return c.SendString("alive")
}
