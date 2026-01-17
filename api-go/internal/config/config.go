package config

import (
	"log"
	"os"
	"strconv"
	"strings"

	"github.com/joho/godotenv"
)

type Config struct {
	// Server
	AppEnv string
	Port   string
	Debug  bool

	// Database
	DatabaseURL string

	// Redis
	RedisURL string

	// AWS S3
	AWSS3Bucket        string
	AWSS3Region        string
	AWSS3Endpoint      string
	AWSAccessKeyID     string
	AWSSecretAccessKey string

	// JWT
	JWTSecretKey          string
	JWTAccessTokenExpiry  int // minutes
	JWTRefreshTokenExpiry int // days

	// Go Renderer
	GoRendererURL     string
	GoRendererTimeout int // seconds

	// Stripe
	StripeSecretKey     string
	StripeWebhookSecret string

	// Rate Limiting
	RateLimitEnabled bool

	// Encryption
	SecretKeyEncryptionKey string

	// Turnstile
	TurnstileSecretKey string

	// CORS
	CORSOrigins []string

	// Admin
	AdminEmails []string

	// Features
	UseGoRenderer bool

	// Sentry
	SentryDSN string

	// Cache
	RenderCacheTTL int // seconds
	APICacheTTL    int // seconds
}

var cfg *Config

func Load() *Config {
	if cfg != nil {
		return cfg
	}

	// Load .env file if exists
	_ = godotenv.Load()

	cfg = &Config{
		// Server
		AppEnv: getEnv("APP_ENV", "development"),
		Port:   getEnv("PORT", "8080"),
		Debug:  getEnvBool("DEBUG", false),

		// Database
		DatabaseURL: getEnv("DATABASE_URL", ""),

		// Redis
		RedisURL: getEnv("REDIS_URL", "redis://localhost:6379/0"),

		// AWS S3
		AWSS3Bucket:        getEnv("AWS_S3_BUCKET", ""),
		AWSS3Region:        getEnv("AWS_S3_REGION", "nyc3"),
		AWSS3Endpoint:      getEnv("AWS_S3_ENDPOINT", ""),
		AWSAccessKeyID:     getEnv("AWS_ACCESS_KEY_ID", ""),
		AWSSecretAccessKey: getEnv("AWS_SECRET_ACCESS_KEY", ""),

		// JWT
		JWTSecretKey:          getEnv("JWT_SECRET_KEY", ""),
		JWTAccessTokenExpiry:  getEnvInt("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30),
		JWTRefreshTokenExpiry: getEnvInt("JWT_REFRESH_TOKEN_EXPIRE_DAYS", 7),

		// Go Renderer
		GoRendererURL:     getEnv("GO_RENDERER_URL", "http://167.71.85.169:8001"),
		GoRendererTimeout: getEnvInt("GO_RENDERER_TIMEOUT", 60),

		// Stripe
		StripeSecretKey:     getEnv("STRIPE_SECRET_KEY", ""),
		StripeWebhookSecret: getEnv("STRIPE_WEBHOOK_SECRET", ""),

		// Rate Limiting
		RateLimitEnabled: getEnvBool("RATE_LIMIT_ENABLED", true),

		// Encryption
		SecretKeyEncryptionKey: getEnv("SECRET_KEY_ENCRYPTION_KEY", ""),

		TurnstileSecretKey: getEnv("TURNSTILE_SECRET_KEY", ""),

		// CORS
		APICacheTTL: getEnvInt("API_CACHE_TTL", 300), // 5 minutes
	}

	// Helper to clean JSON-style array string
	corsRaw := getEnv("CORS_ORIGINS", "*")
	corsRaw = strings.ReplaceAll(corsRaw, "[", "")
	corsRaw = strings.ReplaceAll(corsRaw, "]", "")
	corsRaw = strings.ReplaceAll(corsRaw, "\"", "")
	corsRaw = strings.ReplaceAll(corsRaw, " ", "") // remove spaces too
	cfg.CORSOrigins = strings.Split(corsRaw, ",")

	// Other Configs
	cfg.AdminEmails = getEnvSlice("ADMIN_EMAILS", []string{})
	cfg.UseGoRenderer = getEnvBool("USE_GO_RENDERER", true)
	cfg.RenderCacheTTL = getEnvInt("RENDER_CACHE_TTL", 86400)
	cfg.SentryDSN = getEnv("SENTRY_DSN", "")

	// Validate required config
	if cfg.DatabaseURL == "" {
		log.Fatal("DATABASE_URL is required")
	}
	if cfg.JWTSecretKey == "" {
		log.Fatal("JWT_SECRET_KEY is required")
	}

	return cfg
}

func Get() *Config {
	if cfg == nil {
		return Load()
	}
	return cfg
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}

func getEnvBool(key string, defaultValue bool) bool {
	if value := os.Getenv(key); value != "" {
		return strings.ToLower(value) == "true" || value == "1"
	}
	return defaultValue
}

func getEnvSlice(key string, defaultValue []string) []string {
	if value := os.Getenv(key); value != "" {
		return strings.Split(value, ",")
	}
	return defaultValue
}
