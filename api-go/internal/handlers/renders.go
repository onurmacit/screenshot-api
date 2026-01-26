package handlers

import (
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/onurmacit/screenshot-api/api-go/internal/dto"
	"github.com/onurmacit/screenshot-api/api-go/internal/models"
	"github.com/onurmacit/screenshot-api/api-go/internal/services"
	"github.com/onurmacit/screenshot-api/api-go/internal/utils"
	"gorm.io/gorm"
)

type RenderHandler struct {
	renderService *services.RenderService
	authService   *services.AuthService
	db            *gorm.DB
}

func NewRenderHandler(renderService *services.RenderService, authService *services.AuthService, db *gorm.DB) *RenderHandler {
	return &RenderHandler{
		renderService: renderService,
		authService:   authService,
		db:            db,
	}
}

// CreateScreenshot handles POST /renders/screenshot
// Supports ?async=true for async processing (returns 202 with job_id)
func (h *RenderHandler) CreateScreenshot(c *fiber.Ctx) error {
	// 1. Parse Request
	var req dto.RenderRequest
	if err := c.BodyParser(&req); err != nil {
		return fiber.NewError(fiber.StatusBadRequest, "Invalid JSON body")
	}

	// 2. Default Values
	if req.Width == 0 {
		req.Width = 1920
	}
	if req.Height == 0 {
		req.Height = 1080
	}
	if req.Format == "" {
		req.Format = "jpeg"
	}
	if req.Quality == 0 {
		req.Quality = 80
	}
	if req.Timeout == 0 {
		req.Timeout = 30000
	}

	// 3. Validate URL (SSRF Protection - SEC-003)
	if req.URL != "" {
		if err := utils.ValidateURL(req.URL); err != nil {
			return fiber.NewError(fiber.StatusUnprocessableEntity, err.Error())
		}
	}

	// 3.5. Extract IP and Country
	req.IPAddress, req.CountryCode = h.getIPAndCountry(c)

	// 4. Get User from Context (set by AuthMiddleware)
	user := c.Locals("user").(*models.User)

	// 5. Check if async mode requested
	if c.Query("async") == "true" {
		// Async mode: enqueue job and return immediately
		jobResult, err := h.renderService.CaptureScreenshotAsync(c.Context(), req, user)
		if err != nil {
			if appErr, ok := err.(*utils.AppError); ok {
				return c.Status(appErr.Code).JSON(fiber.Map{"detail": appErr.Message})
			}
			return utils.ErrInternal
		}
		// Return 202 Accepted with job details
		return c.Status(fiber.StatusAccepted).JSON(fiber.Map{
			"job_id":     jobResult.JobID,
			"status":     jobResult.Status,
			"type":       jobResult.Type,
			"url":        jobResult.URL,
			"created_at": jobResult.CreatedAt,
			"message":    "Job queued for processing. Poll GET /api/v1/jobs/{job_id} for status.",
		})
	}

	// 6. Sync mode: Call Service (existing behavior)
	result, err := h.renderService.CaptureScreenshot(c.Context(), req, user)
	if err != nil {
		if appErr, ok := err.(*utils.AppError); ok {
			return c.Status(appErr.Code).JSON(fiber.Map{"detail": appErr.Message})
		}
		return utils.ErrInternal
	}

	// 7. Return Response
	if h.isBinaryRequest(c, &req) {
		return h.handleBinaryResponse(c, result)
	}

	return c.JSON(result)
}

// CreateJob handles POST /renders/jobs (Async processing)
func (h *RenderHandler) CreateJob(c *fiber.Ctx) error {
	var req dto.RenderRequest
	if err := c.BodyParser(&req); err != nil {
		return fiber.NewError(fiber.StatusBadRequest, "Invalid JSON body")
	}

	// Default Values (Same as sync)
	if req.Width == 0 {
		req.Width = 1920
	}
	if req.Height == 0 {
		req.Height = 1080
	}
	if req.Format == "" {
		req.Format = "jpeg"
	}

	req.IPAddress, req.CountryCode = h.getIPAndCountry(c)

	user := c.Locals("user").(*models.User)

	job, err := h.renderService.CreateRenderJob(c.Context(), req, user)
	if err != nil {
		if appErr, ok := err.(*utils.AppError); ok {
			return c.Status(appErr.Code).JSON(fiber.Map{"detail": appErr.Message})
		}
		return utils.ErrInternal
	}

	return c.Status(fiber.StatusAccepted).JSON(job)
}

// CreatePDF handles POST /renders/pdf
func (h *RenderHandler) CreatePDF(c *fiber.Ctx) error {
	var req dto.PDFRequest
	if err := c.BodyParser(&req); err != nil {
		return fiber.NewError(fiber.StatusBadRequest, "Invalid JSON body")
	}

	// Basic Validation
	if req.URL == "" && req.HTML == "" && req.Markdown == "" {
		return fiber.NewError(fiber.StatusBadRequest, "URL, HTML or Markdown is required")
	}

	// URL Validation (SSRF Protection - SEC-003)
	if req.URL != "" {
		if err := utils.ValidateURL(req.URL); err != nil {
			return fiber.NewError(fiber.StatusUnprocessableEntity, err.Error())
		}
	}

	req.IPAddress, req.CountryCode = h.getIPAndCountry(c)

	user := c.Locals("user").(*models.User)

	result, err := h.renderService.CreatePDF(c.Context(), req, user)
	if err != nil {
		if appErr, ok := err.(*utils.AppError); ok {
			return c.Status(appErr.Code).JSON(fiber.Map{"detail": appErr.Message})
		}
		return utils.ErrInternal
	}

	return c.JSON(result)
}

// SignURL handles POST /renders/sign-url
func (h *RenderHandler) SignURL(c *fiber.Ctx) error {
	var req dto.SignURLRequest
	if err := c.BodyParser(&req); err != nil {
		return fiber.NewError(fiber.StatusBadRequest, "Invalid JSON body")
	}

	// 1. Get API Key from Locals
	apiKey, ok := c.Locals("apiKey").(*models.APIKey)
	if !ok || apiKey == nil {
		return fiber.NewError(fiber.StatusForbidden, "API Key required for signing")
	}

	// 2. Decrypt Secret
	if apiKey.SecretKey == "" || apiKey.SecretKey == "legacy" {
		return fiber.NewError(fiber.StatusForbidden, "This API Key does not support signing. Please create a new key.")
	}

	keyEnc := h.renderService.Config().SecretKeyEncryptionKey
	if keyEnc == "" {
		return fiber.NewError(fiber.StatusInternalServerError, "Encryption key not configured")
	}

	secretKey, err := utils.Decrypt(apiKey.SecretKey, keyEnc)
	if err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, "Failed to decrypt secret key")
	}

	// 3. Get Raw Access Key
	rawAccessKey := c.Get("X-API-Key")
	if rawAccessKey == "" {
		rawAccessKey = c.Query("api_key")
	}
	if rawAccessKey == "" {
		auth := c.Get("Authorization")
		if len(auth) > 7 && auth[:7] == "Bearer " {
			rawAccessKey = auth[7:]
		}
	}

	// 4. Call Service
	result, err := h.renderService.SignURL(c.Context(), req, rawAccessKey, secretKey)
	if err != nil {
		if appErr, ok := err.(*utils.AppError); ok {
			return c.Status(appErr.Code).JSON(fiber.Map{"detail": appErr.Message})
		}
		return utils.ErrInternal
	}

	return c.JSON(result)
}

// RenderSigned handles GET/POST /renders/signed
func (h *RenderHandler) RenderSigned(c *fiber.Ctx) error {
	// 1. Get Critical Params
	accessKey := c.Query("access_key")
	signature := c.Query("signature")
	expiresStr := c.Query("expires")

	if accessKey == "" || signature == "" || expiresStr == "" {
		return fiber.NewError(fiber.StatusUnauthorized, "Missing signature params")
	}

	// 2. Validate Expiry
	expires, err := strconv.ParseInt(expiresStr, 10, 64)
	if err != nil {
		return fiber.NewError(fiber.StatusBadRequest, "Invalid expiry format")
	}
	if time.Now().Unix() > expires {
		return fiber.NewError(fiber.StatusForbidden, "Link expired")
	}

	// 3. Validate API Key
	user, apiKey, err := h.authService.ValidateAPIKey(c.Context(), accessKey)
	if err != nil {
		return fiber.NewError(fiber.StatusUnauthorized, "Invalid access key")
	}

	// 4. Decrypt Secret
	keyEnc := h.renderService.Config().SecretKeyEncryptionKey
	secretKey, err := utils.Decrypt(apiKey.SecretKey, keyEnc)
	if err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, "Server configuration error")
	}

	// 5. Verify Signature
	params := c.Queries()
	delete(params, "signature") // Verify everything else

	if !utils.VerifySignature(params, secretKey, signature) {
		return fiber.NewError(fiber.StatusForbidden, "Invalid signature")
	}

	// 6. Build Request
	var req dto.RenderRequest
	if err := c.QueryParser(&req); err != nil {
		return fiber.NewError(fiber.StatusBadRequest, "Invalid params")
	}

	// Apply Defaults
	if req.Width == 0 {
		req.Width = 1920
	}
	if req.Height == 0 {
		req.Height = 1080
	}
	if req.Format == "" {
		req.Format = "jpeg"
	}

	req.IPAddress, req.CountryCode = h.getIPAndCountry(c)

	// 7. Render
	result, err := h.renderService.CaptureScreenshot(c.Context(), req, user)
	if err != nil {
		if appErr, ok := err.(*utils.AppError); ok {
			return c.Status(appErr.Code).JSON(fiber.Map{"detail": appErr.Message})
		}
		return utils.ErrInternal
	}

	if h.isBinaryRequest(c, &req) {
		return h.handleBinaryResponse(c, result)
	}

	return c.JSON(result)
}

// CreateDemo handles POST /renders/demo
func (h *RenderHandler) CreateDemo(c *fiber.Ctx) error {
	var req dto.DemoRequest
	if err := c.BodyParser(&req); err != nil {
		return fiber.NewError(fiber.StatusBadRequest, "Invalid JSON body")
	}

	if req.URL == "" || req.Token == "" {
		return fiber.NewError(fiber.StatusBadRequest, "URL and Token are required")
	}

	// URL Validation (SSRF Protection - SEC-003)
	if err := utils.ValidateURL(req.URL); err != nil {
		return fiber.NewError(fiber.StatusUnprocessableEntity, err.Error())
	}

	// 1. Verify Turnstile
	ip := c.IP()
	if !utils.VerifyTurnstile(req.Token, h.renderService.Config().TurnstileSecretKey, ip) {
		return fiber.NewError(fiber.StatusForbidden, "Captcha verification failed")
	}

	// 2. Get Demo User
	user, err := h.authService.GetOrCreateDemoUser(c.Context())
	if err != nil {
		return utils.ErrInternal
	}

	// ✅ Extract IP and Country
	ipAddress, countryCode := h.getIPAndCountry(c)

	// 3. Render
	renderReq := dto.RenderRequest{
		URL:           req.URL,
		Width:         1280,
		Height:        720,
		Format:        "jpeg",
		FullPage:      false, // Demo Limit
		BlockAds:      true,
		BlockTrackers: true,
		IPAddress:     ipAddress,
		CountryCode:   countryCode,
	}

	result, err := h.renderService.CaptureScreenshot(c.Context(), renderReq, user)
	if err != nil {
		if appErr, ok := err.(*utils.AppError); ok {
			return c.Status(appErr.Code).JSON(fiber.Map{"detail": appErr.Message})
		}
		return utils.ErrInternal
	}

	return c.JSON(result)
}

// FastScreenshot handles GET /renders (Query Params)
func (h *RenderHandler) FastScreenshot(c *fiber.Ctx) error {
	var req dto.RenderRequest
	if err := c.QueryParser(&req); err != nil {
		return fiber.NewError(fiber.StatusBadRequest, "Invalid query params")
	}

	// Basic Validation
	if req.URL == "" {
		return fiber.NewError(fiber.StatusBadRequest, "URL is required")
	}

	// Apply Defaults
	if req.Width == 0 {
		req.Width = 1920
	}
	if req.Height == 0 {
		req.Height = 1080
	}
	if req.Format == "" {
		req.Format = "jpeg"
	}

	// URL Validation (SSRF Protection - SEC-003)
	if err := utils.ValidateURL(req.URL); err != nil {
		return fiber.NewError(fiber.StatusUnprocessableEntity, err.Error())
	}

	req.IPAddress, req.CountryCode = h.getIPAndCountry(c)

	user := c.Locals("user").(*models.User)

	result, err := h.renderService.CaptureScreenshot(c.Context(), req, user)
	if err != nil {
		if appErr, ok := err.(*utils.AppError); ok {
			return c.Status(appErr.Code).JSON(fiber.Map{"detail": appErr.Message})
		}
		return utils.ErrInternal
	}

	if h.isBinaryRequest(c, &req) {
		return h.handleBinaryResponse(c, result)
	}

	return c.JSON(result)
}

// ListJobs handles GET /jobs
func (h *RenderHandler) ListJobs(c *fiber.Ctx) error {
	user := c.Locals("user").(*models.User)
	limit := c.QueryInt("limit", 10)
	offset := c.QueryInt("offset", 0)

	jobs, total, err := h.renderService.ListJobs(c.Context(), user.ID, limit, offset)
	if err != nil {
		if appErr, ok := err.(*utils.AppError); ok {
			return c.Status(appErr.Code).JSON(fiber.Map{"detail": appErr.Message})
		}
		return utils.ErrInternal
	}

	return c.JSON(fiber.Map{
		"items":  jobs,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// GetJob handles GET /jobs/:id
func (h *RenderHandler) GetJob(c *fiber.Ctx) error {
	user := c.Locals("user").(*models.User)
	jobID := c.Params("id")

	if jobID == "" {
		return fiber.NewError(fiber.StatusBadRequest, "Job ID required")
	}

	job, err := h.renderService.GetJob(c.Context(), user.ID, jobID)
	if err != nil {
		if appErr, ok := err.(*utils.AppError); ok {
			return c.Status(appErr.Code).JSON(fiber.Map{"detail": appErr.Message})
		}
		return utils.ErrInternal
	}

	return c.JSON(job)
}

// DeleteJob handles DELETE /jobs/:id
func (h *RenderHandler) DeleteJob(c *fiber.Ctx) error {
	user := c.Locals("user").(*models.User)
	jobID := c.Params("id")

	if jobID == "" {
		return fiber.NewError(fiber.StatusBadRequest, "Job ID is required")
	}

	if err := h.renderService.DeleteJob(c.Context(), jobID, user.ID); err != nil {
		if appErr, ok := err.(*utils.AppError); ok {
			return c.Status(appErr.Code).JSON(fiber.Map{"detail": appErr.Message})
		}
		return utils.ErrInternal
	}

	return c.SendStatus(fiber.StatusNoContent)
}

// Helpers for Binary Response (Migration Fix)

func (h *RenderHandler) isBinaryRequest(c *fiber.Ctx, req *dto.RenderRequest) bool {
	// 1. Check Query/Body param
	if req.ResponseType == "binary" || req.ResponseType == "by_format" {
		return true
	}

	// 2. Check Accept header
	accept := c.Get("Accept")
	if accept != "" && accept != "*/*" && !strings.Contains(accept, "application/json") {
		if strings.Contains(accept, "image/") || strings.Contains(accept, "application/pdf") {
			return true
		}
	}

	return false
}

func (h *RenderHandler) handleBinaryResponse(c *fiber.Ctx, result *dto.ScreenshotResponse) error {
	// Fetch the file from S3 URL
	resp, err := http.Get(result.URL)
	if err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, "Failed to fetch binary data from storage")
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fiber.NewError(fiber.StatusInternalServerError, "Storage returned error during binary fetch")
	}

	// Read all into memory (safe for screenshots, usually 1-5MB)
	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, "Failed to read binary data")
	}

	// Set Content-Type
	contentType := resp.Header.Get("Content-Type")
	if contentType == "" {
		// Fallback based on format
		switch result.Format {
		case "png":
			contentType = "image/png"
		case "webp":
			contentType = "image/webp"
		case "pdf":
			contentType = "application/pdf"
		default:
			contentType = "image/jpeg"
		}
	}
	c.Set("Content-Type", contentType)

	// Return as bytes
	return c.Send(bodyBytes)
}

func (h *RenderHandler) getIPAndCountry(c *fiber.Ctx) (string, string) {
	// Priority: CF-Connecting-IP > X-Forwarded-For > RemoteIP
	ip := c.Get("CF-Connecting-IP")
	if ip == "" {
		forwarded := c.Get("X-Forwarded-For")
		if forwarded != "" {
			parts := strings.Split(forwarded, ",")
			ip = strings.TrimSpace(parts[0])
		}
	}
	if ip == "" {
		ip = c.IP()
	}

	country := c.Get("CF-IPCountry", "XX")
	return ip, country
}
