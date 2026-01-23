package handlers

import (
	"time"

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

// GetStats - Global admin statistics
func (h *AdminHandler) GetStats(c *fiber.Ctx) error {
	if !h.checkAdmin(c) {
		return fiber.NewError(fiber.StatusForbidden, "Admin access required")
	}

	var totalUsers, totalAPIKeys, totalJobs, totalScreenshots, totalPDFs int64

	h.db.Model(&models.User{}).Count(&totalUsers)
	h.db.Model(&models.APIKey{}).Count(&totalAPIKeys)
	h.db.Model(&models.RenderJob{}).Count(&totalJobs)

	// Screenshots vs PDFs
	h.db.Model(&models.RenderJob{}).Where("type = ?", "screenshot").Count(&totalScreenshots)
	h.db.Model(&models.RenderJob{}).Where("type = ?", "pdf").Count(&totalPDFs)

	// Recent Jobs for the overview table
	type RecentJob struct {
		ID        string    `json:"id"`
		URL       string    `json:"url"`
		UserEmail string    `json:"user_email"`
		Type      string    `json:"type"`
		Format    string    `json:"format"`
		Status    string    `json:"status"`
		CreatedAt time.Time `json:"created_at"`
	}

	var recentJobs []RecentJob
	h.db.Model(&models.RenderJob{}).
		Select(`
			render_jobs.id,
			COALESCE(render_jobs.url, '') as url,
			COALESCE(users.email, 'unknown') as user_email,
			render_jobs.type,
			COALESCE(render_jobs.format, 'jpeg') as format,
			render_jobs.status,
			render_jobs.created_at
		`).
		Joins("LEFT JOIN users ON render_jobs.user_id = users.id").
		Order("render_jobs.created_at DESC").
		Limit(10).
		Scan(&recentJobs)

	return c.JSON(fiber.Map{
		"total_users":       totalUsers,
		"total_api_keys":    totalAPIKeys,
		"total_jobs":        totalJobs,
		"total_screenshots": totalScreenshots,
		"total_pdfs":        totalPDFs,
		"recent_jobs":       recentJobs,
	})
}

// ListUsers - All users with counts
func (h *AdminHandler) ListUsers(c *fiber.Ctx) error {
	if !h.checkAdmin(c) {
		return fiber.NewError(fiber.StatusForbidden, "Admin access required")
	}

	page := c.QueryInt("page", 1)
	perPage := c.QueryInt("per_page", 20)
	offset := (page - 1) * perPage

	type UserWithCounts struct {
		models.User
		PlanName     string `json:"plan_name"`
		APIKeysCount int    `json:"api_keys_count"`
		JobsCount    int    `json:"jobs_count"`
	}

	var users []UserWithCounts
	var total int64

	// Get total count
	h.db.Model(&models.User{}).Count(&total)

	// Get paginated users with counts
	err := h.db.Model(&models.User{}).
		Select(`
            users.*,
            plans.display_name as plan_name,
            COUNT(DISTINCT api_keys.id) as api_keys_count,
            COUNT(DISTINCT render_jobs.id) as jobs_count
        `).
		Joins("LEFT JOIN plans ON users.plan_id = plans.id").
		Joins("LEFT JOIN api_keys ON users.id = api_keys.user_id").
		Joins("LEFT JOIN render_jobs ON users.id = render_jobs.user_id").
		Group("users.id, plans.display_name").
		Order("users.created_at DESC").
		Limit(perPage).
		Offset(offset).
		Scan(&users).Error

	if err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, "Failed to fetch users")
	}

	pages := int(total) / perPage
	if int(total)%perPage > 0 {
		pages++
	}

	return c.JSON(fiber.Map{
		"items":    users,
		"total":    total,
		"page":     page,
		"per_page": perPage,
		"pages":    pages,
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
			return c.Status(appErr.Code).JSON(fiber.Map{"detail": appErr.Message})
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

// ListAPIKeys - All API keys with pagination
func (h *AdminHandler) ListAPIKeys(c *fiber.Ctx) error {
	if !h.checkAdmin(c) {
		return fiber.NewError(fiber.StatusForbidden, "Admin access required")
	}

	page := c.QueryInt("page", 1)
	pageSize := c.QueryInt("page_size", 50)
	offset := (page - 1) * pageSize

	type APIKeyWithUser struct {
		ID         string     `json:"id"`
		Name       string     `json:"name"`
		KeyPrefix  string     `json:"key_prefix"`
		UserEmail  string     `json:"user_email"`
		UserID     string     `json:"user_id"`
		IsActive   bool       `json:"is_active"`
		JobsCount  int        `json:"jobs_count"`
		CreatedAt  time.Time  `json:"created_at"`
		LastUsedAt *time.Time `json:"last_used_at"`
	}

	var apiKeys []APIKeyWithUser

	err := h.db.Model(&models.APIKey{}).
		Select(`
            api_keys.id,
            api_keys.name,
            api_keys.key_prefix,
            COALESCE(users.email, 'unknown') as user_email,
            api_keys.user_id,
            api_keys.is_active,
            COUNT(render_jobs.id) as jobs_count,
            api_keys.created_at,
            api_keys.last_used_at
        `).
		Joins("LEFT JOIN users ON api_keys.user_id = users.id").
		Joins("LEFT JOIN render_jobs ON render_jobs.api_key_id = api_keys.id").
		Group("api_keys.id, users.email").
		Order("api_keys.created_at DESC").
		Limit(pageSize).
		Offset(offset).
		Scan(&apiKeys).Error

	if err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, "Failed to fetch API keys")
	}

	var total int64
	h.db.Model(&models.APIKey{}).Count(&total)

	pages := int(total) / pageSize
	if int(total)%pageSize > 0 {
		pages++
	}

	return c.JSON(fiber.Map{
		"items":    apiKeys,
		"total":    total,
		"page":     page,
		"per_page": pageSize,
		"pages":    pages,
	})
}

// ListJobs - All render jobs with pagination
func (h *AdminHandler) ListJobs(c *fiber.Ctx) error {
	if !h.checkAdmin(c) {
		return fiber.NewError(fiber.StatusForbidden, "Admin access required")
	}

	page := c.QueryInt("page", 1)
	pageSize := c.QueryInt("page_size", 100)
	offset := (page - 1) * pageSize

	type JobWithUser struct {
		ID               string    `json:"id"`
		UserEmail        string    `json:"user_email"`
		Type             string    `json:"type"`
		Status           string    `json:"status"`
		URL              string    `json:"url"`
		Format           string    `json:"format"`
		ProcessingTimeMs *int      `json:"processing_time_ms"`
		FileSizeBytes    *int      `json:"file_size_bytes"`
		CreatedAt        time.Time `json:"created_at"`
	}

	var jobs []JobWithUser

	err := h.db.Model(&models.RenderJob{}).
		Select(`
            render_jobs.id,
            COALESCE(users.email, 'unknown') as user_email,
            render_jobs.type,
            render_jobs.status,
            COALESCE(render_jobs.url, '') as url,
            COALESCE(render_jobs.format, '') as format,
            render_jobs.processing_time_ms,
            render_jobs.file_size_bytes,
            render_jobs.created_at
        `).
		Joins("LEFT JOIN users ON render_jobs.user_id = users.id").
		Order("render_jobs.created_at DESC").
		Limit(pageSize).
		Offset(offset).
		Scan(&jobs).Error

	if err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, "Failed to fetch jobs")
	}

	var total int64
	h.db.Model(&models.RenderJob{}).Count(&total)

	pages := int(total) / pageSize
	if int(total)%pageSize > 0 {
		pages++
	}

	return c.JSON(fiber.Map{
		"items":    jobs,
		"total":    total,
		"page":     page,
		"per_page": pageSize,
		"pages":    pages,
	})
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

func (h *AdminHandler) GetDemoStats(c *fiber.Ctx) error {
	if !h.checkAdmin(c) {
		return fiber.NewError(fiber.StatusForbidden, "Admin access required")
	}

	var demoUser models.User
	if err := h.db.Where("email = ?", "demo@screenshotbeam.com").First(&demoUser).Error; err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, "Demo user not found")
	}

	now := time.Now()
	today := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, time.UTC)
	weekAgo := now.AddDate(0, 0, -7)

	var totalToday, totalWeek, totalAllTime int64
	h.db.Model(&models.RenderJob{}).Where("user_id = ? AND created_at >= ?", demoUser.ID, today).Count(&totalToday)
	h.db.Model(&models.RenderJob{}).Where("user_id = ? AND created_at >= ?", demoUser.ID, weekAgo).Count(&totalWeek)
	h.db.Model(&models.RenderJob{}).Where("user_id = ?", demoUser.ID).Count(&totalAllTime)

	type URLCount struct {
		URL   string `json:"url"`
		Count int    `json:"count"`
	}
	var topURLs []URLCount
	h.db.Model(&models.RenderJob{}).
		Select("url, COUNT(*) as count").
		Where("user_id = ?", demoUser.ID).
		Group("url").
		Order("count DESC").
		Limit(10).
		Scan(&topURLs)

	type RecentCapture struct {
		ID           string    `json:"id"`
		URL          string    `json:"url"`
		IP           string    `json:"ip"`
		Country      string    `json:"country"`
		Timestamp    time.Time `json:"timestamp"`
		RenderTimeMs int       `json:"render_time_ms"`
		Width        int       `json:"width"`
		Height       int       `json:"height"`
	}

	var recentCaptures []RecentCapture
	h.db.Model(&models.RenderJob{}).
		Select(`
            id, 
            COALESCE(url, '') as url, 
            COALESCE(ip_address, '') as ip, 
            COALESCE(country_code, '') as country, 
            created_at as timestamp, 
            COALESCE(processing_time_ms, 0) as render_time_ms, 
            COALESCE(width, 0) as width, 
            COALESCE(height, 0) as height
        `).
		Where("user_id = ?", demoUser.ID).
		Order("created_at DESC").
		Limit(50).
		Scan(&recentCaptures)

	return c.JSON(fiber.Map{
		"total_today":     totalToday,
		"total_week":      totalWeek,
		"total_all_time":  totalAllTime,
		"top_urls":        topURLs,
		"recent_captures": recentCaptures,
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
