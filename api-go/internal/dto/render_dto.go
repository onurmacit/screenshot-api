package dto

import "time"

type RenderRequest struct {
	URL                   string  `json:"url" validate:"required,url"`
	Width                 int     `json:"width"`
	Height                int     `json:"height"`
	Format                string  `json:"format"`
	Quality               int     `json:"quality"`
	FullPage              bool    `json:"full_page"`
	CaptureBeyondViewport bool    `json:"capture_beyond_viewport"`
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
	ResponseType          string  `json:"response_type"` // json, binary, by_format

	// Internal
	ReturnBase64 bool `json:"return_base64"`
}

// PDF options
type PDFRequest struct {
	URL             string  `json:"url"`
	HTML            string  `json:"html,omitempty"`     // Optional
	Markdown        string  `json:"markdown,omitempty"` // Optional
	Format          string  `json:"format,omitempty"`   // A4, Letter, etc.
	Landscape       bool    `json:"landscape,omitempty"`
	PrintBackground bool    `json:"print_background,omitempty"`
	Scale           float64 `json:"scale,omitempty"`
	Delay           int     `json:"delay,omitempty"`
	Timeout         int     `json:"timeout,omitempty"`
}

// PDF Response (Sync)
type PDFResponse struct {
	URL              string `json:"url"`
	PageCount        int    `json:"page_count"`
	ProcessingTimeMs int    `json:"processing_time_ms"`
	FileSize         int    `json:"file_size"`
}

type Metadata struct {
	Width            int `json:"width"`
	Height           int `json:"height"`
	PageCount        int `json:"page_count"` // Added
	ProcessingTimeMs int `json:"processing_time_ms"`
}

type SignURLRequest struct {
	URL     string                 `json:"url"`
	Options map[string]interface{} `json:"options"`
	Expiry  int                    `json:"expiry,omitempty"` // seconds
}

type SignURLResponse struct {
	SignedURL string `json:"signed_url"`
	ExpiresAt int64  `json:"expires_at"`
}

type DemoRequest struct {
	URL   string `json:"url"`
	Token string `json:"token"`
}

type ScreenshotResponse struct {
	URL              string `json:"url"`
	ScreenshotURL    string `json:"screenshot_url"` // Alias
	Width            int    `json:"width"`
	Height           int    `json:"height"`
	Format           string `json:"format"`
	FileSize         int    `json:"file_size"`
	ProcessingTimeMs int    `json:"processing_time_ms"`
	Status           string `json:"status"`
	CreatedAt        string `json:"created_at"`
}

type RenderJobResponse struct {
	JobID            string     `json:"job_id"`
	Type             string     `json:"type"`
	Status           string     `json:"status"`
	URL              string     `json:"url,omitempty"`
	Format           string     `json:"format,omitempty"`
	Size             *SizeInfo  `json:"size,omitempty"`
	FileSize         int        `json:"file_size,omitempty"`
	ProcessingTimeMs int        `json:"processing_time_ms,omitempty"`
	Cached           bool       `json:"cached,omitempty"`
	CreatedAt        time.Time  `json:"created_at"`
	CompletedAt      *time.Time `json:"completed_at,omitempty"`
	ErrorMessage     string     `json:"error_message,omitempty"`
}

type SizeInfo struct {
	Width  int `json:"width"`
	Height int `json:"height"`
}
