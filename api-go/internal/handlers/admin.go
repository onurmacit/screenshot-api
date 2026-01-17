package handlers

import (
	"github.com/gofiber/fiber/v2"
	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/middleware"
	"github.com/onurmacit/screenshot-api/api-go/internal/models"
	"github.com/onurmacit/screenshot-api/api-go/internal/services"
	"github.com/onurmacit/screenshot-api/api-go/internal/utils"
	"gorm.io/gorm"
)

type AdminHandler struct {
	db             *gorm.DB
	cfg            *config.Config
	billingService *services.BillingService
}

func NewAdminHandler(db *gorm.DB, cfg *config.Config, billingService *services.BillingService) *AdminHandler {
	return &AdminHandler{db: db, cfg: cfg, billingService: billingService}
}

func (h *AdminHandler) checkAdmin(c *fiber.Ctx) bool {
	user := c.Locals("user").(*models.User)
	for _, email := range h.cfg.AdminEmails {
		if user.Email == email {
			return true
		}
	}
	// Be careful with nil user. Middleware ensures it.
	return false
}

func (h *AdminHandler) GetStats(c *fiber.Ctx) error {
	if !h.checkAdmin(c) {
		return fiber.NewError(fiber.StatusForbidden, "Admin access required")
	}

	var totalUsers int64
	var totalJobs int64
	var totalKeys int64

	if err := h.db.Model(&models.User{}).Count(&totalUsers).Error; err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, "DB Error")
	}
	h.db.Model(&models.RenderJob{}).Count(&totalJobs)
	h.db.Model(&models.APIKey{}).Count(&totalKeys)

	return c.JSON(fiber.Map{
		"users": totalUsers,
		"jobs":  totalJobs,
		"keys":  totalKeys,
	})
}

func (h *AdminHandler) ListUsers(c *fiber.Ctx) error {
	if !h.checkAdmin(c) {
		return fiber.NewError(fiber.StatusForbidden, "Admin access required")
	}

	limit := c.QueryInt("limit", 20)
	offset := c.QueryInt("offset", 0)

	var users []models.User
	var total int64

	if err := h.db.Model(&models.User{}).Count(&total).Error; err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, "DB Error")
	}

	if err := h.db.Preload("Plan").Limit(limit).Offset(offset).Order("created_at desc").Find(&users).Error; err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, "DB Error")
	}

	return c.JSON(fiber.Map{
		"items":  users,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

func (h *AdminHandler) GetUserUsage(c *fiber.Ctx) error {
	if !h.checkAdmin(c) {
		return fiber.NewError(fiber.StatusForbidden, "Admin access required")
	}

	userID := c.Params("id")
	if userID == "" {
		return fiber.NewError(fiber.StatusBadRequest, "User ID required")
	}

	var records []models.UsageRecord
	if err := h.db.Where("user_id = ?", userID).Order("month desc").Find(&records).Error; err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, "DB Error")
	}

	return c.JSON(records)
}

func (h *AdminHandler) UpdateUserPlan(c *fiber.Ctx) error {
	if !h.checkAdmin(c) {
		return fiber.NewError(fiber.StatusForbidden, "Admin access required")
	}

	userID := c.Params("id")
	if userID == "" {
		return fiber.NewError(fiber.StatusBadRequest, "User ID required")
	}

	var req struct {
		PlanID int `json:"plan_id"`
	}
	if err := c.BodyParser(&req); err != nil {
		return utils.ErrBadRequest
	}

	if err := h.billingService.SetUserPlan(c.Context(), userID, req.PlanID); err != nil {
		if appErr, ok := err.(*utils.AppError); ok {
			return c.Status(appErr.Code).JSON(fiber.Map{"error": appErr.Message})
		}
		return fiber.NewError(fiber.StatusInternalServerError, err.Error())
	}

	return c.JSON(fiber.Map{"status": "success", "message": "Plan updated"})
}

func (h *AdminHandler) ListPlans(c *fiber.Ctx) error {
	if !h.checkAdmin(c) {
		return fiber.NewError(fiber.StatusForbidden, "Admin access required")
	}

	plans, err := h.billingService.GetPlans(c.Context())
	if err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, err.Error())
	}

	return c.JSON(plans)
}

func (h *AdminHandler) GetMetrics(c *fiber.Ctx) error {
	if !h.checkAdmin(c) {
		return fiber.NewError(fiber.StatusForbidden, "Admin access required")
	}

	metrics := middleware.GetMetrics()

	return c.JSON(fiber.Map{
		"total_requests":   metrics.TotalRequests,
		"total_errors":     metrics.TotalErrors,
		"error_rate":       float64(metrics.TotalErrors) / float64(max(metrics.TotalRequests, 1)) * 100,
		"requests_by_code": metrics.RequestsByCode,
		"top_paths":        getTopPaths(metrics.RequestsByPath, 10),
	})
}

func max(a, b int64) int64 {
	if a > b {
		return a
	}
	return b
}

func getTopPaths(paths map[string]int64, limit int) []fiber.Map {
	result := make([]fiber.Map, 0, limit)
	for path, count := range paths {
		if len(result) < limit {
			result = append(result, fiber.Map{"path": path, "count": count})
		}
	}
	return result
}
