package main

import (
	"log"
	"strings"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"

	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/handlers"
	"github.com/onurmacit/screenshot-api/api-go/internal/middleware"
	"github.com/onurmacit/screenshot-api/api-go/internal/repository"
	"github.com/onurmacit/screenshot-api/api-go/internal/services"
	"github.com/onurmacit/screenshot-api/api-go/internal/utils"
	"github.com/onurmacit/screenshot-api/api-go/pkg/database"
	"github.com/onurmacit/screenshot-api/api-go/pkg/redis"

	"github.com/getsentry/sentry-go"
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
	// if err := db.AutoMigrate(&models.User{}, &models.APIKey{}, &models.RenderJob{}); err != nil {
	// 	log.Printf("Warning: Auto migration failed: %v", err)
	// }

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

	// Initialize Handlers
	renderHandler := handlers.NewRenderHandler(renderService, authService)
	authHandler := handlers.NewAuthHandler(authService)
	adminHandler := handlers.NewAdminHandler(db, cfg, billingService)
	usageHandler := handlers.NewUsageHandler(db, cfg, usageService)
	healthHandler := handlers.NewHealthHandler(db)
	billingHandler := handlers.NewBillingHandler(db, billingService)
	webhooksHandler := handlers.NewWebhooksHandler(db)

	// Create Fiber app
	app := fiber.New(fiber.Config{
		AppName:       "Screenshot API Go",
		CaseSensitive: true,
		StrictRouting: true,
		ServerHeader:  "ScreenshotAPI",
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
	app.Use(middleware.RecoverWithLog())   // Panic recovery with logging
	app.Use(middleware.RequestLogger())    // Structured request logging
	app.Use(middleware.MetricsCollector()) // Basic metrics
	app.Use(middleware.IPRateLimit(cfg))   // Phase 2.1: Global IP-based protection
	app.Use(cors.New(cors.Config{
		AllowOrigins:     strings.Join(cfg.CORSOrigins, ","),
		AllowHeaders:     "Origin, Content-Type, Accept, X-API-Key, Authorization, X-Request-ID",
		AllowCredentials: true,
		ExposeHeaders:    "X-Processing-Time-Ms, X-Image-Width, X-Image-Height, X-Cache, X-Request-ID",
	}))
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
	admin.Get("/users", adminHandler.ListUsers)
	admin.Patch("/users/:id/plan", adminHandler.UpdateUserPlan)
	admin.Get("/users/:id/usage", adminHandler.GetUserUsage)
	admin.Get("/plans", adminHandler.ListPlans)
	admin.Get("/metrics", adminHandler.GetMetrics)

	// Renders
	renders := protected.Group("/renders")
	renders.Get("/", renderHandler.FastScreenshot)
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

	// Start server
	log.Printf("Server starting on port %s", cfg.Port)
	if err := app.Listen(":" + cfg.Port); err != nil {
		log.Fatalf("Server failed to start: %v", err)
	}
}
