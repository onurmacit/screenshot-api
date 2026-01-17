package handlers

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"

	"github.com/gofiber/fiber/v2"
	"github.com/onurmacit/screenshot-api/api-go/internal/models"
	"gorm.io/gorm"
)

type WebhooksHandler struct {
	db *gorm.DB
}

func NewWebhooksHandler(db *gorm.DB) *WebhooksHandler {
	return &WebhooksHandler{db: db}
}

// generateWebhookSecret creates a secure random secret
func generateWebhookSecret() string {
	bytes := make([]byte, 32)
	rand.Read(bytes)
	return "whsec_" + hex.EncodeToString(bytes)
}

// ListWebhooks returns all webhooks for the authenticated user
func (h *WebhooksHandler) ListWebhooks(c *fiber.Ctx) error {
	user := c.Locals("user").(*models.User)

	var webhooks []models.Webhook
	if err := h.db.Where("user_id = ?", user.ID).Order("created_at DESC").Find(&webhooks).Error; err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, "Failed to fetch webhooks")
	}

	// Don't expose secrets
	result := make([]fiber.Map, len(webhooks))
	for i, wh := range webhooks {
		result[i] = fiber.Map{
			"id":         wh.ID,
			"url":        wh.URL,
			"events":     wh.Events,
			"is_active":  wh.IsActive,
			"created_at": wh.CreatedAt,
		}
	}

	return c.JSON(fiber.Map{"webhooks": result})
}

// CreateWebhook creates a new webhook
func (h *WebhooksHandler) CreateWebhook(c *fiber.Ctx) error {
	user := c.Locals("user").(*models.User)

	var req struct {
		URL      string   `json:"url"`
		Events   []string `json:"events"`
		IsActive bool     `json:"is_active"`
	}
	if err := c.BodyParser(&req); err != nil {
		return fiber.NewError(fiber.StatusBadRequest, "Invalid request body")
	}

	if req.URL == "" {
		return fiber.NewError(fiber.StatusBadRequest, "URL is required")
	}

	secret := generateWebhookSecret()

	webhook := models.Webhook{
		UserID:   user.ID,
		URL:      req.URL,
		Events:   req.Events,
		Secret:   secret,
		IsActive: req.IsActive,
	}

	if err := h.db.Create(&webhook).Error; err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, "Failed to create webhook")
	}

	return c.Status(fiber.StatusCreated).JSON(fiber.Map{
		"id":         webhook.ID,
		"url":        webhook.URL,
		"events":     webhook.Events,
		"is_active":  webhook.IsActive,
		"secret":     secret, // Only shown once!
		"created_at": webhook.CreatedAt,
	})
}

// GetWebhook returns a specific webhook
func (h *WebhooksHandler) GetWebhook(c *fiber.Ctx) error {
	user := c.Locals("user").(*models.User)
	webhookID := c.Params("id")

	var webhook models.Webhook
	if err := h.db.Where("id = ? AND user_id = ?", webhookID, user.ID).First(&webhook).Error; err != nil {
		return fiber.NewError(fiber.StatusNotFound, "Webhook not found")
	}

	return c.JSON(fiber.Map{
		"id":         webhook.ID,
		"url":        webhook.URL,
		"events":     webhook.Events,
		"is_active":  webhook.IsActive,
		"created_at": webhook.CreatedAt,
	})
}

// UpdateWebhook updates a webhook
func (h *WebhooksHandler) UpdateWebhook(c *fiber.Ctx) error {
	user := c.Locals("user").(*models.User)
	webhookID := c.Params("id")

	var webhook models.Webhook
	if err := h.db.Where("id = ? AND user_id = ?", webhookID, user.ID).First(&webhook).Error; err != nil {
		return fiber.NewError(fiber.StatusNotFound, "Webhook not found")
	}

	var req struct {
		URL      *string   `json:"url"`
		Events   *[]string `json:"events"`
		IsActive *bool     `json:"is_active"`
	}
	if err := c.BodyParser(&req); err != nil {
		return fiber.NewError(fiber.StatusBadRequest, "Invalid request body")
	}

	if req.URL != nil {
		webhook.URL = *req.URL
	}
	if req.Events != nil {
		webhook.Events = *req.Events
	}
	if req.IsActive != nil {
		webhook.IsActive = *req.IsActive
	}

	if err := h.db.Save(&webhook).Error; err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, "Failed to update webhook")
	}

	return c.JSON(fiber.Map{
		"id":         webhook.ID,
		"url":        webhook.URL,
		"events":     webhook.Events,
		"is_active":  webhook.IsActive,
		"created_at": webhook.CreatedAt,
	})
}

// DeleteWebhook deletes a webhook
func (h *WebhooksHandler) DeleteWebhook(c *fiber.Ctx) error {
	user := c.Locals("user").(*models.User)
	webhookID := c.Params("id")

	result := h.db.Where("id = ? AND user_id = ?", webhookID, user.ID).Delete(&models.Webhook{})
	if result.RowsAffected == 0 {
		return fiber.NewError(fiber.StatusNotFound, "Webhook not found")
	}

	return c.SendStatus(fiber.StatusNoContent)
}

// RotateSecret generates a new secret for a webhook
func (h *WebhooksHandler) RotateSecret(c *fiber.Ctx) error {
	user := c.Locals("user").(*models.User)
	webhookID := c.Params("id")

	var webhook models.Webhook
	if err := h.db.Where("id = ? AND user_id = ?", webhookID, user.ID).First(&webhook).Error; err != nil {
		return fiber.NewError(fiber.StatusNotFound, "Webhook not found")
	}

	newSecret := generateWebhookSecret()
	webhook.Secret = newSecret

	if err := h.db.Save(&webhook).Error; err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, "Failed to rotate secret")
	}

	return c.JSON(fiber.Map{
		"id":     webhook.ID,
		"secret": newSecret, // Only shown once!
	})
}

// VerifySignature verifies a webhook signature (Public utility endpoint)
func (h *WebhooksHandler) VerifySignature(c *fiber.Ctx) error {
	var req struct {
		Payload   string `json:"payload"`
		Signature string `json:"signature"`
		Secret    string `json:"secret"`
	}
	if err := c.BodyParser(&req); err != nil {
		return fiber.NewError(fiber.StatusBadRequest, "Invalid request body")
	}

	mac := hmac.New(sha256.New, []byte(req.Secret))
	mac.Write([]byte(req.Payload))
	expectedSig := "sha256=" + hex.EncodeToString(mac.Sum(nil))

	valid := hmac.Equal([]byte(expectedSig), []byte(req.Signature))

	return c.JSON(fiber.Map{"valid": valid})
}

// ListEvents returns available webhook events (Public)
func (h *WebhooksHandler) ListEvents(c *fiber.Ctx) error {
	events := []fiber.Map{
		{"name": "render.completed", "description": "Fired when a render job completes successfully"},
		{"name": "render.failed", "description": "Fired when a render job fails"},
		{"name": "usage.limit.reached", "description": "Fired when monthly usage limit is reached"},
		{"name": "usage.limit.warning", "description": "Fired when usage reaches 80% of limit"},
	}

	return c.JSON(fiber.Map{"events": events})
}
