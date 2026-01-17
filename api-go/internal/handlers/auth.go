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

// === Authentication ===

func (h *AuthHandler) Register(c *fiber.Ctx) error {
	var req dto.RegisterRequest
	if err := c.BodyParser(&req); err != nil {
		return utils.ErrBadRequest
	}
	if req.Email == "" || req.Password == "" {
		return fiber.NewError(fiber.StatusBadRequest, "Email and password required")
	}

	response, err := h.authService.Register(req, c.IP(), c.Get("User-Agent"))
	if err != nil {
		return h.handleError(c, err)
	}

	return c.Status(fiber.StatusCreated).JSON(response)
}

func (h *AuthHandler) Login(c *fiber.Ctx) error {
	var req dto.LoginRequest
	if err := c.BodyParser(&req); err != nil {
		return utils.ErrBadRequest
	}

	response, err := h.authService.Login(req, c.IP(), c.Get("User-Agent"))
	if err != nil {
		return h.handleError(c, err)
	}

	return c.JSON(response)
}

func (h *AuthHandler) RefreshToken(c *fiber.Ctx) error {
	var req dto.RefreshTokenRequest
	if err := c.BodyParser(&req); err != nil {
		return utils.ErrBadRequest
	}

	response, err := h.authService.RefreshToken(c.Context(), req.RefreshToken, c.IP(), c.Get("User-Agent"))
	if err != nil {
		return h.handleError(c, err)
	}

	return c.JSON(response)
}

func (h *AuthHandler) Logout(c *fiber.Ctx) error {
	var req dto.RefreshTokenRequest
	if err := c.BodyParser(&req); err != nil {
		return utils.ErrBadRequest
	}

	if err := h.authService.Logout(c.Context(), req.RefreshToken); err != nil {
		return h.handleError(c, err)
	}

	return c.SendStatus(fiber.StatusNoContent)
}

func (h *AuthHandler) SocialLogin(c *fiber.Ctx) error {
	var req dto.SocialLoginRequest
	if err := c.BodyParser(&req); err != nil {
		return utils.ErrBadRequest
	}

	if req.Provider == "" || req.Token == "" {
		return fiber.NewError(fiber.StatusBadRequest, "Provider and token required")
	}

	response, err := h.authService.SocialLogin(req, c.IP(), c.Get("User-Agent"))
	if err != nil {
		return h.handleError(c, err)
	}

	return c.JSON(response)
}

func (h *AuthHandler) GetMe(c *fiber.Ctx) error {
	user := c.Locals("user").(*models.User)
	// Return user profile (sanitize hash)
	user.PasswordHash = nil
	return c.JSON(user)
}

// === API Key Management ===

func (h *AuthHandler) CreateAPIKey(c *fiber.Ctx) error {
	var req dto.APIKeyCreateRequest
	if err := c.BodyParser(&req); err != nil {
		return utils.ErrBadRequest
	}

	user := c.Locals("user").(*models.User)

	response, err := h.authService.CreateAPIKey(c.Context(), req, user.ID)
	if err != nil {
		return h.handleError(c, err)
	}

	return c.Status(fiber.StatusCreated).JSON(response)
}

func (h *AuthHandler) ListAPIKeys(c *fiber.Ctx) error {
	user := c.Locals("user").(*models.User)

	response, err := h.authService.ListAPIKeys(c.Context(), user.ID)
	if err != nil {
		return h.handleError(c, err)
	}

	return c.JSON(response)
}

func (h *AuthHandler) DeleteAPIKey(c *fiber.Ctx) error {
	keyID := c.Params("id")
	user := c.Locals("user").(*models.User)

	if err := h.authService.DeleteAPIKey(c.Context(), user.ID, keyID); err != nil {
		return h.handleError(c, err)
	}

	return c.SendStatus(fiber.StatusNoContent)
}

func (h *AuthHandler) ToggleEnforceSigning(c *fiber.Ctx) error {
	keyID := c.Params("id")
	user := c.Locals("user").(*models.User)

	var req dto.APIKeyEnforceSigningRequest
	if err := c.BodyParser(&req); err != nil {
		return utils.ErrBadRequest
	}

	response, err := h.authService.ToggleEnforceSigning(c.Context(), user.ID, keyID, req.Enforce)
	if err != nil {
		return h.handleError(c, err)
	}

	return c.JSON(response)
}

func (h *AuthHandler) handleError(c *fiber.Ctx, err error) error {
	if appErr, ok := err.(*utils.AppError); ok {
		return c.Status(appErr.Code).JSON(fiber.Map{"detail": appErr.Message})
	}
	return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"detail": err.Error()})
}
