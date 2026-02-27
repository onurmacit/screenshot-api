package services

import (
	"fmt"
	"io"
	"log"
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
	ScrollIntoView        string  `json:"scroll_into_view"`
	ScrollAdjustTop       int     `json:"scroll_adjust_top"`
	HTML                  string  `json:"html"`
	Markdown              string  `json:"markdown"`
	Timeout               int     `json:"timeout"`
	CaptureBeyondViewport bool    `json:"capture_beyond_viewport"`
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

		// For scroll operations, wait for page to fully stabilize
		// Dynamic sites like Stripe need extra time for JS to render content
		if opts.ScrollIntoView != "" || opts.ScrollAdjustTop != 0 {
			// Wait for network to be idle (no pending requests for 500ms)
			_ = page.WaitRequestIdle(500*time.Millisecond, nil, nil, nil)
			// Additional stabilization time for lazy-loaded content
			time.Sleep(1000 * time.Millisecond)
			log.Printf("[SCROLL] Page stabilized, proceeding with scroll")
		}
	}

	// Wait for delay if specified
	if opts.Delay > 0 {
		time.Sleep(time.Duration(opts.Delay) * time.Millisecond)
	}

	// === SCROLL HANDLING ===
	// scroll_into_view: Scroll to make a specific element visible
	// scroll_adjust_top: Fine-tune scroll position (positive = down, negative = up)

	if opts.ScrollIntoView != "" {
		// Log for debugging
		log.Printf("[SCROLL] scroll_into_view requested: selector='%s'", opts.ScrollIntoView)

		// Use multiple scroll methods for maximum reliability
		result, err := page.Eval(`(selector) => {
			// Find all matching elements and use the LAST one (usually the main footer)
			const elements = document.querySelectorAll(selector);
			if (elements.length === 0) {
				return { success: false, error: 'Element not found: ' + selector };
			}
			
			// Use the last matching element (for footer, this is usually the main one)
			const el = elements[elements.length - 1];
			
			// Get document height for context
			const docHeight = Math.max(
				document.body.scrollHeight,
				document.documentElement.scrollHeight
			);
			
			// Get element's absolute position
			const rect = el.getBoundingClientRect();
			const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
			let absoluteTop = rect.top + scrollTop;
			
			// Store initial scroll position
			const initialScroll = window.scrollY;
			
			// If element appears to be in wrong position (within first viewport), 
			// it might be due to lazy loading. Scroll to bottom first to trigger loading.
			if (absoluteTop < window.innerHeight && docHeight > window.innerHeight * 2) {
				// Scroll to bottom to trigger lazy loading
				window.scrollTo(0, docHeight);
				// Brief wait (handled by Go code)
			}
			
			// Re-get position after potential scroll
			const newRect = el.getBoundingClientRect();
			absoluteTop = newRect.top + window.pageYOffset;
			
			// Now scroll to element
			window.scrollTo({
				top: absoluteTop,
				behavior: 'instant'
			});
			
			// Also try scrollIntoView as backup
			el.scrollIntoView({ behavior: 'instant', block: 'start' });
			
			return { 
				success: true, 
				elementTop: absoluteTop,
				initialScroll: initialScroll,
				finalScroll: window.scrollY,
				viewportHeight: window.innerHeight,
				documentHeight: docHeight,
				elementsFound: elements.length
			};
		}`, opts.ScrollIntoView)

		if err != nil {
			log.Printf("[SCROLL] JavaScript error: %v", err)
			return nil, fmt.Errorf("scroll_into_view failed: %w", err)
		}

		// Check if element was found and log result
		resultMap := result.Value.Map()
		if success, ok := resultMap["success"]; !ok || !success.Bool() {
			errMsg := "unknown error"
			if e, ok := resultMap["error"]; ok {
				errMsg = e.String()
			}
			log.Printf("[SCROLL] Element not found: %s", errMsg)
			return nil, fmt.Errorf("scroll_into_view element not found: '%s' - %s", opts.ScrollIntoView, errMsg)
		}

		// Log scroll result for debugging
		log.Printf("[SCROLL] Result: elementsFound=%.0f, docHeight=%.0f, elementTop=%.0f, initialScroll=%.0f, finalScroll=%.0f",
			resultMap["elementsFound"].Num(),
			resultMap["documentHeight"].Num(),
			resultMap["elementTop"].Num(),
			resultMap["initialScroll"].Num(),
			resultMap["finalScroll"].Num())

		// Wait for scroll to complete and content to stabilize
		time.Sleep(500 * time.Millisecond)
	}

	// Apply scroll adjustment (works with or without scroll_into_view)
	// positive value = scroll down (content moves up)
	// negative value = scroll up (content moves down)
	if opts.ScrollAdjustTop != 0 {
		log.Printf("[SCROLL] scroll_adjust_top requested: offset=%d", opts.ScrollAdjustTop)

		// Use JavaScript for precise pixel-level scroll control
		// Only use scrollTo once (not both scrollTo and scrollBy)
		result, _ := page.Eval(`(offset) => {
			const before = window.scrollY;
			const target = Math.max(0, before + offset); // Prevent negative scroll
			window.scrollTo({
				top: target,
				behavior: 'instant'
			});
			return { before: before, target: target, after: window.scrollY, offset: offset };
		}`, opts.ScrollAdjustTop)

		if result != nil {
			rm := result.Value.Map()
			log.Printf("[SCROLL] Adjust result: before=%.0f, target=%.0f, after=%.0f, offset=%.0f",
				rm["before"].Num(), rm["target"].Num(), rm["after"].Num(), rm["offset"].Num())
		}

		// Wait for scroll to complete
		time.Sleep(300 * time.Millisecond)
	}

	// Final stabilization wait if any scrolling occurred
	if opts.ScrollIntoView != "" || opts.ScrollAdjustTop != 0 {
		// Wait for any lazy-loaded images or content triggered by scroll
		time.Sleep(300 * time.Millisecond)
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

	// Track actual captured dimensions (may differ from viewport for selector captures)
	capturedWidth := opts.Width
	capturedHeight := opts.Height

	if opts.Selector != "" {
		// Enhanced selector capture with bounding box clip
		var err error
		var w, h int
		imageBytes, w, h, err = r.captureSelector(page, opts, format)
		if err != nil {
			return nil, err
		}
		capturedWidth = w
		capturedHeight = h
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
		Width:            capturedWidth,
		Height:           capturedHeight,
		ProcessingTimeMs: processingTime,
	}, nil
}

// captureSelector captures a specific element with enhanced logic
// Returns: imageBytes, width, height, error
//
// Performance strategy:
//   - Fast JS pre-check (~0ms) to see if element exists in DOM
//   - If not found: progressive scroll + short JS re-checks (max ~5s total)
//   - If found: use rod Element with short timeout for interaction
//   - Total budget: 10 seconds max for entire selector operation
func (r *Renderer) captureSelector(page *rod.Page, opts ScreenshotOptions, format proto.PageCaptureScreenshotFormat) ([]byte, int, int, error) {
	// Validate selector syntax
	if !isValidSelector(opts.Selector) {
		return nil, 0, 0, &SelectorError{
			Selector:  opts.Selector,
			Operation: "validate",
			Err:       ErrInvalidSelector,
		}
	}

	// Total time budget for selector operations (prevents runaway waits)
	selectorDeadline := time.Now().Add(10 * time.Second)

	// Configuration
	stableTimeout := 500 * time.Millisecond
	scrollDelay := 150 * time.Millisecond

	// --- PHASE 1: Fast JavaScript pre-check (instant, no rod timeout) ---
	// This avoids the 15s rod timeout per attempt when the element simply doesn't exist
	log.Printf("[SELECTOR] Fast pre-check for: '%s'", opts.Selector)

	exists, err := r.jsElementExists(page, opts.Selector)
	if err != nil {
		log.Printf("[SELECTOR] JS pre-check error: %v, falling back to rod", err)
		// Don't fail here, fall through to rod-based lookup
		exists = false
	}

	var el *rod.Element

	if exists {
		// Element exists in DOM — grab it with a short rod timeout
		log.Printf("[SELECTOR] Element found in DOM, acquiring rod reference")
		el, err = r.findElementWithTimeout(page, opts.Selector, 3*time.Second)
		if err != nil {
			return nil, 0, 0, &SelectorError{
				Selector:  opts.Selector,
				Operation: "find",
				Err:       fmt.Errorf("%w: element found in DOM but rod could not acquire it - %v", ErrSelectorNotFound, err),
			}
		}
	} else {
		// Element NOT in DOM — try progressive scroll to trigger lazy loading
		log.Printf("[SELECTOR] Element not in DOM, trying scroll-and-retry")

		maxScrollRetries := 2
		scrollDistances := []float64{500, 1500} // progressive scroll

		for attempt := 0; attempt < maxScrollRetries; attempt++ {
			// Check time budget
			if time.Now().After(selectorDeadline) {
				break
			}

			// Scroll to trigger lazy loading
			page.Mouse.Scroll(0, scrollDistances[attempt], 1)
			time.Sleep(time.Duration(800+attempt*400) * time.Millisecond)

			// Re-check with JS
			exists, _ = r.jsElementExists(page, opts.Selector)
			if exists {
				log.Printf("[SELECTOR] Element appeared after scroll attempt %d", attempt+1)
				break
			}
		}

		if !exists {
			// Final attempt: scroll to bottom and check
			if time.Now().Before(selectorDeadline) {
				page.Eval(`() => window.scrollTo(0, document.body.scrollHeight)`)
				time.Sleep(1 * time.Second)
				exists, _ = r.jsElementExists(page, opts.Selector)
			}
		}

		if !exists {
			log.Printf("[SELECTOR] Element not found after all attempts: '%s'", opts.Selector)
			return nil, 0, 0, &SelectorError{
				Selector:  opts.Selector,
				Operation: "find",
				Err:       fmt.Errorf("%w: element not found in page DOM", ErrSelectorNotFound),
			}
		}

		// Element found after scrolling — acquire with rod
		el, err = r.findElementWithTimeout(page, opts.Selector, 3*time.Second)
		if err != nil {
			return nil, 0, 0, &SelectorError{
				Selector:  opts.Selector,
				Operation: "find",
				Err:       fmt.Errorf("%w: element found in DOM after scrolling but rod could not acquire it - %v", ErrSelectorNotFound, err),
			}
		}
	}

	// --- PHASE 2: Visibility & stability checks ---
	// Skip auto-scroll if user specified scroll_into_view (they control scroll position)
	userControlledScroll := opts.ScrollIntoView != ""

	visible, err := el.Visible()
	if err != nil || !visible {
		// Only auto-scroll if user didn't specify scroll_into_view
		if !userControlledScroll {
			_ = el.ScrollIntoView()
			time.Sleep(scrollDelay)
		}

		// Check visibility again (element might be CSS hidden, not scroll-hidden)
		visible, _ = el.Visible()
		if !visible {
			return nil, 0, 0, &SelectorError{
				Selector:  opts.Selector,
				Operation: "visibility",
				Err:       fmt.Errorf("%w: element exists but is not visible (display:none or visibility:hidden)", ErrSelectorNotVisible),
			}
		}
	}

	// Wait for element to be stable (handles animations) — only if time budget allows
	if time.Now().Before(selectorDeadline) {
		err = el.WaitStable(stableTimeout)
		if err != nil {
			// Fallback to WaitVisible with short timeout
			_ = el.WaitVisible()
			// Non-fatal: proceed even if unstable
		}
	}

	// Scroll element into view ONLY if user didn't specify scroll_into_view
	if !userControlledScroll {
		if scrollErr := el.ScrollIntoView(); scrollErr != nil {
			_ = scrollErr
		}
	}

	// Brief delay for render stabilization
	time.Sleep(scrollDelay)

	// --- PHASE 3: Capture ---
	shape, err := el.Shape()
	if err != nil {
		return nil, 0, 0, &SelectorError{
			Selector:  opts.Selector,
			Operation: "bounds",
			Err:       fmt.Errorf("failed to get element bounds: %v", err),
		}
	}

	box := shape.Box()

	if box.Width <= 0 || box.Height <= 0 {
		return nil, 0, 0, &SelectorError{
			Selector:  opts.Selector,
			Operation: "bounds",
			Err:       fmt.Errorf("element has invalid dimensions: %.0fx%.0f (element may be collapsed or off-screen)", box.Width, box.Height),
		}
	}

	scale := opts.DeviceScaleFactor
	if scale == 0 {
		scale = 1.0
	}

	clip := &proto.PageViewport{
		X:      box.X,
		Y:      box.Y,
		Width:  box.Width,
		Height: box.Height,
		Scale:  scale,
	}

	quality := opts.Quality
	imageBytes, err := page.Screenshot(false, &proto.PageCaptureScreenshot{
		Format:                format,
		Quality:               &quality,
		Clip:                  clip,
		CaptureBeyondViewport: true,
	})
	if err != nil {
		return nil, 0, 0, &SelectorError{
			Selector:  opts.Selector,
			Operation: "capture",
			Err:       fmt.Errorf("screenshot capture failed: %v", err),
		}
	}

	elapsed := time.Since(selectorDeadline.Add(-10 * time.Second)).Milliseconds()
	log.Printf("[SELECTOR] Capture complete: '%s' (%dx%d) in %dms", opts.Selector, int(box.Width), int(box.Height), elapsed)

	return imageBytes, int(box.Width), int(box.Height), nil
}

// jsElementExists performs a fast JavaScript check to see if an element exists in the DOM.
// This is nearly instant (~0ms) compared to rod's Element() which waits for the timeout.
func (r *Renderer) jsElementExists(page *rod.Page, selector string) (bool, error) {
	var jsCode string

	if isXPathSelector(selector) {
		// XPath check
		jsCode = `(selector) => {
			try {
				const result = document.evaluate(selector, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
				return result.singleNodeValue !== null;
			} catch(e) {
				return false;
			}
		}`
	} else {
		// CSS selector check
		jsCode = `(selector) => {
			try {
				return document.querySelector(selector) !== null;
			} catch(e) {
				return false;
			}
		}`
	}

	result, err := page.Timeout(2*time.Second).Eval(jsCode, selector)
	if err != nil {
		return false, err
	}

	return result.Value.Bool(), nil
}

// findElementWithTimeout finds an element using rod with a specific timeout.
// Since we already confirmed the element exists via JS, this should be fast.
func (r *Renderer) findElementWithTimeout(page *rod.Page, selector string, timeout time.Duration) (*rod.Element, error) {
	if isXPathSelector(selector) {
		return page.Timeout(timeout).ElementX(selector)
	}
	return page.Timeout(timeout).Element(selector)
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
