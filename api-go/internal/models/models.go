package models

import (
	"time"

	"github.com/google/uuid"
	"github.com/lib/pq"
	"gorm.io/gorm"
)

// User represents a user in the system
type User struct {
	ID               uuid.UUID `gorm:"type:uuid;primaryKey;default:gen_random_uuid()" json:"id"`
	Email            string    `gorm:"type:varchar(255);uniqueIndex;not null" json:"email"`
	PasswordHash     *string   `gorm:"type:text" json:"-"`
	FullName         *string   `gorm:"type:varchar(255)" json:"full_name"`
	PlanID           int       `gorm:"not null;default:1" json:"plan_id"`
	StripeCustomerID *string   `gorm:"type:varchar(255)" json:"stripe_customer_id"`
	IsActive         bool      `gorm:"default:true" json:"is_active"`
	AuthProvider     *string   `gorm:"type:varchar(50)" json:"auth_provider"` // google, github
	ProviderID       *string   `gorm:"type:varchar(255)" json:"provider_id"`
	CreatedAt        time.Time `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt        time.Time `gorm:"autoUpdateTime" json:"updated_at"`

	// Relations
	Plan          Plan           `gorm:"foreignKey:PlanID" json:"plan,omitempty"`
	APIKeys       []APIKey       `gorm:"foreignKey:UserID" json:"-"`
	RefreshTokens []RefreshToken `gorm:"foreignKey:UserID" json:"-"`
}

func (User) TableName() string {
	return "users"
}

// Plan represents a subscription plan
type Plan struct {
	ID                    int            `gorm:"primaryKey" json:"id"`
	Name                  string         `gorm:"type:varchar(50);uniqueIndex;not null" json:"name"`
	DisplayName           string         `gorm:"type:varchar(100);not null" json:"display_name"`
	PriceMonthly          float64        `gorm:"type:numeric(10,2);not null;default:0" json:"price_monthly"`
	PriceYearly           float64        `gorm:"type:numeric(10,2);not null;default:0" json:"price_yearly"`
	RequestsPerMonth      int            `gorm:"not null" json:"requests_per_month"`
	MaxConcurrentRequests int            `gorm:"not null" json:"max_concurrent_requests"`
	MaxTimeoutMS          int            `gorm:"not null" json:"max_timeout_ms"`
	MaxFileSizeMB         int            `gorm:"not null" json:"max_file_size_mb"`
	Features              map[string]any `gorm:"type:jsonb;serializer:json" json:"features"`
	IsActive              bool           `gorm:"default:true" json:"is_active"`
	StripePriceID         *string        `gorm:"type:varchar(255)" json:"stripe_price_id"`
	CreatedAt             time.Time      `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt             time.Time      `gorm:"autoUpdateTime" json:"updated_at"`
}

func (Plan) TableName() string {
	return "plans"
}

// APIKey represents an API key for authentication
type APIKey struct {
	ID                 uuid.UUID      `gorm:"type:uuid;primaryKey;default:gen_random_uuid()" json:"id"`
	UserID             uuid.UUID      `gorm:"type:uuid;not null;index" json:"user_id"`
	Name               *string        `gorm:"type:varchar(255)" json:"name"`
	KeyHash            string         `gorm:"type:varchar(64);uniqueIndex;not null" json:"-"`
	KeyPrefix          string         `gorm:"type:varchar(10);not null" json:"key_prefix"`
	AccessKey          string         `gorm:"type:varchar(50);not null" json:"access_key"` // Public identifier (pk_...)
	SecretKey          string         `gorm:"-" json:"-"`                                  // Legacy/Encrypted (Not in DB)
	SecretKeyEncrypted *string        `gorm:"type:text" json:"-"`                          // Dual-key Encrypted (sk_...)
	Scopes             pq.StringArray `gorm:"type:text[]" json:"scopes"`
	IsActive           bool           `gorm:"default:true" json:"is_active"`
	EnforceSigning     bool           `gorm:"default:false" json:"enforce_signing"`
	ExpiresAt          *time.Time     `gorm:"" json:"expires_at"`
	LastUsedAt         *time.Time     `gorm:"" json:"last_used_at"`
	CreatedAt          time.Time      `gorm:"autoCreateTime" json:"created_at"`

	// Relations
	User User `gorm:"foreignKey:UserID" json:"user,omitempty"`
}

func (APIKey) TableName() string {
	return "api_keys"
}

// CheckScope checks if the key has the required scope
func (k *APIKey) CheckScope(required string) bool {
	for _, s := range k.Scopes {
		if s == required || s == "*" {
			return true
		}
	}
	return false
}

// IsExpired checks if the key is expired
func (k *APIKey) IsExpired() bool {
	if k.ExpiresAt == nil {
		return false
	}
	return time.Now().After(*k.ExpiresAt)
}

// RenderJob represents a screenshot or PDF rendering job
type RenderJob struct {
	ID               uuid.UUID      `gorm:"type:uuid;primaryKey;default:gen_random_uuid()" json:"id"`
	UserID           uuid.UUID      `gorm:"type:uuid;not null;index" json:"user_id"`
	APIKeyID         *uuid.UUID     `gorm:"type:uuid" json:"api_key_id"`
	Type             string         `gorm:"type:varchar(20);not null;default:'screenshot'" json:"type"` // screenshot, pdf
	Status           string         `gorm:"type:varchar(20);not null;default:'pending'" json:"status"`  // pending, processing, completed, failed
	URL              string         `gorm:"type:text;not null" json:"url"`
	Options          map[string]any `gorm:"type:jsonb;serializer:json" json:"options"`
	S3Key            *string        `gorm:"type:text" json:"-"`
	S3URL            *string        `gorm:"type:text" json:"s3_url"`
	FileSizeBytes    *int           `gorm:"" json:"file_size_bytes"`
	ProcessingTimeMS *int           `gorm:"" json:"processing_time_ms"`
	ErrorMessage     *string        `gorm:"type:text" json:"error_message"`
	Result           map[string]any `gorm:"type:jsonb;serializer:json" json:"result"`
	Priority         int            `gorm:"default:5" json:"priority"`
	WebhookURL       *string        `gorm:"type:text" json:"webhook_url"`
	CreatedAt        time.Time      `gorm:"autoCreateTime" json:"created_at"`
	StartedAt        *time.Time     `gorm:"" json:"started_at"`
	CompletedAt      *time.Time     `gorm:"" json:"completed_at"`
	ExpiresAt        *time.Time     `gorm:"" json:"expires_at"`

	// Relations
	User User `gorm:"foreignKey:UserID" json:"user,omitempty"`
}

func (RenderJob) TableName() string {
	return "render_jobs"
}

func (j *RenderJob) BeforeCreate(tx *gorm.DB) (err error) {
	if j.ID == uuid.Nil {
		j.ID = uuid.New()
	}
	return
}

// RefreshToken represents a JWT refresh token
type RefreshToken struct {
	ID         uuid.UUID `gorm:"type:uuid;primaryKey;default:gen_random_uuid()" json:"id"`
	UserID     uuid.UUID `gorm:"type:uuid;not null;index" json:"user_id"`
	TokenHash  string    `gorm:"type:varchar(64);uniqueIndex;not null" json:"-"`
	IPAddress  *string   `gorm:"type:varchar(45)" json:"ip_address"`
	DeviceInfo *string   `gorm:"type:text" json:"device_info"`
	IsRevoked  bool      `gorm:"default:false" json:"is_revoked"`
	ExpiresAt  time.Time `gorm:"not null" json:"expires_at"`
	CreatedAt  time.Time `gorm:"autoCreateTime" json:"created_at"`

	// Relations
	User User `gorm:"foreignKey:UserID" json:"user,omitempty"`
}

func (RefreshToken) TableName() string {
	return "refresh_tokens"
}

// Webhook for user configured endpoints
type Webhook struct {
	ID           uuid.UUID  `gorm:"type:uuid;primaryKey;default:gen_random_uuid()" json:"id"`
	UserID       uuid.UUID  `gorm:"type:uuid;not null;index" json:"user_id"`
	URL          string     `gorm:"type:text;not null" json:"url"`
	Secret       string     `gorm:"type:varchar(255);not null" json:"secret"` // Signing secret
	Events       []string   `gorm:"type:text[];serializer:json" json:"events"`
	IsActive     bool       `gorm:"default:true" json:"is_active"`
	FailureCount int        `gorm:"default:0" json:"failure_count"`
	LastCalledAt *time.Time `gorm:"" json:"last_called_at"`
	CreatedAt    time.Time  `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt    time.Time  `gorm:"autoUpdateTime" json:"updated_at"`

	// Relations
	User User `gorm:"foreignKey:UserID" json:"user,omitempty"`
}

func (Webhook) TableName() string {
	return "webhooks"
}

// Invoice represents a billing invoice
type Invoice struct {
	ID              uuid.UUID `gorm:"type:uuid;primaryKey;default:gen_random_uuid()" json:"id"`
	UserID          uuid.UUID `gorm:"type:uuid;not null;index" json:"user_id"`
	StripeInvoiceID string    `gorm:"type:varchar(255);uniqueIndex" json:"stripe_invoice_id"`
	Amount          int       `gorm:"not null" json:"amount"` // cents
	Currency        string    `gorm:"type:varchar(3);default:'usd'" json:"currency"`
	Status          string    `gorm:"type:varchar(20)" json:"status"`
	InvoiceURL      string    `gorm:"type:text" json:"invoice_url"`
	PeriodStart     time.Time `gorm:"not null" json:"period_start"`
	PeriodEnd       time.Time `gorm:"not null" json:"period_end"`
	CreatedAt       time.Time `gorm:"autoCreateTime" json:"created_at"`

	// Relations
	User User `gorm:"foreignKey:UserID" json:"user,omitempty"`
}

func (Invoice) TableName() string {
	return "invoices"
}

// UsageRecord represents monthly usage tracking
type UsageRecord struct {
	ID        uuid.UUID `gorm:"type:uuid;primaryKey;default:gen_random_uuid()" json:"id"`
	UserID    uuid.UUID `gorm:"type:uuid;not null" json:"user_id"`
	Month     time.Time `gorm:"type:date;not null" json:"month"` // First day of month
	Count     int       `gorm:"default:0" json:"count"`
	CreatedAt time.Time `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt time.Time `gorm:"autoUpdateTime" json:"updated_at"`

	// Relations
	User User `gorm:"foreignKey:UserID" json:"user,omitempty"`
}

func (UsageRecord) TableName() string {
	return "usage_records"
}
