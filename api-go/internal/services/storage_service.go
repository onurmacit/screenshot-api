package services

import (
	"context"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/dto"
	"github.com/onurmacit/screenshot-api/api-go/pkg/s3"
)

type StorageService struct {
	client *s3.Client
	cfg    *config.Config
}

func NewStorageService(cfg *config.Config) (*StorageService, error) {
	client, err := s3.Connect(
		context.Background(),
		cfg.AWSS3Region,
		cfg.AWSS3Endpoint,
		cfg.AWSAccessKeyID,
		cfg.AWSSecretAccessKey,
		cfg.AWSS3Bucket,
	)
	if err != nil {
		return nil, err
	}

	return &StorageService{
		client: client,
		cfg:    cfg,
	}, nil
}

func (s *StorageService) UploadRender(ctx context.Context, data []byte, format string, userID string) (*dto.RenderJobResponse, error) {
	// Generate Key
	year, month, day := time.Now().Date()
	fileName := fmt.Sprintf("%s.%s", uuid.New().String(), format)
	key := fmt.Sprintf("renders/%s/%d/%02d/%02d/%s", userID, year, month, day, fileName)

	// Format content type
	contentType := "image/jpeg"
	if format == "png" {
		contentType = "image/png"
	} else if format == "webp" {
		contentType = "image/webp"
	} else if format == "pdf" {
		contentType = "application/pdf"
	}

	// Upload
	url, err := s.client.Upload(ctx, key, data, contentType, map[string]string{
		"user-id": userID,
	})
	if err != nil {
		return nil, err
	}

	return &dto.RenderJobResponse{
		URL:      url,
		FileSize: len(data),
		// Other fields filled later
	}, nil
}

func (s *StorageService) Delete(ctx context.Context, key string) error {
	return s.client.Delete(ctx, key)
}
