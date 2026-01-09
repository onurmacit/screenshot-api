package services

import (
	"fmt"
	"io"
	"net"
	"net/url"
	"strings"
	"time"

	"github.com/go-rod/rod"
	"github.com/go-rod/rod/lib/proto"
)

// Renderer handles screenshot and PDF rendering
type Renderer struct {
	pool *BrowserPool
}

// NewRenderer creates a new renderer with the given browser pool
func NewRenderer(pool *BrowserPool) *Renderer {
	return &Renderer{pool: pool}
}

// ScreenshotOptions defines options for screenshot capture
type ScreenshotOptions struct {
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
}

// ScreenshotResult contains the result of a screenshot capture
type ScreenshotResult struct {
	ImageBytes       []byte `json:"-"`
	Width            int    `json:"width"`
	Height           int    `json:"height"`
	ProcessingTimeMs int64  `json:"processing_time_ms"`
}

// PDFOptions defines options for PDF generation
type PDFOptions struct {
	URL             string  `json:"url"`
	Format          string  `json:"format"`
	Landscape       bool    `json:"landscape"`
	PrintBackground bool    `json:"print_background"`
	Scale           float64 `json:"scale"`
	Delay           int     `json:"delay"`
	Timeout         int     `json:"timeout"`
}

// PDFResult contains the result of PDF generation
type PDFResult struct {
	PDFBytes         []byte `json:"-"`
	PageCount        int    `json:"page_count"`
	ProcessingTimeMs int64  `json:"processing_time_ms"`
}

// Blocked domains for ads, trackers, etc.
var blockedDomains = []string{
	// Analytics & Tracking
	"google-analytics", "googletagmanager", "analytics.", "tracking.",
	"hotjar", "clarity.ms", "fullstory", "heapanalytics",
	"mixpanel", "segment.", "amplitude", "plausible",
	// Ads
	"googlesyndication", "doubleclick", "adnxs", "adsrvr", "adroll",
	"criteo", "taboola", "outbrain", "revcontent",
	"amazon-adsystem", "advertising", "adservice", "pagead",
	// Social widgets
	"facebook.net", "connect.facebook", "fbcdn",
	"platform.twitter", "syndication.twitter",
	// Chat widgets
	"intercom", "crisp.chat", "drift", "zendesk", "zdassets",
	"hubspot", "hs-scripts", "hs-analytics", "tawk.to",
	// Error tracking (we do our own)
	"sentry", "bugsnag", "rollbar", "logrocket",
}

// Cookie banner domains
var cookieBannerDomains = []string{
	"cookiebot", "onetrust", "optanon", "cookielaw",
	"trustarc", "truste.com", "cookieconsent", "osano",
	"quantcast", "didomi", "iubenda", "usercentrics",
	"termly", "secureprivacy", "cookiepro", "complianz",
}

// CaptureScreenshot captures a screenshot of the given URL
func (r *Renderer) CaptureScreenshot(opts ScreenshotOptions) (*ScreenshotResult, error) {
	startTime := time.Now()

	// SSRF protection
	if err := validateURL(opts.URL); err != nil {
		return nil, err
	}

	// Set defaults
	if opts.Width == 0 {
		opts.Width = 1920
	}
	if opts.Height == 0 {
		opts.Height = 1080
	}
	if opts.Format == "" {
		opts.Format = "jpeg"
	}
	if opts.Quality == 0 {
		opts.Quality = 80
	}
	if opts.Timeout == 0 {
		opts.Timeout = 30000
	}

	// Get browser from pool
	browser := r.pool.Acquire()

	// Create new page
	page := browser.MustPage()
	defer page.MustClose()

	// Set viewport
	page.MustSetViewport(opts.Width, opts.Height, opts.DeviceScaleFactor, false)

	// Set user agent if provided
	if opts.UserAgent != "" {
		page.MustSetUserAgent(&proto.NetworkSetUserAgentOverride{
			UserAgent: opts.UserAgent,
		})
	}

	// Block unwanted resources
	if opts.BlockAds || opts.BlockTrackers || opts.BlockCookieBanners {
		router := page.HijackRequests()
		router.MustAdd("*", func(ctx *rod.Hijack) {
			reqURL := ctx.Request.URL().String()
			hostname := ctx.Request.URL().Hostname()

			// Block ads and trackers
			if opts.BlockAds || opts.BlockTrackers {
				for _, domain := range blockedDomains {
					if strings.Contains(hostname, domain) || strings.Contains(reqURL, domain) {
						ctx.Response.Fail(proto.NetworkErrorReasonBlockedByClient)
						return
					}
				}
			}

			// Block cookie banners
			if opts.BlockCookieBanners {
				for _, domain := range cookieBannerDomains {
					if strings.Contains(hostname, domain) || strings.Contains(reqURL, domain) {
						ctx.Response.Fail(proto.NetworkErrorReasonBlockedByClient)
						return
					}
				}
			}

			ctx.ContinueRequest(&proto.FetchContinueRequest{})
		})
		go router.Run()
		defer router.Stop()
	}

	// Navigate to URL or set HTML content
	if opts.HTML != "" {
		page.MustSetDocumentContent(opts.HTML)
	} else if opts.URL != "" {
		page.Timeout(time.Duration(opts.Timeout) * time.Millisecond).MustNavigate(opts.URL)
		page.MustWaitLoad()
	}

	// Wait for delay if specified
	if opts.Delay > 0 {
		time.Sleep(time.Duration(opts.Delay) * time.Millisecond)
	}

	// Scroll into view if specified
	if opts.ScrollIntoView != "" {
		el := page.MustElement(opts.ScrollIntoView)
		el.MustScrollIntoView()
		if opts.ScrollAdjustTop != 0 {
			page.Mouse.MustScroll(0, float64(opts.ScrollAdjustTop))
		}
	}

	// Capture screenshot
	var imageBytes []byte
	var format proto.PageCaptureScreenshotFormat

	switch opts.Format {
	case "png":
		format = proto.PageCaptureScreenshotFormatPng
	case "webp":
		format = proto.PageCaptureScreenshotFormatWebp
	default:
		format = proto.PageCaptureScreenshotFormatJpeg
	}

	if opts.Selector != "" {
		// Capture specific element
		el := page.MustElement(opts.Selector)
		imageBytes, _ = el.Screenshot(format, opts.Quality)
	} else if opts.FullPage {
		// Full page screenshot
		imageBytes, _ = page.Screenshot(true, &proto.PageCaptureScreenshot{
			Format:  format,
			Quality: &opts.Quality,
		})
	} else {
		// Viewport screenshot
		imageBytes, _ = page.Screenshot(false, &proto.PageCaptureScreenshot{
			Format:  format,
			Quality: &opts.Quality,
		})
	}

	processingTime := time.Since(startTime).Milliseconds()

	return &ScreenshotResult{
		ImageBytes:       imageBytes,
		Width:            opts.Width,
		Height:           opts.Height,
		ProcessingTimeMs: processingTime,
	}, nil
}

// GeneratePDF generates a PDF from the given URL
func (r *Renderer) GeneratePDF(opts PDFOptions) (*PDFResult, error) {
	startTime := time.Now()

	// SSRF protection
	if err := validateURL(opts.URL); err != nil {
		return nil, err
	}

	// Set defaults
	if opts.Format == "" {
		opts.Format = "A4"
	}
	if opts.Scale == 0 {
		opts.Scale = 1.0
	}
	if opts.Timeout == 0 {
		opts.Timeout = 30000
	}

	// Get browser from pool
	browser := r.pool.Acquire()

	// Create new page
	page := browser.MustPage()
	defer page.MustClose()

	// Navigate to URL
	page.Timeout(time.Duration(opts.Timeout) * time.Millisecond).MustNavigate(opts.URL)
	page.MustWaitLoad()

	// Wait for delay if specified
	if opts.Delay > 0 {
		time.Sleep(time.Duration(opts.Delay) * time.Millisecond)
	}

	// Generate PDF
	pdfReader, err := page.PDF(&proto.PagePrintToPDF{
		Landscape:         opts.Landscape,
		PrintBackground:   opts.PrintBackground,
		Scale:             &opts.Scale,
		PaperWidth:        nil, // Use format defaults
		PaperHeight:       nil,
		PreferCSSPageSize: true,
	})
	if err != nil {
		return nil, fmt.Errorf("PDF generation failed: %w", err)
	}

	// Read all bytes from the stream
	pdfBytes, err := io.ReadAll(pdfReader)
	if err != nil {
		return nil, fmt.Errorf("failed to read PDF bytes: %w", err)
	}

	processingTime := time.Since(startTime).Milliseconds()

	return &PDFResult{
		PDFBytes:         pdfBytes,
		PageCount:        1, // Rod doesn't provide page count easily
		ProcessingTimeMs: processingTime,
	}, nil
}

// validateURL checks if the URL is safe (no SSRF)
func validateURL(rawURL string) error {
	if rawURL == "" {
		return nil // HTML content mode
	}

	parsed, err := url.Parse(rawURL)
	if err != nil {
		return fmt.Errorf("invalid URL: %w", err)
	}

	// Only allow http/https
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return fmt.Errorf("invalid scheme: %s", parsed.Scheme)
	}

	// Block localhost
	hostname := parsed.Hostname()
	if hostname == "localhost" || hostname == "127.0.0.1" || hostname == "::1" || hostname == "0.0.0.0" {
		return fmt.Errorf("localhost URLs not allowed")
	}

	// Try to resolve and check for private IPs
	ips, err := net.LookupIP(hostname)
	if err == nil {
		for _, ip := range ips {
			if isPrivateIP(ip) {
				return fmt.Errorf("private IP addresses not allowed")
			}
		}
	}

	return nil
}

// isPrivateIP checks if an IP is private
func isPrivateIP(ip net.IP) bool {
	privateBlocks := []string{
		"10.0.0.0/8",
		"172.16.0.0/12",
		"192.168.0.0/16",
		"127.0.0.0/8",
		"169.254.0.0/16",
		"::1/128",
		"fc00::/7",
		"fe80::/10",
	}

	for _, block := range privateBlocks {
		_, cidr, _ := net.ParseCIDR(block)
		if cidr.Contains(ip) {
			return true
		}
	}

	return false
}
