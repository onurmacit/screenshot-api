package handlers

import (
	"github.com/gofiber/fiber/v2"
	"github.com/onurmacit/screenshot-api/api-go/internal/dto"
	"github.com/onurmacit/screenshot-api/api-go/internal/models"
	"github.com/onurmacit/screenshot-api/api-go/internal/services"
	"github.com/onurmacit/screenshot-api/api-go/internal/utils"
)

type AuthHandler struct {
	authService *services.AuthService
}

func NewAuthHandler(authService *services.AuthService) *AuthHandler {
	return &AuthHandler{
		authService: authService,
	}
}

// Implement JWT Login/Register/Refresh later if needed
// For now, focus on API Keys management for Dashboard

func (h *AuthHandler) CreateAPIKey(c *fiber.Ctx) error {
	var req dto.APIKeyCreateRequest
	if err := c.BodyParser(&req); err != nil {
		return fiber.NewError(fiber.StatusBadRequest, "Invalid JSON body")
	}

	user := c.Locals("user").(*models.User)

	response, err := h.authService.CreateAPIKey(c.Context(), user.ID, req.Name, req.Scopes)
	if err != nil {
		return utils.ErrInternal
	}

	return c.Status(fiber.StatusCreated).JSON(response)
}

func (h *AuthHandler) ListAPIKeys(c *fiber.Ctx) error {
	user := c.Locals("user").(*models.User)

	response, err := h.authService.ListAPIKeys(c.Context(), user.ID)
	if err != nil {
		return utils.ErrInternal
	}

	return c.JSON(response)
}

func (h *AuthHandler) DeleteAPIKey(c *fiber.Ctx) error {
	keyID := c.Params("id")
	user := c.Locals("user").(*models.User)

	if err := h.authService.DeleteAPIKey(c.Context(), user.ID, keyID); err != nil {
		return err // Will be handled by error handler
	}

	return c.SendStatus(fiber.StatusNoContent)
}
