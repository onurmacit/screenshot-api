package handlers

import (
	"time"

	"github.com/gofiber/fiber/v2"
	"gorm.io/gorm"
)

type HealthHandler struct {
	db *gorm.DB
}

func NewHealthHandler(db *gorm.DB) *HealthHandler {
	return &HealthHandler{db: db}
}

// Health returns API health status
func (h *HealthHandler) Health(c *fiber.Ctx) error {
	// Check database connection
	sqlDB, err := h.db.DB()
	dbStatus := "connected"
	if err != nil || sqlDB.Ping() != nil {
		dbStatus = "disconnected"
	}

	return c.JSON(fiber.Map{
		"status":    "ok",
		"version":   "1.0.0",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
		"database":  dbStatus,
	})
}

// DetailedHealth returns detailed health information
func (h *HealthHandler) DetailedHealth(c *fiber.Ctx) error {
	sqlDB, err := h.db.DB()
	dbStatus := "healthy"
	dbLatency := int64(0)

	if err != nil {
		dbStatus = "unhealthy"
	} else {
		start := time.Now()
		if sqlDB.Ping() != nil {
			dbStatus = "unhealthy"
		}
		dbLatency = time.Since(start).Milliseconds()
	}

	return c.JSON(fiber.Map{
		"status":    "ok",
		"version":   "1.0.0",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
		"services": fiber.Map{
			"database": fiber.Map{
				"status":     dbStatus,
				"latency_ms": dbLatency,
			},
			"renderer": fiber.Map{
				"status": "healthy",
			},
		},
	})
}
