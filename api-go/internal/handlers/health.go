package handlers

import (
	"os"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/redis/go-redis/v9"
	"gorm.io/gorm"
)

type HealthHandler struct {
	db    *gorm.DB
	redis *redis.Client
}

type HealthResponse struct {
	Status       string            `json:"status"`
	Version      string            `json:"version"`
	CommitSHA    string            `json:"commit_sha"`
	Instance     string            `json:"instance"`
	Timestamp    time.Time         `json:"timestamp"`
	Uptime       float64           `json:"uptime_seconds"`
	Dependencies map[string]string `json:"dependencies"`
}

var startTime = time.Now()

func NewHealthHandler(db *gorm.DB, redis *redis.Client) *HealthHandler {
	return &HealthHandler{
		db:    db,
		redis: redis,
	}
}

// Health - Detailed health check
func (h *HealthHandler) Health(c *fiber.Ctx) error {
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

	// Check Redis
	if err := h.redis.Ping(c.Context()).Err(); err != nil {
		deps["redis"] = "unhealthy: " + err.Error()
		allHealthy = false
	} else {
		deps["redis"] = "healthy"
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
	if db, err := h.db.DB(); err != nil || db.Ping() != nil {
		return c.Status(503).SendString("not ready: database unavailable")
	}

	return c.SendString("ready")
}

// Live - Kubernetes liveness probe
func (h *HealthHandler) Live(c *fiber.Ctx) error {
	// Simple check - is the app running?
	return c.SendString("alive")
}
