package services

import (
	"context"
	"fmt"
	"strconv"
	"time"

	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/models"
	"github.com/onurmacit/screenshot-api/api-go/internal/utils"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

type UsageService struct {
	cache *CacheService
	cfg   *config.Config
	db    *gorm.DB
}

func NewUsageService(cache *CacheService, cfg *config.Config, db *gorm.DB) *UsageService {
	return &UsageService{
		cache: cache,
		cfg:   cfg,
		db:    db,
	}
}

// CheckAndIncrement checks if user has remaining quota and increments usage
func (s *UsageService) CheckAndIncrement(ctx context.Context, user *models.User) error {
	// 1. Get current month key
	now := time.Now()
	key := fmt.Sprintf("usage:%s:%s", user.ID, now.Format("2006-01"))

	// 2. Increment in Redis
	count, err := s.cache.IncrUsage(ctx, key)
	if err != nil {
		return nil // Fail open
	}

	// 3. Sync to DB (Async)
	go func() {
		// Calculate first day of month
		firstOfMonth := time.Date(now.Year(), now.Month(), 1, 0, 0, 0, 0, time.UTC)

		// Upsert UsageRecord
		var record models.UsageRecord // Keep var for lint happiness if using &record later, or define properly
		// Actually, best way:
		record = models.UsageRecord{
			UserID: user.ID,
			Month:  firstOfMonth,
			Count:  int(count),
		}

		s.db.Clauses(clause.OnConflict{
			Columns:   []clause.Column{{Name: "user_id"}, {Name: "month"}},
			DoUpdates: clause.Assignments(map[string]interface{}{"count": int(count)}),
		}).Create(&record)
	}()

	// 4. Check Plan Limit
	limit := user.Plan.RequestsPerMonth

	if int(count) > limit {
		return utils.NewError(429, fmt.Sprintf("Monthly limit exceeded (%d/%d)", count, limit))
	}

	return nil
}

// GetCurrentUsage returns current month usage
func (s *UsageService) GetCurrentUsage(ctx context.Context, userID string) (int, error) {
	now := time.Now()
	key := fmt.Sprintf("usage:%s:%s", userID, now.Format("2006-01"))

	val, err := s.cache.Get(ctx, key)
	if err != nil {
		return 0, nil
	}

	return strconv.Atoi(val)
}

// GetHistory returns usages from DB
func (s *UsageService) GetHistory(ctx context.Context, userID string) ([]models.UsageRecord, error) {
	var records []models.UsageRecord
	err := s.db.Where("user_id = ?", userID).Order("month desc").Find(&records).Error
	return records, err
}
