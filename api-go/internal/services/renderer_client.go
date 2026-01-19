package services

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"time"

	"github.com/sony/gobreaker"

	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/dto"
	"github.com/onurmacit/screenshot-api/api-go/internal/utils"
)

type RendererClient struct {
	client  *http.Client
	baseURL string
	cb      *gobreaker.CircuitBreaker
}

func NewRendererClient(cfg *config.Config) *RendererClient {
	// Circuit Breaker Settings
	// - Opens after 5 consecutive failures
	// - Half-open after 30 seconds
	// - Closes after 2 successful requests in half-open state
	cbSettings := gobreaker.Settings{
		Name:        "renderer",
		MaxRequests: 2,                // Max requests in half-open state
		Interval:    60 * time.Second, // Reset failure count after this interval
		Timeout:     30 * time.Second, // Time to wait before switching from open to half-open
		ReadyToTrip: func(counts gobreaker.Counts) bool {
			// Open circuit after 5 consecutive failures OR
			// when failure rate > 50% with at least 10 requests
			failureRatio := float64(counts.TotalFailures) / float64(counts.Requests)
			return counts.ConsecutiveFailures >= 5 || (counts.Requests >= 10 && failureRatio > 0.5)
		},
		OnStateChange: func(name string, from gobreaker.State, to gobreaker.State) {
			log.Printf("Circuit Breaker [%s]: state changed from %s to %s", name, from.String(), to.String())
		},
	}

	return &RendererClient{
		client: &http.Client{
			Timeout: time.Duration(cfg.GoRendererTimeout) * time.Second,
		},
		baseURL: cfg.GoRendererURL,
		cb:      gobreaker.NewCircuitBreaker(cbSettings),
	}
}

// Capture sends a screenshot request to the renderer service
func (c *RendererClient) Capture(ctx context.Context, req dto.RenderRequest) ([]byte, *dto.Metadata, error) {
	return c.sendRequest(ctx, "/render/screenshot", req)
}

// GeneratePDF sends a PDF generation request to the renderer service
func (c *RendererClient) GeneratePDF(ctx context.Context, req dto.PDFRequest) ([]byte, *dto.Metadata, error) {
	return c.sendRequest(ctx, "/render/pdf", req)
}

// GetCircuitBreakerState returns the current state of the circuit breaker
func (c *RendererClient) GetCircuitBreakerState() string {
	return c.cb.State().String()
}

// GetCircuitBreakerCounts returns the current counts of the circuit breaker
func (c *RendererClient) GetCircuitBreakerCounts() gobreaker.Counts {
	return c.cb.Counts()
}

func (c *RendererClient) sendRequest(ctx context.Context, endpoint string, payload interface{}) ([]byte, *dto.Metadata, error) {
	// Execute request through circuit breaker
	result, err := c.cb.Execute(func() (interface{}, error) {
		return c.doRequest(ctx, endpoint, payload)
	})

	if err != nil {
		// Check if circuit is open
		if err == gobreaker.ErrOpenState {
			return nil, nil, utils.NewError(http.StatusServiceUnavailable, "Renderer service temporarily unavailable (circuit open)")
		}
		if err == gobreaker.ErrTooManyRequests {
			return nil, nil, utils.NewError(http.StatusServiceUnavailable, "Renderer service recovering (circuit half-open)")
		}
		// Other errors from doRequest
		return nil, nil, err
	}

	// Type assert the result
	response := result.(*rendererResponse)
	return response.data, response.metadata, nil
}

// rendererResponse holds the response from renderer
type rendererResponse struct {
	data     []byte
	metadata *dto.Metadata
}

func (c *RendererClient) doRequest(ctx context.Context, endpoint string, payload interface{}) (*rendererResponse, error) {
	jsonBody, err := json.Marshal(payload)
	if err != nil {
		return nil, utils.ErrInternal
	}

	req, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+endpoint, bytes.NewBuffer(jsonBody))
	if err != nil {
		return nil, utils.ErrInternal
	}

	req.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		// This error will trigger circuit breaker
		return nil, fmt.Errorf("renderer request failed: %w", err)
	}
	defer resp.Body.Close()

	// 5xx errors should trip the circuit breaker
	if resp.StatusCode >= 500 {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("renderer server error (%d): %s", resp.StatusCode, string(body))
	}

	// 4xx errors are client errors, don't trip circuit breaker
	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		return nil, utils.NewError(resp.StatusCode, fmt.Sprintf("Renderer error: %s", string(body)))
	}

	imageBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, utils.ErrInternal
	}

	// Parse metadata headers
	metadata := &dto.Metadata{
		Width:            getIntHeader(resp.Header, "X-Width"),
		Height:           getIntHeader(resp.Header, "X-Height"),
		PageCount:        getIntHeader(resp.Header, "X-Page-Count"),
		ProcessingTimeMs: getIntHeader(resp.Header, "X-Processing-Time-Ms"),
	}

	return &rendererResponse{
		data:     imageBytes,
		metadata: metadata,
	}, nil
}

func getIntHeader(headers http.Header, key string) int {
	val := headers.Get(key)
	if val == "" {
		return 0
	}
	var res int
	fmt.Sscanf(val, "%d", &res)
	return res
}
