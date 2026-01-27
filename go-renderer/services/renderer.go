package services

import (
	"fmt"
	"io"
	"net"
	"net/url"
	"os"
	"regexp"
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
	URL                   string  `json:"url"`
	Width                 int     `json:"width"`
	Height                int     `json:"height"`
	Format                string  `json:"format"`
	Quality               int     `json:"quality"`
	FullPage              bool    `json:"full_page"`
	Delay                 int     `json:"delay"`
	DeviceScaleFactor     float64 `json:"device_scale_factor"`
	BlockAds              bool    `json:"block_ads"`
	BlockTrackers         bool    `json:"block_trackers"`
	BlockCookieBanners    bool    `json:"block_cookie_banners"`
	UserAgent             string  `json:"user_agent"`
	Selector              string  `json:"selector"`
	SelectorPadding       int     `json:"selector_padding"`        // Padding around selector element (px)
	SelectorPaddingTop    int     `json:"selector_padding_top"`    // Top padding override
	SelectorPaddingRight  int     `json:"selector_padding_right"`  // Right padding override
	SelectorPaddingBottom int     `json:"selector_padding_bottom"` // Bottom padding override
	SelectorPaddingLeft   int     `json:"selector_padding_left"`   // Left padding override
	ScrollIntoView        string  `json:"scroll_into_view"`
	ScrollAdjustTop       int     `json:"scroll_adjust_top"`
	HTML                  string  `json:"html"`
	Markdown              string  `json:"markdown"`
	Timeout               int     `json:"timeout"`
	CaptureBeyondViewport bool    `json:"capture_beyond_viewport"`
	WaitForSelector       string  `json:"wait_for_selector"`       // Wait for this selector before capture
	WaitForSelectorState  string  `json:"wait_for_selector_state"` // visible, hidden, attached, detached
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

	// Navigate to URL or set HTML/Markdown content
	if opts.HTML != "" {
		page.MustSetDocumentContent(opts.HTML)
	} else if opts.Markdown != "" {
		// Convert Markdown to HTML and render
		htmlContent := markdownToHTML(opts.Markdown)
		page.MustSetDocumentContent(htmlContent)
	} else if opts.URL != "" {
		page.Timeout(time.Duration(opts.Timeout) * time.Millisecond).MustNavigate(opts.URL)
		page.MustWaitLoad()
	}

	// Wait for specific selector if requested (useful for SPAs)
	if opts.WaitForSelector != "" {
		waitTimeout := 10 * time.Second
		var waitErr error

		switch opts.WaitForSelectorState {
		case "hidden":
			el, err := page.Timeout(waitTimeout).ElementR(opts.WaitForSelector, "")
			if err == nil {
				// Element found, wait for it to disappear
				waitErr = el.WaitInvisible()
			} else {
				// If element already not found, that's also fine for "hidden"
				waitErr = nil
			}
		case "detached":
			// Wait until element is removed from DOM
			for i := 0; i < 100; i++ {
				_, err := page.Timeout(100 * time.Millisecond).Element(opts.WaitForSelector)
				if err != nil {
					break // Element not found, good
				}
				time.Sleep(100 * time.Millisecond)
			}
		case "attached":
			// Just wait for element to exist in DOM
			_, waitErr = page.Timeout(waitTimeout).Element(opts.WaitForSelector)
		default: // "visible" or empty
			// Wait for element to be visible
			el, err := page.Timeout(waitTimeout).Element(opts.WaitForSelector)
			if err == nil {
				waitErr = el.WaitVisible()
			} else {
				waitErr = err
			}
		}

		if waitErr != nil {
			return nil, fmt.Errorf("wait_for_selector '%s' failed: %w", opts.WaitForSelector, waitErr)
		}
	}

	// Wait for delay if specified
	if opts.Delay > 0 {
		time.Sleep(time.Duration(opts.Delay) * time.Millisecond)
	}

	// Scroll into view if specified
	if opts.ScrollIntoView != "" {
		el, err := page.Timeout(10 * time.Second).Element(opts.ScrollIntoView)
		if err != nil {
			return nil, fmt.Errorf("scroll element not found: %s - %w", opts.ScrollIntoView, err)
		}
		err = el.ScrollIntoView()
		if err != nil {
			return nil, fmt.Errorf("failed to scroll into view: %w", err)
		}
		if opts.ScrollAdjustTop != 0 {
			page.Mouse.Scroll(0, float64(opts.ScrollAdjustTop), 1)
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
		// Enhanced selector capture with bounding box clip
		var err error
		imageBytes, err = r.captureSelector(page, opts, format)
		if err != nil {
			return nil, err
		}
	} else if opts.FullPage {
		// Full page screenshot
		imageBytes, _ = page.Screenshot(true, &proto.PageCaptureScreenshot{
			Format:                format,
			Quality:               &opts.Quality,
			CaptureBeyondViewport: opts.CaptureBeyondViewport,
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

// captureSelector captures a specific element with enhanced logic
func (r *Renderer) captureSelector(page *rod.Page, opts ScreenshotOptions, format proto.PageCaptureScreenshotFormat) ([]byte, error) {
	// Validate selector syntax
	if !isValidSelector(opts.Selector) {
		return nil, &SelectorError{
			Selector:  opts.Selector,
			Operation: "validate",
			Err:       ErrInvalidSelector,
		}
	}

	// Configuration
	findTimeout := 15 * time.Second
	stableTimeout := 500 * time.Millisecond
	scrollDelay := 150 * time.Millisecond
	maxRetries := 3
	retryBackoff := 200 * time.Millisecond

	var el *rod.Element
	var err error

	// 1. Find element with retry logic
	for attempt := 0; attempt <= maxRetries; attempt++ {
		if attempt > 0 {
			time.Sleep(retryBackoff * time.Duration(attempt))
		}

		// Determine if selector is XPath or CSS
		if isXPathSelector(opts.Selector) {
			el, err = page.Timeout(findTimeout).ElementX(opts.Selector)
		} else {
			el, err = page.Timeout(findTimeout).Element(opts.Selector)
		}

		if err == nil {
			break
		}

		// On last attempt, return error
		if attempt == maxRetries {
			return nil, &SelectorError{
				Selector:  opts.Selector,
				Operation: "find",
				Err:       fmt.Errorf("%w: element not found after %d attempts - %v", ErrSelectorNotFound, maxRetries+1, err),
			}
		}

		// Scroll down to trigger lazy loading and retry
		page.Mouse.Scroll(0, 500, 1)
		time.Sleep(scrollDelay)
	}

	// 2. Check if element is visible (not display:none or visibility:hidden)
	visible, err := el.Visible()
	if err != nil || !visible {
		// Try to make it visible by scrolling
		_ = el.ScrollIntoView()
		time.Sleep(scrollDelay)

		// Check again
		visible, _ = el.Visible()
		if !visible {
			return nil, &SelectorError{
				Selector:  opts.Selector,
				Operation: "visibility",
				Err:       fmt.Errorf("%w: element exists but is not visible (display:none or visibility:hidden)", ErrSelectorNotVisible),
			}
		}
	}

	// 3. Wait for element to be stable (handles animations)
	err = el.WaitStable(stableTimeout)
	if err != nil {
		// Fallback to WaitVisible
		err = el.WaitVisible()
		if err != nil {
			return nil, &SelectorError{
				Selector:  opts.Selector,
				Operation: "wait",
				Err:       fmt.Errorf("%w: element unstable - %v", ErrSelectorNotVisible, err),
			}
		}
	}

	// 4. Scroll element into view with centering
	if scrollErr := el.ScrollIntoView(); scrollErr != nil {
		// Non-fatal: element might already be visible, continue
		_ = scrollErr
	}

	// 5. Brief delay for render stabilization (lazy images, CSS transitions)
	time.Sleep(scrollDelay)

	// 6. Get bounding box for precise clip
	shape, err := el.Shape()
	if err != nil {
		return nil, &SelectorError{
			Selector:  opts.Selector,
			Operation: "bounds",
			Err:       fmt.Errorf("failed to get element bounds: %v", err),
		}
	}

	box := shape.Box()

	// Ensure valid dimensions
	if box.Width <= 0 || box.Height <= 0 {
		return nil, &SelectorError{
			Selector:  opts.Selector,
			Operation: "bounds",
			Err:       fmt.Errorf("element has invalid dimensions: %.0fx%.0f (element may be collapsed or off-screen)", box.Width, box.Height),
		}
	}

	// 7. Calculate padding (individual overrides take precedence)
	padTop := opts.SelectorPadding
	padRight := opts.SelectorPadding
	padBottom := opts.SelectorPadding
	padLeft := opts.SelectorPadding

	if opts.SelectorPaddingTop != 0 {
		padTop = opts.SelectorPaddingTop
	}
	if opts.SelectorPaddingRight != 0 {
		padRight = opts.SelectorPaddingRight
	}
	if opts.SelectorPaddingBottom != 0 {
		padBottom = opts.SelectorPaddingBottom
	}
	if opts.SelectorPaddingLeft != 0 {
		padLeft = opts.SelectorPaddingLeft
	}

	// 8. Create clip from bounding box with padding
	scale := opts.DeviceScaleFactor
	if scale == 0 {
		scale = 1.0
	}

	// Apply padding (ensure we don't go negative)
	clipX := box.X - float64(padLeft)
	clipY := box.Y - float64(padTop)
	clipWidth := box.Width + float64(padLeft) + float64(padRight)
	clipHeight := box.Height + float64(padTop) + float64(padBottom)

	if clipX < 0 {
		clipWidth += clipX // Reduce width by the negative amount
		clipX = 0
	}
	if clipY < 0 {
		clipHeight += clipY // Reduce height by the negative amount
		clipY = 0
	}

	clip := &proto.PageViewport{
		X:      clipX,
		Y:      clipY,
		Width:  clipWidth,
		Height: clipHeight,
		Scale:  scale,
	}

	// 9. Capture with clip
	quality := opts.Quality
	imageBytes, err := page.Screenshot(false, &proto.PageCaptureScreenshot{
		Format:  format,
		Quality: &quality,
		Clip:    clip,
	})
	if err != nil {
		return nil, &SelectorError{
			Selector:  opts.Selector,
			Operation: "capture",
			Err:       fmt.Errorf("screenshot capture failed: %v", err),
		}
	}

	return imageBytes, nil
}

// isXPathSelector checks if the selector is an XPath expression
func isXPathSelector(s string) bool {
	// XPath selectors typically start with / or //
	return strings.HasPrefix(s, "/") || strings.HasPrefix(s, "(")
}

// isValidSelector performs comprehensive selector validation
func isValidSelector(s string) bool {
	if s == "" {
		return false
	}

	// Trim whitespace
	s = strings.TrimSpace(s)
	if s == "" {
		return false
	}

	// Check for common invalid/dangerous patterns (XSS prevention)
	dangerousPatterns := []string{"<", ">", "{", "}", "javascript:", "data:", "vbscript:"}
	for _, pattern := range dangerousPatterns {
		if strings.Contains(strings.ToLower(s), pattern) {
			return false
		}
	}

	// Validate XPath selectors
	if isXPathSelector(s) {
		// Basic XPath validation - must have valid structure
		if !strings.Contains(s, "/") && !strings.HasPrefix(s, "(") {
			return false
		}
		return true
	}

	// Validate CSS selectors - must start with valid character
	// CSS selectors start with: ., #, [, *, or letter
	firstChar := rune(s[0])
	validStarts := []rune{'.', '#', '[', '*', ':'}
	for _, c := range validStarts {
		if firstChar == c {
			return true
		}
	}

	// Allow alphanumeric start (tag names like div, span, etc.)
	if (firstChar >= 'a' && firstChar <= 'z') || (firstChar >= 'A' && firstChar <= 'Z') {
		return true
	}

	return false
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

	// Block localhost (except if explicitly allowed)
	hostname := parsed.Hostname()
	if os.Getenv("ALLOW_LOCALHOST") != "true" {
		if hostname == "localhost" || hostname == "127.0.0.1" || hostname == "::1" || hostname == "0.0.0.0" {
			return fmt.Errorf("localhost URLs not allowed")
		}
	}

	// Try to resolve and check for private IPs
	ips, err := net.LookupIP(hostname)
	if err == nil && os.Getenv("ALLOW_LOCALHOST") != "true" {
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

// markdownToHTML converts Markdown content to a styled HTML page
func markdownToHTML(markdown string) string {
	content := markdown

	// Headers (process in reverse order to avoid ## matching # first)
	h3Re := regexp.MustCompile(`(?m)^### (.+)$`)
	content = h3Re.ReplaceAllString(content, "<h3>$1</h3>")

	h2Re := regexp.MustCompile(`(?m)^## (.+)$`)
	content = h2Re.ReplaceAllString(content, "<h2>$1</h2>")

	h1Re := regexp.MustCompile(`(?m)^# (.+)$`)
	content = h1Re.ReplaceAllString(content, "<h1>$1</h1>")

	// Bold
	boldRe := regexp.MustCompile(`\*\*(.+?)\*\*`)
	content = boldRe.ReplaceAllString(content, "<strong>$1</strong>")

	// Italic
	italicRe := regexp.MustCompile(`\*(.+?)\*`)
	content = italicRe.ReplaceAllString(content, "<em>$1</em>")

	// Inline code
	codeRe := regexp.MustCompile("`(.+?)`")
	content = codeRe.ReplaceAllString(content, "<code>$1</code>")

	// Links
	linkRe := regexp.MustCompile(`\[(.+?)\]\((.+?)\)`)
	content = linkRe.ReplaceAllString(content, `<a href="$2">$1</a>`)

	// Line breaks to paragraphs
	content = "<p>" + strings.ReplaceAll(content, "\n\n", "</p><p>") + "</p>"
	content = strings.ReplaceAll(content, "\n", "<br>")

	// Wrap in HTML template with styling
	htmlTemplate := `<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background-color: #ffffff;
    width: 100%%;
    margin: 0;
    padding: 40px 60px;
    box-sizing: border-box;
    line-height: 1.7;
    color: #1a1a1a;
}
h1, h2, h3, h4, h5, h6 { color: #111; margin-top: 1.5em; margin-bottom: 0.5em; }
h1 { font-size: 2.5em; border-bottom: 2px solid #eee; padding-bottom: 0.3em; }
h2 { font-size: 2em; border-bottom: 1px solid #eee; padding-bottom: 0.2em; }
h3 { font-size: 1.5em; }
code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }
pre { background: #f4f4f4; padding: 16px; border-radius: 6px; overflow-x: auto; }
a { color: #0366d6; text-decoration: none; }
a:hover { text-decoration: underline; }
p { margin: 0.5em 0; }
</style>
</head>
<body>
%s
</body>
</html>`

	return fmt.Sprintf(htmlTemplate, content)
}
