package config

import (
	"log"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/joho/godotenv"
)

// Config holds all application configuration
type Config struct {
	// Database
	DatabaseURL string

	// Redis
	RedisURL string

	// JWT
	JWTSecret             string
	JWTSecretKey          string
	JWTAccessTokenExpiry  int // minutes
	JWTRefreshTokenExpiry int // hours

	// Encryption
	SecretKeyEncryptionKey string

	// AWS/S3
	AWSAccessKeyID     string
	AWSSecretAccessKey string
	S3Bucket           string
	S3Endpoint         string
	S3Region           string
	AWSS3Bucket        string
	AWSS3Endpoint      string
	AWSS3Region        string

	// Stripe
	StripeSecretKey     string
	StripeWebhookSecret string

	// Sentry
	SentryDSN string
	Debug     bool

	// Rate Limiting
	RateLimitEnabled bool

	// Cache TTL
	APICacheTTL    int // seconds
	RenderCacheTTL int // seconds

	// Renderer
	GoRendererURL     string
	GoRendererTimeout int // seconds

	// Turnstile (Cloudflare CAPTCHA)
	TurnstileSecretKey string

	// App
	AppEnv        string
	Port          string
	Version       string
	CommitSHA     string
	InstanceColor string

	// Admin
	AdminEmails []string
}

// Global config instance
var cfg *Config

// loadSecret loads a secret from either a file (for Docker secrets) or environment variable
func loadSecret(envVar string) string {
	// Check if _FILE variant exists (Docker secrets pattern)
	if fileEnv := os.Getenv(envVar + "_FILE"); fileEnv != "" {
		content, err := os.ReadFile(fileEnv)
		if err != nil {
			log.Printf("Warning: Failed to read secret file %s: %v", fileEnv, err)
			// Fallback to regular env var
			return os.Getenv(envVar)
		}

		// Log secret access (without the actual value)
		log.Printf("Secret loaded from file: %s at %s", envVar, time.Now().Format(time.RFC3339))
		return strings.TrimSpace(string(content))
	}

	// Fallback to regular env var
	return os.Getenv(envVar)
}

// Load loads configuration from environment
func Load() *Config {
	// Try to load .env files (not critical if missing)
	_ = godotenv.Load(".env.production")
	_ = godotenv.Load(".env.local")
	_ = godotenv.Load(".env")

	cfg = &Config{
		// Database
		DatabaseURL: loadSecret("DATABASE_URL"),

		// Redis
		RedisURL: loadSecret("REDIS_URL"),

		// JWT
		JWTSecret:             loadSecret("JWT_SECRET"),
		JWTSecretKey:          loadSecret("JWT_SECRET"),
		JWTAccessTokenExpiry:  getEnvOrDefaultInt("JWT_ACCESS_TOKEN_EXPIRY", 60),   // 60 minutes
		JWTRefreshTokenExpiry: getEnvOrDefaultInt("JWT_REFRESH_TOKEN_EXPIRY", 168), // 7 days in hours

		// Encryption
		SecretKeyEncryptionKey: loadSecret("SECRET_KEY_ENCRYPTION_KEY"),

		// AWS/S3
		AWSAccessKeyID:     loadSecret("AWS_ACCESS_KEY_ID"),
		AWSSecretAccessKey: loadSecret("AWS_SECRET_ACCESS_KEY"),
		S3Bucket:           os.Getenv("S3_BUCKET"),
		S3Endpoint:         os.Getenv("S3_ENDPOINT"),
		S3Region:           getEnvOrDefault("S3_REGION", "nyc3"),
		AWSS3Bucket:        os.Getenv("S3_BUCKET"),
		AWSS3Endpoint:      os.Getenv("S3_ENDPOINT"),
		AWSS3Region:        getEnvOrDefault("S3_REGION", "nyc3"),

		// Stripe
		StripeSecretKey:     loadSecret("STRIPE_SECRET_KEY"),
		StripeWebhookSecret: loadSecret("STRIPE_WEBHOOK_SECRET"),

		// Sentry
		SentryDSN: os.Getenv("SENTRY_DSN"),
		Debug:     os.Getenv("DEBUG") == "true",

		// Rate Limiting
		RateLimitEnabled: os.Getenv("RATE_LIMIT_ENABLED") != "false",

		// Cache TTL
		APICacheTTL:    getEnvOrDefaultInt("API_CACHE_TTL", 300),     // 5 minutes
		RenderCacheTTL: getEnvOrDefaultInt("RENDER_CACHE_TTL", 3600), // 1 hour

		// Renderer
		GoRendererURL:     os.Getenv("GO_RENDERER_URL"),
		GoRendererTimeout: getEnvOrDefaultInt("GO_RENDERER_TIMEOUT", 60),

		// Turnstile
		TurnstileSecretKey: os.Getenv("TURNSTILE_SECRET_KEY"),

		// App
		AppEnv:        getEnvOrDefault("APP_ENV", "development"),
		Port:          getEnvOrDefault("PORT", "8080"),
		Version:       os.Getenv("VERSION"),
		CommitSHA:     os.Getenv("COMMIT_SHA"),
		InstanceColor: os.Getenv("INSTANCE_COLOR"),

		// Admin
		AdminEmails: parseAdminEmails(os.Getenv("ADMIN_EMAILS")),
	}

	// Validate required fields
	if cfg.DatabaseURL == "" {
		log.Fatal("DATABASE_URL is required")
	}

	if cfg.JWTSecret == "" {
		log.Fatal("JWT_SECRET is required")
	}

	return cfg
}

// Get returns the current config
func Get() *Config {
	if cfg == nil {
		return Load()
	}
	return cfg
}

func getEnvOrDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvOrDefaultInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intVal, err := strconv.Atoi(value); err == nil {
			return intVal
		}
	}
	return defaultValue
}

func parseAdminEmails(emails string) []string {
	if emails == "" {
		return []string{}
	}

	parts := strings.Split(emails, ",")
	result := make([]string, 0, len(parts))
	for _, email := range parts {
		trimmed := strings.TrimSpace(email)
		if trimmed != "" {
			result = append(result, trimmed)
		}
	}
	return result
}

// IsProduction returns true if running in production
func (c *Config) IsProduction() bool {
	return c.AppEnv == "production"
}

// IsDevelopment returns true if running in development
func (c *Config) IsDevelopment() bool {
	return c.AppEnv == "development" || c.AppEnv == ""
}

// IsAdmin checks if an email is an admin
func (c *Config) IsAdmin(email string) bool {
	for _, adminEmail := range c.AdminEmails {
		if strings.EqualFold(email, adminEmail) {
			return true
		}
	}
	return false
}
