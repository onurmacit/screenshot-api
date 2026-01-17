package services

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/models"
	rpkg "github.com/onurmacit/screenshot-api/api-go/pkg/redis"
	"github.com/redis/go-redis/v9"
)

type CacheService struct {
	client *redis.Client
	cfg    *config.Config
}

const (
	PrefixAPIKey   = "auth:apikey"
	PrefixUserPlan = "user:plan"
	PrefixRender   = "render"
	PrefixUsage    = "usage:monthly"
)

func NewCacheService(cfg *config.Config) *CacheService {
	return &CacheService{
		client: rpkg.Get(),
		cfg:    cfg,
	}
}

func (s *CacheService) Get(ctx context.Context, key string) (string, error) {
	return s.client.Get(ctx, key).Result()
}

func (s *CacheService) Set(ctx context.Context, key string, value interface{}, ttl time.Duration) error {
	jsonBytes, err := json.Marshal(value)
	if err != nil {
		return err
	}
	return s.client.Set(ctx, key, jsonBytes, ttl).Err()
}

func (s *CacheService) Delete(ctx context.Context, key string) error {
	return s.client.Del(ctx, key).Err()
}

// API Key Caching
func (s *CacheService) GetAPIKey(ctx context.Context, keyHash string) (*models.User, *models.APIKey, error) {
	key := fmt.Sprintf("%s:%s", PrefixAPIKey, keyHash)
	val, err := s.client.Get(ctx, key).Result()
	if err != nil {
		return nil, nil, err
	}

	var data struct {
		User   *models.User   `json:"user"`
		APIKey *models.APIKey `json:"api_key"`
	}

	if err := json.Unmarshal([]byte(val), &data); err != nil {
		return nil, nil, err
	}

	return data.User, data.APIKey, nil
}

func (s *CacheService) SetAPIKey(ctx context.Context, keyHash string, user *models.User, apiKey *models.APIKey) error {
	key := fmt.Sprintf("%s:%s", PrefixAPIKey, keyHash)
	data := map[string]interface{}{
		"user":    user,
		"api_key": apiKey,
	}
	return s.Set(ctx, key, data, time.Duration(s.cfg.APICacheTTL)*time.Second)
}

// Rate Limiting
func (s *CacheService) IncrUsage(ctx context.Context, key string) (int64, error) {
	pipe := s.client.Pipeline()
	incr := pipe.Incr(ctx, key)
	pipe.Expire(ctx, key, 32*24*time.Hour) // Keep for ~1 month
	_, err := pipe.Exec(ctx)
	if err != nil {
		return 0, err
	}
	return incr.Val(), nil
}
