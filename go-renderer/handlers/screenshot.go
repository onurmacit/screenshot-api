package handlers

import (
	"encoding/base64"
	"fmt"

	"github.com/gofiber/fiber/v2"

	"github.com/onurmacit/screenshot-api/go-renderer/services"
)

// ScreenshotHandler handles screenshot and PDF requests
type ScreenshotHandler struct {
	renderer *services.Renderer
}

// NewScreenshotHandler creates a new screenshot handler
func NewScreenshotHandler(renderer *services.Renderer) *ScreenshotHandler {
	return &ScreenshotHandler{renderer: renderer}
}

// ScreenshotRequest represents the request body for screenshot capture
type ScreenshotRequest struct {
	URL                string  `json:"url"`
	Width              int     `json:"width"`
	Height             int     `json:"height"`
	Format             string  `json:"format"`
	Quality            int     `json:"quality"`
	FullPage           bool    `json:"full_page"`
	Delay              int     `json:"delay"`
	DeviceScaleFactor  float64 `json:"device_scale_factor"`
	BlockAds           bool    `json:"block_ads"`
	BlockTrackers      bool    `json:"block_trackers"`
	BlockCookieBanners bool    `json:"block_cookie_banners"`
	UserAgent          string  `json:"user_agent"`
	Selector           string  `json:"selector"`
	ScrollIntoView     string  `json:"scroll_into_view"`
	ScrollAdjustTop    int     `json:"scroll_adjust_top"`
	HTML               string  `json:"html"`
	Markdown           string  `json:"markdown"`
	Timeout            int     `json:"timeout"`
	ReturnBase64       bool    `json:"return_base64"`
}

// ScreenshotResponse represents the JSON response (when return_base64 is true)
type ScreenshotResponse struct {
	ImageBase64      string `json:"image_base64,omitempty"`
	Width            int    `json:"width"`
	Height           int    `json:"height"`
	ProcessingTimeMs int64  `json:"processing_time_ms"`
	Format           string `json:"format"`
}

// PDFRequest represents the request body for PDF generation
type PDFRequest struct {
	URL             string  `json:"url"`
	Format          string  `json:"format"`
	Landscape       bool    `json:"landscape"`
	PrintBackground bool    `json:"print_background"`
	Scale           float64 `json:"scale"`
	Delay           int     `json:"delay"`
	Timeout         int     `json:"timeout"`
	ReturnBase64    bool    `json:"return_base64"`
}

// PDFResponse represents the JSON response for PDF
type PDFResponse struct {
	PDFBase64        string `json:"pdf_base64,omitempty"`
	PageCount        int    `json:"page_count"`
	ProcessingTimeMs int64  `json:"processing_time_ms"`
}

// CaptureScreenshot handles screenshot capture requests
func (h *ScreenshotHandler) CaptureScreenshot(c *fiber.Ctx) error {
	var req ScreenshotRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{
			"error":   "invalid_request",
			"message": err.Error(),
		})
	}

	// Validate: at least URL or HTML required
	if req.URL == "" && req.HTML == "" && req.Markdown == "" {
		return c.Status(400).JSON(fiber.Map{
			"error":   "missing_source",
			"message": "url, html, or markdown is required",
		})
	}

	// Convert request to options
	opts := services.ScreenshotOptions{
		URL:                req.URL,
		Width:              req.Width,
		Height:             req.Height,
		Format:             req.Format,
		Quality:            req.Quality,
		FullPage:           req.FullPage,
		Delay:              req.Delay,
		DeviceScaleFactor:  req.DeviceScaleFactor,
		BlockAds:           req.BlockAds,
		BlockTrackers:      req.BlockTrackers,
		BlockCookieBanners: req.BlockCookieBanners,
		UserAgent:          req.UserAgent,
		Selector:           req.Selector,
		ScrollIntoView:     req.ScrollIntoView,
		ScrollAdjustTop:    req.ScrollAdjustTop,
		HTML:               req.HTML,
		Markdown:           req.Markdown,
		Timeout:            req.Timeout,
	}

	// Capture screenshot
	result, err := h.renderer.CaptureScreenshot(opts)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{
			"error":   "render_error",
			"message": err.Error(),
		})
	}

	// Return JSON with base64 or binary image
	if req.ReturnBase64 {
		return c.JSON(ScreenshotResponse{
			ImageBase64:      base64.StdEncoding.EncodeToString(result.ImageBytes),
			Width:            result.Width,
			Height:           result.Height,
			ProcessingTimeMs: result.ProcessingTimeMs,
			Format:           req.Format,
		})
	}

	// Return binary image (default for efficiency)
	contentType := "image/jpeg"
	switch req.Format {
	case "png":
		contentType = "image/png"
	case "webp":
		contentType = "image/webp"
	}

	c.Set("Content-Type", contentType)
	c.Set("X-Processing-Time-Ms", fmt.Sprintf("%d", result.ProcessingTimeMs))
	c.Set("X-Width", fmt.Sprintf("%d", result.Width))
	c.Set("X-Height", fmt.Sprintf("%d", result.Height))

	return c.Send(result.ImageBytes)
}

// GeneratePDF handles PDF generation requests
func (h *ScreenshotHandler) GeneratePDF(c *fiber.Ctx) error {
	var req PDFRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{
			"error":   "invalid_request",
			"message": err.Error(),
		})
	}

	// Validate URL
	if req.URL == "" {
		return c.Status(400).JSON(fiber.Map{
			"error":   "missing_url",
			"message": "url is required",
		})
	}

	// Convert request to options
	opts := services.PDFOptions{
		URL:             req.URL,
		Format:          req.Format,
		Landscape:       req.Landscape,
		PrintBackground: req.PrintBackground,
		Scale:           req.Scale,
		Delay:           req.Delay,
		Timeout:         req.Timeout,
	}

	// Generate PDF
	result, err := h.renderer.GeneratePDF(opts)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{
			"error":   "render_error",
			"message": err.Error(),
		})
	}

	// Return JSON with base64 or binary PDF
	if req.ReturnBase64 {
		return c.JSON(PDFResponse{
			PDFBase64:        base64.StdEncoding.EncodeToString(result.PDFBytes),
			PageCount:        result.PageCount,
			ProcessingTimeMs: result.ProcessingTimeMs,
		})
	}

	// Return binary PDF (default)
	c.Set("Content-Type", "application/pdf")
	c.Set("X-Processing-Time-Ms", fmt.Sprintf("%d", result.ProcessingTimeMs))
	c.Set("X-Page-Count", fmt.Sprintf("%d", result.PageCount))

	return c.Send(result.PDFBytes)
}
