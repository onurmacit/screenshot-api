package services

import (
	"context"
	"encoding/json"
	"errors"
	"log"

	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/models"
	"github.com/onurmacit/screenshot-api/api-go/internal/utils"
	"github.com/stripe/stripe-go/v74"
	"github.com/stripe/stripe-go/v74/checkout/session"
	"github.com/stripe/stripe-go/v74/webhook"
	"gorm.io/gorm"
)

type BillingService struct {
	db  *gorm.DB
	cfg *config.Config
}

func NewBillingService(db *gorm.DB, cfg *config.Config) *BillingService {
	// Initialize Stripe
	stripe.Key = cfg.StripeSecretKey

	return &BillingService{
		db:  db,
		cfg: cfg,
	}
}

// SeedPlans populates the database with default plans if they don't exist
func (s *BillingService) SeedPlans() error {
	plans := []models.Plan{
		{
			ID:                    1,
			Name:                  "free",
			DisplayName:           "Free Plan",
			PriceMonthly:          0,
			RequestsPerMonth:      100,
			MaxConcurrentRequests: 1,
			MaxTimeoutMS:          10000, // 10s
			MaxFileSizeMB:         2,
			IsActive:              true,
		},
		{
			ID:                    2,
			Name:                  "hobby",
			DisplayName:           "Hobby",
			PriceMonthly:          15.00,
			RequestsPerMonth:      5000,
			MaxConcurrentRequests: 5,
			MaxTimeoutMS:          30000, // 30s
			MaxFileSizeMB:         5,
			IsActive:              true,
			StripePriceID:         strPtr("price_HobbyMonthly"), // Placeholder
		},
		{
			ID:                    3,
			Name:                  "startup",
			DisplayName:           "Startup",
			PriceMonthly:          50.00,
			RequestsPerMonth:      20000,
			MaxConcurrentRequests: 20,
			MaxTimeoutMS:          60000, // 60s
			MaxFileSizeMB:         10,
			IsActive:              true,
			StripePriceID:         strPtr("price_StartupMonthly"), // Placeholder
		},
		{
			ID:                    4,
			Name:                  "business",
			DisplayName:           "Business",
			PriceMonthly:          120.00,
			RequestsPerMonth:      100000,
			MaxConcurrentRequests: 50,
			MaxTimeoutMS:          60000, // 60s
			MaxFileSizeMB:         20,
			IsActive:              true,
			StripePriceID:         strPtr("price_BusinessMonthly"), // Placeholder
		},
	}

	for _, p := range plans {
		var count int64
		// Check by ID (force ID to keep consistency)
		s.db.Model(&models.Plan{}).Where("id = ?", p.ID).Count(&count)
		if count == 0 {
			if err := s.db.Create(&p).Error; err != nil {
				log.Printf("Failed to seed plan %s: %v", p.Name, err)
				return err
			}
			log.Printf("Seeded plan: %s", p.Name)
		} else {
			// Update Stripe Price ID if missing and we have one in seed
			if p.StripePriceID != nil {
				s.db.Model(&models.Plan{}).Where("id = ? AND stripe_price_id IS NULL", p.ID).
					Update("stripe_price_id", *p.StripePriceID)
			}
		}
	}
	return nil
}

// CreateCheckoutSession creates a Stripe Checkout Session for subscription
func (s *BillingService) CreateCheckoutSession(ctx context.Context, userID string, priceID string) (string, error) {
	// 1. Get User
	var user models.User
	if err := s.db.First(&user, "id = ?", userID).Error; err != nil {
		return "", err
	}

	// 2. Prepare params
	params := &stripe.CheckoutSessionParams{
		Mode: stripe.String(string(stripe.CheckoutSessionModeSubscription)),
		PaymentMethodTypes: stripe.StringSlice([]string{
			"card",
		}),
		LineItems: []*stripe.CheckoutSessionLineItemParams{
			{
				Price:    stripe.String(priceID),
				Quantity: stripe.Int64(1),
			},
		},
		SuccessURL:        stripe.String(s.cfg.GoRendererURL + "/dashboard?success=true&session_id={CHECKOUT_SESSION_ID}"), // Adjust success URL
		CancelURL:         stripe.String(s.cfg.GoRendererURL + "/dashboard?canceled=true"),
		ClientReferenceID: stripe.String(userID),
	}

	// 3. Add Customer ID if exists
	if user.StripeCustomerID != nil {
		params.Customer = stripe.String(*user.StripeCustomerID)
	} else {
		params.CustomerEmail = stripe.String(user.Email)
	}

	// 4. Create Session
	sess, err := session.New(params)
	if err != nil {
		log.Printf("Stripe session creation failed: %v", err)
		return "", err
	}

	return sess.URL, nil
}

// ConstructWebhookEvent verifies the webhook signature
func (s *BillingService) ConstructWebhookEvent(payload []byte, signature string) (stripe.Event, error) {
	return webhook.ConstructEvent(payload, signature, s.cfg.StripeWebhookSecret)
}

// HandleWebhookEvent processes the Stripe event
func (s *BillingService) HandleWebhookEvent(ctx context.Context, event stripe.Event) error {
	switch event.Type {
	case "checkout.session.completed":
		var session stripe.CheckoutSession
		err := json.Unmarshal(event.Data.Raw, &session)
		if err != nil {
			return err
		}
		return s.handleCheckoutSessionCompleted(ctx, &session)
	}
	return nil
}

func (s *BillingService) handleCheckoutSessionCompleted(ctx context.Context, session *stripe.CheckoutSession) error {
	userID := session.ClientReferenceID
	customerID := session.Customer.ID

	// If subscription mode, get subscription details to find the plan
	// Note: We need to map Stripe Price ID to our Plan ID.
	// For simplicity, we query our Plan table by StripePriceID.

	// But Checkout Session Line Items might require expansion to get Price ID.
	// Typically, we trust the ClientReferenceID to find the user.
	// And we need to know WHICH plan they bought.

	// Retrieve line items to get the Price ID
	// (Skipping for brevity/complexity, assuming we can get it or update via subscription webhook)

	// For now, let's just update the user's StripeCustomerID
	if userID != "" {
		updates := map[string]interface{}{
			"stripe_customer_id": customerID,
		}

		// Ideally we update the plan here too, but we need to fetch the Subscription to know the Price ID
		// Or assume if we implemented metadata in checkout session.

		if err := s.db.Model(&models.User{}).Where("id = ?", userID).Updates(updates).Error; err != nil {
			log.Printf("Failed to update user %s stripe info: %v", userID, err)
			return err
		}
	}

	return nil
}

// GetUserInvoices returns invoices for the user (stubbed or real if we implemented ListInvoices)
func (s *BillingService) GetUserInvoices(ctx context.Context, userID string) ([]interface{}, error) {
	// Not implemented yet
	return []interface{}{}, nil
}

// Helper
func strPtr(s string) *string {
	return &s
}

// SetUserPlan manually updates a user's plan (Admin feature)
func (s *BillingService) SetUserPlan(ctx context.Context, userID string, planID int) error {
	var plan models.Plan
	if err := s.db.First(&plan, planID).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return &utils.AppError{Code: 404, Message: "Plan not found"}
		}
		return err
	}

	if err := s.db.Model(&models.User{}).Where("id = ?", userID).Update("plan_id", planID).Error; err != nil {
		return err
	}
	return nil
}

// GetPlans returns all active plans
func (s *BillingService) GetPlans(ctx context.Context) ([]models.Plan, error) {
	var plans []models.Plan
	if err := s.db.Where("is_active = ?", true).Order("price_monthly asc").Find(&plans).Error; err != nil {
		return nil, err
	}
	return plans, nil
}
