package services

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/dto"
	"github.com/onurmacit/screenshot-api/api-go/internal/utils"
)

type RendererClient struct {
	client  *http.Client
	baseURL string
}

func NewRendererClient(cfg *config.Config) *RendererClient {
	return &RendererClient{
		client: &http.Client{
			Timeout: time.Duration(cfg.GoRendererTimeout) * time.Second,
		},
		baseURL: cfg.GoRendererURL,
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

func (c *RendererClient) sendRequest(ctx context.Context, endpoint string, payload interface{}) ([]byte, *dto.Metadata, error) {
	jsonBody, err := json.Marshal(payload)
	if err != nil {
		return nil, nil, utils.ErrInternal
	}

	req, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+endpoint, bytes.NewBuffer(jsonBody))
	if err != nil {
		return nil, nil, utils.ErrInternal
	}

	req.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, nil, utils.NewError(http.StatusServiceUnavailable, "Renderer service unavailable")
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		// Read error message
		body, _ := io.ReadAll(resp.Body)
		return nil, nil, utils.NewError(resp.StatusCode, fmt.Sprintf("Renderer error: %s", string(body)))
	}

	imageBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, nil, utils.ErrInternal
	}

	// Parse metadata headers
	metadata := &dto.Metadata{
		Width:            getIntHeader(resp.Header, "X-Width"),
		Height:           getIntHeader(resp.Header, "X-Height"),
		PageCount:        getIntHeader(resp.Header, "X-Page-Count"),
		ProcessingTimeMs: getIntHeader(resp.Header, "X-Processing-Time-Ms"),
	}

	return imageBytes, metadata, nil
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
