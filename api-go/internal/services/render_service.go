package services

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/url"
	"time"

	"github.com/google/uuid"
	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/dto"
	"github.com/onurmacit/screenshot-api/api-go/internal/models"
	repo "github.com/onurmacit/screenshot-api/api-go/internal/repository"
	"github.com/onurmacit/screenshot-api/api-go/internal/utils"
	"gorm.io/gorm"
)

type RenderService struct {
	renderer *RendererClient
	storage  *StorageService
	cache    *CacheService
	usage    *UsageService
	jobRepo  *repo.RenderJobRepository
	queue    *JobQueue
	cfg      *config.Config
	db       *gorm.DB
}

func NewRenderService(renderer *RendererClient, storage *StorageService, cache *CacheService, usage *UsageService, jobRepo *repo.RenderJobRepository, cfg *config.Config, db *gorm.DB) *RenderService {
	return &RenderService{
		renderer: renderer,
		storage:  storage,
		cache:    cache,
		usage:    usage,
		jobRepo:  jobRepo,
		cfg:      cfg,
		db:       db,
	}
}

// SetQueue sets the job queue for async processing
func (s *RenderService) SetQueue(queue *JobQueue) {
	s.queue = queue
}

func (s *RenderService) Config() *config.Config {
	return s.cfg
}

// ... CaptureScreenshot (existing) ...

func (s *RenderService) CreateRenderJob(ctx context.Context, req dto.RenderRequest, user *models.User) (*dto.RenderJobResponse, error) {
	// 1. Check Usage
	if err := s.usage.CheckAndIncrement(ctx, user); err != nil {
		return nil, err
	}

	// 2. Create Job Record
	optionsJSON := map[string]any{
		"width":  req.Width,
		"height": req.Height,
		"format": req.Format,
	}

	job := &models.RenderJob{
		ID:      uuid.New(),
		UserID:  user.ID,
		Type:    "screenshot",
		Status:  "pending",
		URL:     req.URL,
		Format:  req.Format,
		Width:   req.Width,
		Height:  req.Height,
		Options: optionsJSON,
	}

	if err := s.jobRepo.Create(job); err != nil {
		return nil, err
	}

	// 3. Enqueue to Redis (if queue is available)
	if s.queue != nil {
		reqJSON, _ := json.Marshal(req)
		payload := &JobPayload{
			JobID:      job.ID.String(),
			Type:       "screenshot",
			UserID:     user.ID.String(),
			Request:    reqJSON,
			Priority:   job.Priority,
			CreatedAt:  time.Now(),
			RetryCount: 0,
		}
		if err := s.queue.Enqueue(ctx, payload); err != nil {
			// Log error but don't fail - fallback to goroutine
			go s.processJob(job.ID.String(), req, user)
		}
	} else {
		// Fallback: use goroutine (legacy mode)
		go s.processJob(job.ID.String(), req, user)
	}

	// 4. Return Response
	return &dto.RenderJobResponse{
		JobID:     job.ID.String(),
		Type:      "screenshot",
		Status:    "pending",
		URL:       req.URL,
		CreatedAt: time.Now(),
	}, nil
}

// CaptureScreenshotAsync creates an async job and returns immediately
// This is called when ?async=true query param is set
func (s *RenderService) CaptureScreenshotAsync(ctx context.Context, req dto.RenderRequest, user *models.User) (*dto.RenderJobResponse, error) {
	return s.CreateRenderJob(ctx, req, user)
}

func (s *RenderService) processJob(jobID string, req dto.RenderRequest, user *models.User) {
	// Create background context with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	// Get job (refresh)
	job, err := s.jobRepo.FindByID(jobID)
	if err != nil {
		// Log error
		return
	}

	// Update Status: Processing
	job.Status = "processing"
	start := time.Now()
	job.StartedAt = &start
	_ = s.jobRepo.Update(job)

	// Render
	imageBytes, metadata, err := s.renderer.Capture(ctx, req)
	if err != nil {
		errMsg := err.Error()
		job.Status = "failed"
		job.ErrorMessage = &errMsg
		_ = s.jobRepo.Update(job)
		return
	}

	// Upload
	uploadResult, err := s.storage.UploadRender(ctx, imageBytes, req.Format, user.ID.String())
	if err != nil {
		errMsg := err.Error()
		job.Status = "failed"
		job.ErrorMessage = &errMsg
		_ = s.jobRepo.Update(job)
		return
	}

	// Update Status: Completed
	completed := time.Now()
	processingMs := int(completed.Sub(start).Milliseconds())
	size := len(imageBytes)

	job.Status = "completed"
	job.CompletedAt = &completed
	job.S3URL = &uploadResult.URL
	job.ProcessingTimeMs = &processingMs
	job.FileSizeBytes = &size
	job.Result = map[string]any{
		"url":    uploadResult.URL,
		"width":  metadata.Width,
		"height": metadata.Height,
	}

	_ = s.jobRepo.Update(job)

	// Cache result (optional for jobs?)

	// TODO: Send Webhook
}

func (s *RenderService) CreatePDF(ctx context.Context, req dto.PDFRequest, user *models.User) (*dto.PDFResponse, error) {
	// 1. Check Usage
	if err := s.usage.CheckAndIncrement(ctx, user); err != nil {
		return nil, err
	}

	// 2. Generate Cache Key (Simplified for MVP)
	keyData := fmt.Sprintf("v1:pdf:%s:%s:%t:%t:%f:%d", req.URL, req.Format, req.Landscape, req.PrintBackground, req.Scale, req.Delay)

	h := sha256.New()
	h.Write([]byte(keyData))
	cacheKey := fmt.Sprintf("pdf:%s", hex.EncodeToString(h.Sum(nil)))

	// 3. Check Cache
	cached, err := s.cache.Get(ctx, cacheKey)
	if err == nil && cached != "" {
		var response dto.PDFResponse
		if err := json.Unmarshal([]byte(cached), &response); err == nil {
			return &response, nil
		}
	}

	// 4. Render PDF
	pdfBytes, metadata, err := s.renderer.GeneratePDF(ctx, req)
	if err != nil {
		if ctx.Err() == context.DeadlineExceeded {
			return nil, &utils.AppError{Code: 504, Message: "Render timeout"}
		}
		return nil, &utils.AppError{Code: 502, Message: fmt.Sprintf("PDF generation failed: %v", err)}
	}

	// 5. Upload to S3
	uploadResult, err := s.storage.UploadRender(ctx, pdfBytes, "pdf", user.ID.String())
	if err != nil {
		return nil, err
	}

	// 6. Create Response
	response := dto.PDFResponse{
		URL:              uploadResult.URL,
		PageCount:        metadata.PageCount,
		ProcessingTimeMs: metadata.ProcessingTimeMs,
		FileSize:         len(pdfBytes),
	}

	// 7. Cache Result
	if err := s.cache.Set(ctx, cacheKey, response, time.Duration(s.cfg.RenderCacheTTL)*time.Second); err != nil {
		// Log error but continue
	}

	return &response, nil
}

func (s *RenderService) CaptureScreenshot(ctx context.Context, req dto.RenderRequest, user *models.User) (*dto.ScreenshotResponse, error) {
	// 1. Check Usage Limit
	if err := s.usage.CheckAndIncrement(ctx, user); err != nil {
		return nil, err
	}

	// 2. Generate Cache Key
	cacheKey := s.generateCacheKey(req)

	// 2. Check Cache
	if cachedStr, err := s.cache.Get(ctx, cacheKey); err == nil {
		var response dto.ScreenshotResponse
		if err := json.Unmarshal([]byte(cachedStr), &response); err == nil {
			response.Status = "completed"
			// Important for frontend: returned cached: true header? handled by middleware/controller
			return &response, nil
		}
	}

	// 3. Render
	imageBytes, metadata, err := s.renderer.Capture(ctx, req)
	if err != nil {
		if ctx.Err() == context.DeadlineExceeded {
			return nil, &utils.AppError{Code: 504, Message: "Render timeout"}
		}
		return nil, &utils.AppError{Code: 502, Message: fmt.Sprintf("Screenshot capture failed: %v", err)}
	}

	// 4. Upload to S3
	uploadResult, err := s.storage.UploadRender(ctx, imageBytes, req.Format, user.ID.String())
	if err != nil {
		return nil, &utils.AppError{Code: 500, Message: fmt.Sprintf("Storage upload failed: %v", err)}
	}

	// 5. Prepare Response
	response := &dto.ScreenshotResponse{
		URL:              uploadResult.URL,
		ScreenshotURL:    uploadResult.URL,
		Width:            metadata.Width,
		Height:           metadata.Height,
		Format:           req.Format,
		FileSize:         len(imageBytes),
		ProcessingTimeMs: metadata.ProcessingTimeMs,
		Status:           "completed",
		CreatedAt:        time.Now().Format(time.RFC3339),
	}

	// 6. Cache Response (Async)
	go func() {
		// Use background context for async operations
		bgCtx := context.Background()
		_ = s.cache.Set(bgCtx, cacheKey, response, time.Duration(s.cfg.RenderCacheTTL)*time.Second)
	}()

	return response, nil
}

func (s *RenderService) SignURL(ctx context.Context, req dto.SignURLRequest, accessKey string, secretKey string) (*dto.SignURLResponse, error) {
	// 1. Calculate Expiry
	expiry := req.Expiry
	if expiry == 0 {
		expiry = 3600 // Default 1 hour
	}
	expiresAt := time.Now().Add(time.Duration(expiry) * time.Second).Unix()

	// 2. Prepare Params
	// We need to match EXACTLY how Python sorts/builds the string
	params := make(map[string]string)
	params["url"] = req.URL
	params["access_key"] = accessKey
	params["expires"] = fmt.Sprintf("%d", expiresAt)

	// Add options (flat functionality for now)
	for k, v := range req.Options {
		params[k] = fmt.Sprintf("%v", v)
	}

	// 3. Generate Signature
	signature := utils.GenerateSignature(params, secretKey)

	// 4. Build URL
	values := url.Values{}
	for k, v := range params {
		values.Set(k, v)
	}
	values.Set("signature", signature)

	// Base URL should ideally come from config. Using a default or relative.
	baseURL := "/api/v1/renders/signed"
	if s.cfg.AppEnv == "production" {
		baseURL = "https://screenshotbeam.com/api/v1/renders/signed"
	}

	finalURL := fmt.Sprintf("%s?%s", baseURL, values.Encode())

	return &dto.SignURLResponse{
		SignedURL: finalURL,
		ExpiresAt: expiresAt,
	}, nil
}

func (s *RenderService) generateCacheKey(req dto.RenderRequest) string {
	// Create canonical JSON representation
	// This approach mimics the Python logic but needs to be careful about key order
	// A simpler way: hash relevant fields manually

	keyData := fmt.Sprintf(
		"v1:%s:%d:%d:%s:%d:%t:%t:%d:%f:%t:%t:%t:%s:%s",
		req.URL,
		req.Width,
		req.Height,
		req.Format,
		req.Quality,
		req.FullPage,
		req.CaptureBeyondViewport,
		req.Delay,
		req.DeviceScaleFactor,
		req.BlockAds,
		req.BlockTrackers,
		req.BlockCookieBanners,
		req.UserAgent,
		req.Selector, // Includes selector in cache key!
	)

	hash := sha256.Sum256([]byte(keyData))
	return fmt.Sprintf("render:%s", hex.EncodeToString(hash[:]))
}

// ListJobs lists render jobs for a user
func (s *RenderService) ListJobs(ctx context.Context, userID uuid.UUID, limit, offset int) ([]models.RenderJob, int64, error) {
	return s.jobRepo.ListByUserID(userID.String(), limit, offset)
}

// GetJob retrieves a specific job by ID with user authorization
func (s *RenderService) GetJob(ctx context.Context, userID uuid.UUID, jobID string) (*models.RenderJob, error) {
	job, err := s.jobRepo.FindByID(jobID)
	if err != nil {
		return nil, &utils.AppError{Code: 404, Message: "Job not found"}
	}

	if job.UserID != userID {
		return nil, &utils.AppError{Code: 403, Message: "Forbidden"}
	}

	return job, nil
}

func (s *RenderService) DeleteJob(ctx context.Context, jobID string, userID uuid.UUID) error {
	// 1. Get Job
	job, err := s.jobRepo.FindByID(jobID)
	if err != nil {
		return err
	}

	// 2. Auth Check
	if job.UserID != userID {
		return &utils.AppError{Code: 403, Message: "Forbidden"}
	}

	// 3. Delete from S3
	if job.S3Key != nil && *job.S3Key != "" {
		// Best effort delete from storage
		_ = s.storage.Delete(ctx, *job.S3Key)
	}

	// 4. Delete DB Record
	return s.jobRepo.Delete(jobID)
}
