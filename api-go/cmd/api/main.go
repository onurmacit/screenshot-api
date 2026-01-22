package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/ansrivas/fiberprometheus/v2"
	"github.com/gofiber/fiber/v2"
	"github.com/prometheus/client_golang/prometheus"

	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/handlers"
	"github.com/onurmacit/screenshot-api/api-go/internal/middleware"
	"github.com/onurmacit/screenshot-api/api-go/internal/repository"
	"github.com/onurmacit/screenshot-api/api-go/internal/services"
	"github.com/onurmacit/screenshot-api/api-go/internal/utils"
	"github.com/onurmacit/screenshot-api/api-go/internal/worker"
	"github.com/onurmacit/screenshot-api/api-go/pkg/database"
	"github.com/onurmacit/screenshot-api/api-go/pkg/redis"

	"github.com/getsentry/sentry-go"
	"github.com/onurmacit/screenshot-api/api-go/internal/models"
)

func main() {
	// Load configuration
	cfg := config.Load()

	// Initialize Sentry
	if cfg.SentryDSN != "" {
		if err := sentry.Init(sentry.ClientOptions{
			Dsn:              cfg.SentryDSN,
			TracesSampleRate: 1.0,
			Environment:      cfg.AppEnv,
		}); err != nil {
			log.Printf("Sentry initialization failed: %v\n", err)
		} else {
			log.Println("Sentry initialized successfully")
			defer sentry.Flush(2 * time.Second)
		}
	}

	// Connect to Database
	db, err := database.Connect(cfg.DatabaseURL, cfg.Debug)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer database.Close()

	// Auto migrate database (optional, since Python Alembic manages schema)
	// Auto migrate database (split to allow partial success)
	modelsToMigrate := []interface{}{
		&models.Plan{},
		&models.User{},
		&models.APIKey{},
		&models.RefreshToken{},
		&models.RenderJob{},
		&models.Invoice{},
		&models.Webhook{},
		&models.UsageRecord{},
	}

	// HOTFIX: Manually apply migrations for missing columns
	log.Println("Applying manual schema patches...")
	db.Exec("ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(50)")
	db.Exec("ALTER TABLE users ADD COLUMN IF NOT EXISTS provider_id VARCHAR(255)")
	db.Exec("ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255)")
	// db.Exec("ALTER TABLE plans DROP CONSTRAINT IF EXISTS uni_plans_name")

	// Fix legacy NOT NULL constraints from Python migration
	db.Exec("ALTER TABLE users ALTER COLUMN email_verified DROP NOT NULL")
	db.Exec("ALTER TABLE users ALTER COLUMN is_active SET DEFAULT true")

	// Add missing render_jobs columns for geo-tracking and format
	db.Exec("ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45)")
	db.Exec("ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS country_code VARCHAR(2)")
	db.Exec("ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS width INTEGER")
	db.Exec("ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS height INTEGER")
	db.Exec("ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS format VARCHAR(10)")

	for _, model := range modelsToMigrate {
		if err := db.AutoMigrate(model); err != nil {
			log.Printf("Warning: Auto migration failed for %T: %v", model, err)
		}
	}

	// Connect to Redis
	_, err = redis.Connect(cfg.RedisURL)
	if err != nil {
		log.Fatalf("Failed to connect to redis: %v", err)
	}
	defer redis.Close()

	// Initialize Repositories
	jobRepo := repository.NewRenderJobRepository(db)

	// Initialize Services
	cacheService := services.NewCacheService(cfg)
	usageService := services.NewUsageService(cacheService, cfg, db)
	rendererClient := services.NewRendererClient(cfg)
	storageService, err := services.NewStorageService(cfg)
	if err != nil {
		log.Fatalf("Failed to initialize storage service: %v", err)
	}

	authService := services.NewAuthService(db, cfg)
	billingService := services.NewBillingService(db, cfg)
	// Seed Plans
	if err := billingService.SeedPlans(); err != nil {
		log.Printf("Warning: Failed to seed plans: %v", err)
	}

	renderService := services.NewRenderService(rendererClient, storageService, cacheService, usageService, jobRepo, cfg, db)

	// Initialize Job Queue (Redis Streams) for async processing
	jobQueue := services.NewJobQueue(redis.Get())
	renderService.SetQueue(jobQueue)

	// Initialize Queue (create consumer group)
	if err := jobQueue.Initialize(context.Background()); err != nil {
		log.Printf("Warning: Failed to initialize job queue: %v", err)
	}

	// Start background metric updater for job queue
	go jobQueue.StartMetricsUpdater(context.Background())

	// Start Background Worker (async job processor)
	workerCtx, workerCancel := context.WithCancel(context.Background())
	defer workerCancel()

	backgroundWorker := worker.NewWorker(jobQueue, rendererClient, storageService, jobRepo, cfg, db)
	go func() {
		if err := backgroundWorker.Start(workerCtx); err != nil {
			log.Printf("Worker stopped: %v", err)
		}
	}()
	log.Println("Background worker started for async job processing")

	// Initialize Handlers
	renderHandler := handlers.NewRenderHandler(renderService, authService, db)
	authHandler := handlers.NewAuthHandler(authService)
	adminHandler := handlers.NewAdminHandler(db, cfg, billingService)
	usageHandler := handlers.NewUsageHandler(db, cfg, usageService)
	healthHandler := handlers.NewHealthHandler(db, cfg)
	billingHandler := handlers.NewBillingHandler(db, billingService)
	webhooksHandler := handlers.NewWebhooksHandler(db)

	// Create Fiber app with optimized settings for high concurrency
	app := fiber.New(fiber.Config{
		AppName:       "Screenshot API Go",
		CaseSensitive: true,
		StrictRouting: true,
		ServerHeader:  "ScreenshotAPI",
		// High concurrency settings
		Concurrency:           256 * 1024, // Max concurrent connections
		ReadTimeout:           30 * time.Second,
		WriteTimeout:          30 * time.Second,
		IdleTimeout:           120 * time.Second,
		ReadBufferSize:        8192,
		WriteBufferSize:       8192,
		DisableStartupMessage: false,
		ErrorHandler: func(c *fiber.Ctx, err error) error {
			code := fiber.StatusInternalServerError
			message := "Internal Server Error"

			if e, ok := err.(*utils.AppError); ok {
				code = e.Code
				message = e.Message
			} else if e, ok := err.(*fiber.Error); ok {
				code = e.Code
				message = e.Message
			} else {
				log.Printf("Internal Error: %v", err)
			}

			return c.Status(code).JSON(fiber.Map{
				"detail": message,
			})
		},
	})

	// Middleware - Order matters!
	app.Use(middleware.RecoverWithLog()) // Panic recovery with logging

	// Prometheus Metrics (Q019)
	// Use default registry to include custom metrics from other packages
	prometheusMetrics := fiberprometheus.NewWithRegistry(prometheus.DefaultRegisterer, "screenshot_api", "", "", nil)
	prometheusMetrics.RegisterAt(app, "/metrics")
	app.Use(prometheusMetrics.Middleware)

	app.Use(middleware.RequestLogger())    // Structured request logging
	app.Use(middleware.MetricsCollector()) // Basic metrics (legacy, keep for admin endpoint)
	app.Use(middleware.IPRateLimit(cfg))   // Phase 2.1: Global IP-based protection
	// app.Use(cors.New(cors.Config{
	// 	AllowOrigins:     strings.Join(cfg.CORSOrigins, ","),
	// 	AllowHeaders:     "Origin, Content-Type, Accept, X-API-Key, Authorization, X-Request-ID",
	// 	AllowCredentials: true,
	// 	ExposeHeaders:    "X-Processing-Time-Ms, X-Image-Width, X-Image-Height, X-Cache, X-Request-ID",
	// }))
	app.Use(middleware.DatabaseHealthCheck(db)) // EDGE-005: Graceful 503 on DB failure

	// API V1 Config

	api := app.Group("/api/v1")

	// --- PUBLIC ROUTES ---

	// Auth (Public)
	authPublic := api.Group("/auth")
	authPublic.Post("/register", authHandler.Register)
	authPublic.Post("/login", authHandler.Login)
	authPublic.Post("/social-login", authHandler.SocialLogin)
	authPublic.Post("/refresh", authHandler.RefreshToken)
	authPublic.Post("/logout", authHandler.Logout)

	// Demo & Signed
	api.Post("/renders/demo", renderHandler.CreateDemo)
	api.Get("/renders/signed", renderHandler.RenderSigned)
	api.Post("/renders/signed", renderHandler.RenderSigned)

	// Billing (Public routes - must be before protected group)
	api.Get("/billing/plans", billingHandler.ListPlans)
	api.Get("/billing/plans/:id", billingHandler.GetPlan)
	api.Post("/billing/webhook/stripe", billingHandler.StripeWebhook)

	// Webhooks (Public utilities)
	api.Post("/webhooks/verify", webhooksHandler.VerifySignature)
	api.Get("/webhooks/events", webhooksHandler.ListEvents)

	// Health (Public - under API prefix)
	api.Get("/health", healthHandler.Health)
	api.Get("/health/detailed", healthHandler.DetailedHealth)
	api.Get("/health/ready", healthHandler.Ready) // Kubernetes Readiness Probe
	api.Get("/health/live", healthHandler.Live)   // Kubernetes Liveness Probe

	// --- PROTECTED ROUTES ---
	protected := api.Group("/")
	protected.Use(middleware.APIKeyAuth(authService, cfg))
	protected.Use(middleware.UserRateLimit(cfg))

	// Auth (Protected) & Users
	authProtected := protected.Group("/auth")
	authProtected.Post("/api-keys", authHandler.CreateAPIKey)
	authProtected.Get("/api-keys", authHandler.ListAPIKeys)
	authProtected.Delete("/api-keys/:id", authHandler.DeleteAPIKey)
	authProtected.Patch("/api-keys/:id/enforce-signing", authHandler.ToggleEnforceSigning)

	users := protected.Group("/users")
	users.Get("/me", authHandler.GetMe)

	// Admin Routes
	admin := protected.Group("/admin")
	admin.Get("/stats", adminHandler.GetStats)
	admin.Get("/demo-stats", adminHandler.GetDemoStats)
	admin.Get("/users", adminHandler.ListUsers)
	admin.Get("/api-keys", adminHandler.ListAPIKeys)
	admin.Get("/jobs", adminHandler.ListJobs)
	admin.Patch("/users/:id/plan", adminHandler.UpdateUserPlan)
	admin.Get("/users/:id/usage", adminHandler.GetUserUsage)
	admin.Get("/plans", adminHandler.ListPlans)
	admin.Get("/metrics", adminHandler.GetMetrics)

	// Renders
	renders := protected.Group("/renders")
	renders.Get("/", renderHandler.FastScreenshot)
	renders.Get("/take", renderHandler.FastScreenshot) // Alias for playground compatibility
	renders.Post("/screenshot", renderHandler.CreateScreenshot)
	renders.Post("/pdf", renderHandler.CreatePDF)
	renders.Post("/sign-url", renderHandler.SignURL)

	// Jobs
	jobs := protected.Group("/jobs")
	jobs.Post("/", renderHandler.CreateJob)
	jobs.Get("/", renderHandler.ListJobs)
	jobs.Get("/:id", renderHandler.GetJob)
	jobs.Delete("/:id", renderHandler.DeleteJob)

	// Usage
	usage := protected.Group("/usage")
	usage.Get("/current", usageHandler.GetCurrentUsage)
	usage.Get("/stats", usageHandler.GetCurrentUsage) // Alias for parity
	usage.Get("/history", usageHandler.GetUsageHistory)

	// Billing (Protected subscription routes)
	billingProtected := protected.Group("/billing")
	billingProtected.Post("/subscribe", billingHandler.Subscribe)
	billingProtected.Post("/cancel", billingHandler.CancelSubscription)
	billingProtected.Get("/invoices", billingHandler.ListInvoices)

	// Webhooks (Protected CRUD routes)
	webhooks := protected.Group("/webhooks")
	webhooks.Get("/", webhooksHandler.ListWebhooks)
	webhooks.Post("/", webhooksHandler.CreateWebhook)
	webhooks.Get("/:id", webhooksHandler.GetWebhook)
	webhooks.Patch("/:id", webhooksHandler.UpdateWebhook)
	webhooks.Delete("/:id", webhooksHandler.DeleteWebhook)
	webhooks.Post("/:id/rotate-secret", webhooksHandler.RotateSecret)

	// Root health check (Public - outside /api/v1)
	app.Get("/health", healthHandler.Health)

	// === GRACEFUL SHUTDOWN (Q017) ===

	// Channel to listen for OS signals
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt, syscall.SIGTERM, syscall.SIGINT)

	// Start server in goroutine
	go func() {
		log.Printf("Server starting on port %s", cfg.Port)
		if err := app.Listen(":" + cfg.Port); err != nil {
			log.Printf("Server error: %v", err)
		}
	}()

	// Wait for shutdown signal
	sig := <-quit
	log.Printf("Received signal %v. Initiating graceful shutdown...", sig)

	// Shutdown with timeout (allow 30 seconds for in-flight requests)
	shutdownTimeout := 30 * time.Second
	if err := app.ShutdownWithTimeout(shutdownTimeout); err != nil {
		log.Printf("Error during shutdown: %v", err)
	}

	// Cleanup connections
	log.Println("Closing database connection...")
	database.Close()

	log.Println("Closing Redis connection...")
	redis.Close()

	// Flush Sentry
	if cfg.SentryDSN != "" {
		sentry.Flush(2 * time.Second)
	}

	log.Println("Graceful shutdown complete.")
}
