package worker

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"time"

	"github.com/google/uuid"
	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/dto"
	"github.com/onurmacit/screenshot-api/api-go/internal/models"
	repo "github.com/onurmacit/screenshot-api/api-go/internal/repository"
	"github.com/onurmacit/screenshot-api/api-go/internal/services"
	"gorm.io/gorm"
)

// Worker processes jobs from the queue
type Worker struct {
	queue      *services.JobQueue
	renderer   *services.RendererClient
	storage    *services.StorageService
	jobRepo    *repo.RenderJobRepository
	cfg        *config.Config
	db         *gorm.DB
	maxRetries int
}

// NewWorker creates a new Worker instance
func NewWorker(
	queue *services.JobQueue,
	renderer *services.RendererClient,
	storage *services.StorageService,
	jobRepo *repo.RenderJobRepository,
	cfg *config.Config,
	db *gorm.DB,
) *Worker {
	return &Worker{
		queue:      queue,
		renderer:   renderer,
		storage:    storage,
		jobRepo:    jobRepo,
		cfg:        cfg,
		db:         db,
		maxRetries: 3,
	}
}

// Start begins processing jobs from the queue
// This should be called in a goroutine
func (w *Worker) Start(ctx context.Context) error {
	consumerName := fmt.Sprintf("worker-%s", uuid.New().String()[:8])
	log.Printf("Starting worker: %s", consumerName)

	// Initialize queue consumer group
	if err := w.queue.Initialize(ctx); err != nil {
		return fmt.Errorf("failed to initialize queue: %w", err)
	}

	// Start stale message recovery in background
	go w.recoverStaleMessages(ctx, consumerName)

	// Start consuming jobs
	return w.queue.Consume(ctx, consumerName, func(ctx context.Context, job *services.JobPayload) error {
		return w.processJob(ctx, job)
	})
}

// processJob handles a single job
func (w *Worker) processJob(ctx context.Context, payload *services.JobPayload) error {
	log.Printf("Processing job: id=%s, type=%s", payload.JobID, payload.Type)

	// Get job from database
	job, err := w.jobRepo.FindByID(payload.JobID)
	if err != nil {
		log.Printf("Job not found in DB: %s", payload.JobID)
		return err
	}

	// Update status to processing
	job.Status = "processing"
	start := time.Now()
	job.StartedAt = &start
	if err := w.jobRepo.Update(job); err != nil {
		log.Printf("Failed to update job status: %v", err)
	}

	// Process based on job type
	var result *ProcessResult
	switch payload.Type {
	case "screenshot":
		result, err = w.processScreenshot(ctx, payload, job)
	case "pdf":
		result, err = w.processPDF(ctx, payload, job)
	default:
		err = fmt.Errorf("unknown job type: %s", payload.Type)
	}

	// Handle result
	if err != nil {
		return w.handleFailure(job, payload, err)
	}

	return w.handleSuccess(job, result, start)
}

// ProcessResult contains the result of a job
type ProcessResult struct {
	URL      string
	Width    int
	Height   int
	FileSize int
}

// processScreenshot handles screenshot jobs
func (w *Worker) processScreenshot(ctx context.Context, payload *services.JobPayload, job *models.RenderJob) (*ProcessResult, error) {
	// Parse request from payload
	var req dto.RenderRequest
	if err := json.Unmarshal(payload.Request, &req); err != nil {
		return nil, fmt.Errorf("failed to parse request: %w", err)
	}

	// Process with retry
	var imageBytes []byte
	var metadata *dto.Metadata
	var lastErr error

	for attempt := 0; attempt <= w.maxRetries; attempt++ {
		if attempt > 0 {
			// Exponential backoff
			delay := time.Duration(math.Pow(2, float64(attempt))) * 5 * time.Second
			log.Printf("Retry %d/%d for job %s, waiting %v", attempt, w.maxRetries, payload.JobID, delay)
			time.Sleep(delay)
		}

		// Create context with timeout for this attempt
		attemptCtx, cancel := context.WithTimeout(ctx, 90*time.Second)
		imageBytes, metadata, lastErr = w.renderer.Capture(attemptCtx, req)
		cancel()

		if lastErr == nil {
			break
		}

		log.Printf("Attempt %d failed for job %s: %v", attempt+1, payload.JobID, lastErr)
	}

	if lastErr != nil {
		return nil, fmt.Errorf("all retries failed: %w", lastErr)
	}

	// Upload to S3
	uploadResult, err := w.storage.UploadRender(ctx, imageBytes, req.Format, payload.UserID)
	if err != nil {
		return nil, fmt.Errorf("upload failed: %w", err)
	}

	return &ProcessResult{
		URL:      uploadResult.URL,
		Width:    metadata.Width,
		Height:   metadata.Height,
		FileSize: len(imageBytes),
	}, nil
}

// processPDF handles PDF generation jobs
func (w *Worker) processPDF(ctx context.Context, payload *services.JobPayload, job *models.RenderJob) (*ProcessResult, error) {
	// Parse request from payload
	var req dto.PDFRequest
	if err := json.Unmarshal(payload.Request, &req); err != nil {
		return nil, fmt.Errorf("failed to parse request: %w", err)
	}

	// Process with retry
	var pdfBytes []byte
	var metadata *dto.Metadata
	var lastErr error

	for attempt := 0; attempt <= w.maxRetries; attempt++ {
		if attempt > 0 {
			delay := time.Duration(math.Pow(2, float64(attempt))) * 5 * time.Second
			log.Printf("Retry %d/%d for job %s, waiting %v", attempt, w.maxRetries, payload.JobID, delay)
			time.Sleep(delay)
		}

		attemptCtx, cancel := context.WithTimeout(ctx, 90*time.Second)
		pdfBytes, metadata, lastErr = w.renderer.GeneratePDF(attemptCtx, req)
		cancel()

		if lastErr == nil {
			break
		}

		log.Printf("Attempt %d failed for job %s: %v", attempt+1, payload.JobID, lastErr)
	}

	if lastErr != nil {
		return nil, fmt.Errorf("all retries failed: %w", lastErr)
	}

	// Upload to S3
	uploadResult, err := w.storage.UploadRender(ctx, pdfBytes, "pdf", payload.UserID)
	if err != nil {
		return nil, fmt.Errorf("upload failed: %w", err)
	}

	return &ProcessResult{
		URL:      uploadResult.URL,
		FileSize: len(pdfBytes),
		Width:    metadata.PageCount, // Repurpose for page count
	}, nil
}

// handleSuccess updates the job with success result
func (w *Worker) handleSuccess(job *models.RenderJob, result *ProcessResult, startTime time.Time) error {
	completed := time.Now()
	processingMs := int(completed.Sub(startTime).Milliseconds())

	job.Status = "completed"
	job.CompletedAt = &completed
	job.S3URL = &result.URL
	job.ProcessingTimeMs = &processingMs
	job.FileSizeBytes = &result.FileSize
	job.Result = map[string]any{
		"url":    result.URL,
		"width":  result.Width,
		"height": result.Height,
	}

	if err := w.jobRepo.Update(job); err != nil {
		log.Printf("Failed to update completed job: %v", err)
		return err
	}

	log.Printf("Job completed: id=%s, url=%s, processing_ms=%d", job.ID, result.URL, processingMs)

	// TODO: Send webhook notification if configured
	// w.sendWebhook(job)

	return nil
}

// handleFailure updates the job with failure status
func (w *Worker) handleFailure(job *models.RenderJob, payload *services.JobPayload, err error) error {
	errMsg := err.Error()
	retryCount := payload.RetryCount + 1

	job.Status = "failed"
	job.ErrorMessage = &errMsg
	job.RetryCount = retryCount

	if updateErr := w.jobRepo.Update(job); updateErr != nil {
		log.Printf("Failed to update failed job: %v", updateErr)
	}

	// Increment Prometheus error metric
	services.JobProcessingErrors.Inc()

	log.Printf("Job failed: id=%s, error=%s, retries=%d", job.ID, errMsg, retryCount)

	// Return error to NOT acknowledge the message (allows redelivery)
	// But if we've exceeded max retries, acknowledge to move to dead-letter
	if retryCount >= w.maxRetries {
		log.Printf("Job moved to dead-letter: id=%s", job.ID)
		return nil // ACK to remove from queue
	}

	return err // NACK to allow redelivery
}

// recoverStaleMessages periodically claims and reprocesses stale messages
func (w *Worker) recoverStaleMessages(ctx context.Context, consumerName string) {
	ticker := time.NewTicker(1 * time.Minute)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			// Claim messages that have been pending for more than 5 minutes
			messages, err := w.queue.ClaimStaleMessages(ctx, consumerName, 5*time.Minute)
			if err != nil {
				log.Printf("Error claiming stale messages: %v", err)
				continue
			}

			if len(messages) > 0 {
				log.Printf("Recovered %d stale messages", len(messages))
			}
		}
	}
}
