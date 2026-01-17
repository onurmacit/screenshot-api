package services

import (
	"context"
	"errors"
	"log"

	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/models"
	"github.com/onurmacit/screenshot-api/api-go/internal/utils"
	"gorm.io/gorm"
)

type BillingService struct {
	db  *gorm.DB
	cfg *config.Config
}

func NewBillingService(db *gorm.DB, cfg *config.Config) *BillingService {
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
			PriceMonthly:          1500, // $15.00
			RequestsPerMonth:      5000,
			MaxConcurrentRequests: 5,
			MaxTimeoutMS:          30000, // 30s
			MaxFileSizeMB:         5,
			IsActive:              true,
		},
		{
			ID:                    3,
			Name:                  "startup",
			DisplayName:           "Startup",
			PriceMonthly:          5000, // $50.00
			RequestsPerMonth:      20000,
			MaxConcurrentRequests: 20,
			MaxTimeoutMS:          60000, // 60s
			MaxFileSizeMB:         10,
			IsActive:              true,
		},
		{
			ID:                    4,
			Name:                  "business",
			DisplayName:           "Business",
			PriceMonthly:          12000, // $120.00
			RequestsPerMonth:      100000,
			MaxConcurrentRequests: 50,
			MaxTimeoutMS:          60000, // 60s
			MaxFileSizeMB:         20,
			IsActive:              true,
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
		}
	}
	return nil
}

// SetUserPlan manually updates a user's plan (Admin feature)
func (s *BillingService) SetUserPlan(ctx context.Context, userID string, planID int) error {
	// 1. Validate Plan
	var plan models.Plan
	if err := s.db.First(&plan, planID).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return &utils.AppError{Code: 404, Message: "Plan not found"}
		}
		return err
	}

	// 2. Update User
	// Note: In real billing (Stripe), we would update Stripe Subscription here.
	// Since we are "Stripe-Free", we just update the DB directly.
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
