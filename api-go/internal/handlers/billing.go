package handlers

import (
	"log"

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
	plans, err := h.billingService.GetPlans(c.Context())
	if err != nil {
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

// Subscribe handles subscription requests
func (h *BillingHandler) Subscribe(c *fiber.Ctx) error {
	// 1. Get User
	user, ok := c.Locals("user").(*models.User)
	if !ok {
		return fiber.NewError(fiber.StatusUnauthorized, "User authentication required")
	}

	// 2. Parse Request
	var req struct {
		PlanID int `json:"plan_id"`
	}
	if err := c.BodyParser(&req); err != nil {
		return fiber.NewError(fiber.StatusBadRequest, "Invalid request body")
	}

	// 3. Get Plan details to find Stripe Price ID
	var plan models.Plan
	if err := h.db.First(&plan, req.PlanID).Error; err != nil {
		return fiber.NewError(fiber.StatusNotFound, "Plan not found")
	}

	// If free plan, just downgrade/upgrade directly?
	// For simplicity, we assume generic upgrade flow requiring payment for now.
	// Use placeholder check
	if plan.PriceMonthly == 0 {
		return fiber.NewError(fiber.StatusBadRequest, "Free plan does not require payment")
	}

	if plan.StripePriceID == nil {
		return fiber.NewError(fiber.StatusInternalServerError, "Plan configuration error: missing Stripe Price ID")
	}

	// 4. Create Session
	url, err := h.billingService.CreateCheckoutSession(c.Context(), user.ID.String(), *plan.StripePriceID)
	if err != nil {
		log.Printf("CreateCheckoutSession error: %v", err)
		return fiber.NewError(fiber.StatusInternalServerError, "Failed to initiate checkout")
	}

	return c.JSON(fiber.Map{
		"checkout_url": url,
	})
}

// CancelSubscription handles subscription cancellation (Still stub - needs Stripe Portal or logic)
func (h *BillingHandler) CancelSubscription(c *fiber.Ctx) error {
	// Ideally redirect to Customer Portal
	return c.Status(fiber.StatusServiceUnavailable).JSON(fiber.Map{
		"detail": "Cancellation not implemented yet. Please use the Billing Portal.",
		"code":   "NOT_IMPLEMENTED",
	})
}

// ListInvoices returns user's invoices
func (h *BillingHandler) ListInvoices(c *fiber.Ctx) error {
	return c.JSON(fiber.Map{
		"invoices": []interface{}{},
		"total":    0,
	})
}

// StripeWebhook handles Stripe webhook events
func (h *BillingHandler) StripeWebhook(c *fiber.Ctx) error {
	// 1. Read body
	body := c.Body()

	// 2. Read Signature
	signature := c.Get("Stripe-Signature")

	// 3. Construct Event
	event, err := h.billingService.ConstructWebhookEvent(body, signature)
	if err != nil {
		log.Printf("Webhook signature verification failed: %v", err)
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"detail": "Invalid signature"})
	}

	// 4. Handle Event
	if err := h.billingService.HandleWebhookEvent(c.Context(), event); err != nil {
		log.Printf("Webhook handler failed: %v", err)
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"detail": "Callback failed"})
	}

	return c.Status(fiber.StatusOK).JSON(fiber.Map{"received": true})
}
