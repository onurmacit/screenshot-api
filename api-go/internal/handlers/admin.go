package handlers

import (
	"github.com/gofiber/fiber/v2"
	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/models"
	"gorm.io/gorm"
)

type AdminHandler struct {
	db  *gorm.DB
	cfg *config.Config
}

func NewAdminHandler(db *gorm.DB, cfg *config.Config) *AdminHandler {
	return &AdminHandler{db: db, cfg: cfg}
}

func (h *AdminHandler) checkAdmin(c *fiber.Ctx) bool {
	user := c.Locals("user").(*models.User)
	for _, email := range h.cfg.AdminEmails {
		if user.Email == email {
			return true
		}
	}
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
