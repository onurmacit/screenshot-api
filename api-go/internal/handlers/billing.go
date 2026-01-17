package handlers

import (
	"github.com/gofiber/fiber/v2"
	"github.com/onurmacit/screenshot-api/api-go/internal/models"
	"github.com/onurmacit/screenshot-api/api-go/internal/services"
	"gorm.io/gorm"
)

type BillingHandler struct {
	db             *gorm.DB
	billingService *services.BillingService
}

func NewBillingHandler(db *gorm.DB, billingService *services.BillingService) *BillingHandler {
	return &BillingHandler{db: db, billingService: billingService}
}

// ListPlans returns all available subscription plans (Public)
func (h *BillingHandler) ListPlans(c *fiber.Ctx) error {
	var plans []models.Plan
	if err := h.db.Where("is_active = ?", true).Find(&plans).Error; err != nil {
		return fiber.NewError(fiber.StatusInternalServerError, "Failed to fetch plans")
	}

	planResponses := make([]fiber.Map, len(plans))
	for i, plan := range plans {
		planResponses[i] = fiber.Map{
			"id":                      plan.ID,
			"name":                    plan.Name,
			"display_name":            plan.DisplayName,
			"price_monthly":           plan.PriceMonthly,
			"price_yearly":            plan.PriceYearly,
			"requests_per_month":      plan.RequestsPerMonth,
			"max_concurrent_requests": plan.MaxConcurrentRequests,
			"max_timeout_ms":          plan.MaxTimeoutMS,
			"max_file_size_mb":        plan.MaxFileSizeMB,
			"features":                plan.Features,
			"is_active":               plan.IsActive,
		}
	}

	return c.JSON(fiber.Map{"plans": planResponses})
}

// GetPlan returns a specific plan by ID (Public)
func (h *BillingHandler) GetPlan(c *fiber.Ctx) error {
	planID, err := c.ParamsInt("id")
	if err != nil {
		return fiber.NewError(fiber.StatusBadRequest, "Invalid plan ID")
	}

	var plan models.Plan
	if err := h.db.First(&plan, planID).Error; err != nil {
		return fiber.NewError(fiber.StatusNotFound, "Plan not found")
	}

	return c.JSON(fiber.Map{
		"id":                      plan.ID,
		"name":                    plan.Name,
		"display_name":            plan.DisplayName,
		"price_monthly":           plan.PriceMonthly,
		"price_yearly":            plan.PriceYearly,
		"requests_per_month":      plan.RequestsPerMonth,
		"max_concurrent_requests": plan.MaxConcurrentRequests,
		"max_timeout_ms":          plan.MaxTimeoutMS,
		"max_file_size_mb":        plan.MaxFileSizeMB,
		"features":                plan.Features,
		"is_active":               plan.IsActive,
	})
}

// Subscribe handles subscription requests (Stub - Stripe not integrated)
func (h *BillingHandler) Subscribe(c *fiber.Ctx) error {
	// Stripe integration not yet available
	// For now, return a message indicating manual plan management
	return c.Status(fiber.StatusServiceUnavailable).JSON(fiber.Map{
		"error":   true,
		"message": "Stripe payments not yet integrated. Contact admin for plan upgrades.",
		"code":    "STRIPE_NOT_CONFIGURED",
	})
}

// CancelSubscription handles subscription cancellation (Stub)
func (h *BillingHandler) CancelSubscription(c *fiber.Ctx) error {
	return c.Status(fiber.StatusServiceUnavailable).JSON(fiber.Map{
		"error":   true,
		"message": "Stripe payments not yet integrated. Contact admin for plan changes.",
		"code":    "STRIPE_NOT_CONFIGURED",
	})
}

// ListInvoices returns user's invoices (Stub)
func (h *BillingHandler) ListInvoices(c *fiber.Ctx) error {
	// No invoices without Stripe
	return c.JSON(fiber.Map{
		"invoices": []interface{}{},
		"total":    0,
	})
}

// StripeWebhook handles Stripe webhook events (Stub)
func (h *BillingHandler) StripeWebhook(c *fiber.Ctx) error {
	// Stripe not configured
	return c.Status(fiber.StatusServiceUnavailable).JSON(fiber.Map{
		"error":   true,
		"message": "Stripe webhooks not configured",
	})
}
