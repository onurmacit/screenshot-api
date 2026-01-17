package services

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/dto"
	"github.com/onurmacit/screenshot-api/api-go/internal/models"
	"github.com/onurmacit/screenshot-api/api-go/internal/utils"

	"gorm.io/gorm"
)

type AuthService struct {
	db    *gorm.DB
	cache *CacheService
	cfg   *config.Config
}

func NewAuthService(db *gorm.DB, cfg *config.Config) *AuthService {
	return &AuthService{
		db:    db,
		cache: NewCacheService(cfg),
		cfg:   cfg,
	}
}

// ValidateAPIKey validates an API key and returns the user and key
func (s *AuthService) ValidateAPIKey(ctx context.Context, apiKey string) (*models.User, *models.APIKey, error) {
	// 1. Hash the key (SHA256)
	hash := sha256.New()
	hash.Write([]byte(apiKey))
	keyHash := hex.EncodeToString(hash.Sum(nil))

	// 2. Check cache first
	user, key, err := s.cache.GetAPIKey(ctx, keyHash)
	if err == nil && user != nil && key != nil {
		return user, key, nil
	}

	// 3. Query database
	var apiKeyModel models.APIKey
	if err := s.db.Preload("User").Preload("User.Plan").Where("key_hash = ?", keyHash).First(&apiKeyModel).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, nil, utils.ErrInvalidAPIKey
		}
		return nil, nil, err
	}

	// 4. Validate
	if !apiKeyModel.IsActive {
		return nil, nil, utils.ErrInvalidAPIKey
	}

	if apiKeyModel.IsExpired() {
		return nil, nil, utils.ErrAPIKeyExpired
	}

	// 5. Update last used (async)
	go s.updateLastUsed(apiKeyModel.ID)

	// 6. Cache result
	// Note: We're not handling cache errors here to fail open
	_ = s.cache.SetAPIKey(ctx, keyHash, &apiKeyModel.User, &apiKeyModel)

	return &apiKeyModel.User, &apiKeyModel, nil
}

func (s *AuthService) CreateAPIKey(ctx context.Context, userID uuid.UUID, name string, scopes []string) (*dto.APIKeyCreateResponse, error) {
	// 1. Generate Raw Key
	randomBytes := make([]byte, 24)
	if _, err := rand.Read(randomBytes); err != nil {
		return nil, err
	}
	randomStr := hex.EncodeToString(randomBytes)
	rawKey := fmt.Sprintf("sk_live_%s", randomStr)

	// 2. Hash Key
	hash := sha256.New()
	hash.Write([]byte(rawKey))
	keyHash := hex.EncodeToString(hash.Sum(nil))

	// 3. Create Record
	apiKey := &models.APIKey{
		UserID:    userID,
		Name:      &name,
		KeyHash:   keyHash,
		KeyPrefix: rawKey[:12],
		Scopes:    scopes,
		SecretKey: "legacy",
	}

	if err := s.db.Create(apiKey).Error; err != nil {
		return nil, err
	}

	// 4. Return Response (with raw key)
	return &dto.APIKeyCreateResponse{
		ID:        apiKey.ID.String(),
		AccessKey: rawKey,
		SecretKey: "",
	}, nil
}

func (s *AuthService) ListAPIKeys(ctx context.Context, userID uuid.UUID) ([]dto.APIKeyResponse, error) {
	var keys []models.APIKey
	if err := s.db.Where("user_id = ? AND is_active = ?", userID, true).Order("created_at desc").Find(&keys).Error; err != nil {
		return nil, err
	}

	var response []dto.APIKeyResponse
	for _, k := range keys {
		name := ""
		if k.Name != nil {
			name = *k.Name
		}

		response = append(response, dto.APIKeyResponse{
			ID:        k.ID.String(),
			Name:      name,
			KeyPrefix: k.KeyPrefix,
			Scopes:    k.Scopes,
			CreatedAt: k.CreatedAt.Format(time.RFC3339),
		})
	}
	return response, nil
}

func (s *AuthService) DeleteAPIKey(ctx context.Context, userID uuid.UUID, keyID string) error {
	// Verify ownership
	var key models.APIKey
	if err := s.db.Where("id = ? AND user_id = ?", keyID, userID).First(&key).Error; err != nil {
		return utils.ErrNotFound
	}

	key.IsActive = false
	if err := s.db.Save(&key).Error; err != nil {
		return err
	}

	// Invalidate Cache using constants from cache_service.go
	_ = s.cache.Delete(ctx, fmt.Sprintf("%s:%s", PrefixAPIKey, key.KeyHash))

	return nil
}

func (s *AuthService) updateLastUsed(keyID interface{}) {
	s.db.Model(&models.APIKey{}).Where("id = ?", keyID).Update("last_used_at", gorm.Expr("NOW()"))
}

func (s *AuthService) GetUserByID(ctx context.Context, userID string) (*models.User, error) {
	// 1. Try Cache
	// TODO: Add User Cache logic (PrefixUser)

	// 2. DB
	var user models.User
	if err := s.db.Preload("Plan").Where("id = ?", userID).First(&user).Error; err != nil {
		return nil, err
	}

	return &user, nil
}

func (s *AuthService) GetOrCreateDemoUser(ctx context.Context) (*models.User, error) {
	email := "demo@screenshotbeam.com"
	var user models.User

	err := s.db.Where("email = ?", email).First(&user).Error
	if err == nil {
		return &user, nil
	}

	if errors.Is(err, gorm.ErrRecordNotFound) {
		// Create Demo User
		name := "Demo User"
		user = models.User{
			Email:    email,
			FullName: &name,
			IsActive: true,
			// No Plan -> Default Plan (Free)
		}
		if err := s.db.Create(&user).Error; err != nil {
			return nil, err
		}
		return &user, nil
	}

	return nil, err
}
