package handlers

import (
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/models"
	"github.com/onurmacit/screenshot-api/api-go/internal/services"
	"gorm.io/gorm"
)

type UsageHandler struct {
	db           *gorm.DB
	cfg          *config.Config
	usageService *services.UsageService
}

func NewUsageHandler(db *gorm.DB, cfg *config.Config, usageService *services.UsageService) *UsageHandler {
	return &UsageHandler{db: db, cfg: cfg, usageService: usageService}
}

// GetCurrentUsage returns current usage statistics for the authenticated user
func (h *UsageHandler) GetCurrentUsage(c *fiber.Ctx) error {
	user := c.Locals("user").(*models.User)

	// Get current month period
	now := time.Now().UTC()
	periodStart := time.Date(now.Year(), now.Month(), 1, 0, 0, 0, 0, time.UTC)
	var periodEnd time.Time
	if now.Month() == 12 {
		periodEnd = time.Date(now.Year()+1, 1, 1, 0, 0, 0, 0, time.UTC)
	} else {
		periodEnd = time.Date(now.Year(), now.Month()+1, 1, 0, 0, 0, 0, time.UTC)
	}

	// Get plan info
	var plan models.Plan
	h.db.First(&plan, user.PlanID)

	// Get usage from DB for current month
	var usageCount int64
	h.db.Model(&models.RenderJob{}).
		Where("user_id = ? AND created_at >= ? AND created_at < ?", user.ID, periodStart, periodEnd).
		Count(&usageCount)

	requestsLimit := plan.RequestsPerMonth
	percentage := float64(0)
	if requestsLimit > 0 {
		percentage = float64(usageCount) / float64(requestsLimit) * 100
		if percentage > 100 {
			percentage = 100
		}
	}

	return c.JSON(fiber.Map{
		"period":       periodStart.Format("2006-01"),
		"period_start": periodStart,
		"period_end":   periodEnd,
		"plan": fiber.Map{
			"id":                 plan.ID,
			"name":               plan.Name,
			"display_name":       plan.DisplayName,
			"requests_per_month": plan.RequestsPerMonth,
		},
		"usage": fiber.Map{
			"requests_used":  usageCount,
			"requests_limit": requestsLimit,
			"percentage":     percentage,
		},
		"rate_limits": fiber.Map{
			"per_minute": fiber.Map{
				"used":      0, // Would need Redis integration for real-time
				"limit":     plan.MaxConcurrentRequests * 10,
				"remaining": plan.MaxConcurrentRequests * 10,
			},
			"per_hour": fiber.Map{
				"used":      0,
				"limit":     plan.RequestsPerMonth / 30 / 24,
				"remaining": plan.RequestsPerMonth / 30 / 24,
			},
		},
		"next_reset": now.Truncate(time.Minute).Add(time.Minute),
	})
}

// GetUsageHistory returns historical usage data
func (h *UsageHandler) GetUsageHistory(c *fiber.Ctx) error {
	user := c.Locals("user").(*models.User)

	// Parse query params
	startDateStr := c.Query("start_date", "")
	endDateStr := c.Query("end_date", "")
	granularity := c.Query("granularity", "day")

	now := time.Now().UTC()
	var startDate, endDate time.Time

	if startDateStr != "" {
		parsed, err := time.Parse("2006-01-02", startDateStr)
		if err == nil {
			startDate = parsed
		} else {
			startDate = now.AddDate(0, 0, -30)
		}
	} else {
		startDate = now.AddDate(0, 0, -30)
	}

	if endDateStr != "" {
		parsed, err := time.Parse("2006-01-02", endDateStr)
		if err == nil {
			endDate = parsed
		} else {
			endDate = now
		}
	} else {
		endDate = now
	}

	// Query jobs grouped by date
	var dateFormat string
	switch granularity {
	case "month":
		dateFormat = "YYYY-MM"
	case "week":
		dateFormat = "IYYY-IW"
	default:
		dateFormat = "YYYY-MM-DD"
	}

	type DailyUsage struct {
		Date           string `json:"date"`
		Total          int    `json:"requests"`
		Screenshots    int    `json:"screenshots"`
		PDFs           int    `json:"pdfs"`
		ProcessingTime int64  `json:"total_processing_time_ms"`
		FileSize       int64  `json:"total_file_size_bytes"`
	}

	var results []struct {
		Date           string
		Total          int64
		Screenshots    int64
		PDFs           int64
		ProcessingTime int64
		FileSize       int64
	}

	h.db.Model(&models.RenderJob{}).
		Select(`
			TO_CHAR(created_at, '`+dateFormat+`') as date,
			COUNT(*) as total,
			COUNT(CASE WHEN type = 'screenshot' THEN 1 END) as screenshots,
			COUNT(CASE WHEN type = 'pdf' THEN 1 END) as pdfs,
			COALESCE(SUM(processing_time_ms), 0) as processing_time,
			COALESCE(SUM(file_size_bytes), 0) as file_size
		`).
		Where("user_id = ? AND created_at >= ? AND created_at <= ? AND status = 'completed'",
			user.ID, startDate, endDate).
		Group("date").
		Order("date").
		Find(&results)

	// Build response
	usageData := make([]DailyUsage, len(results))
	var totalRequests int64
	var totalProcessingTime int64
	var totalFileSize int64

	for i, r := range results {
		usageData[i] = DailyUsage{
			Date:           r.Date,
			Total:          int(r.Total),
			Screenshots:    int(r.Screenshots),
			PDFs:           int(r.PDFs),
			ProcessingTime: r.ProcessingTime,
			FileSize:       r.FileSize,
		}
		totalRequests += r.Total
		totalProcessingTime += r.ProcessingTime
		totalFileSize += r.FileSize
	}

	return c.JSON(fiber.Map{
		"start_date":               startDate.Format("2006-01-02"),
		"end_date":                 endDate.Format("2006-01-02"),
		"granularity":              granularity,
		"usage":                    usageData,
		"total_requests":           totalRequests,
		"total_processing_time_ms": totalProcessingTime,
		"total_file_size_bytes":    totalFileSize,
	})
}
