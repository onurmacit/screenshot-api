package main

import (
	"log"
	"strings"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/gofiber/fiber/v2/middleware/recover"

	"github.com/onurmacit/screenshot-api/api-go/internal/config"
	"github.com/onurmacit/screenshot-api/api-go/internal/handlers"
	"github.com/onurmacit/screenshot-api/api-go/internal/middleware"
	"github.com/onurmacit/screenshot-api/api-go/internal/repository"
	"github.com/onurmacit/screenshot-api/api-go/internal/services"
	"github.com/onurmacit/screenshot-api/api-go/internal/utils"
	"github.com/onurmacit/screenshot-api/api-go/pkg/database"
	"github.com/onurmacit/screenshot-api/api-go/pkg/redis"
)

func main() {
	// Load configuration
	cfg := config.Load()

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
	renderService := services.NewRenderService(rendererClient, storageService, cacheService, usageService, jobRepo, cfg, db)

	// Initialize Handlers
	renderHandler := handlers.NewRenderHandler(renderService, authService)
	authHandler := handlers.NewAuthHandler(authService)
	adminHandler := handlers.NewAdminHandler(db, cfg)

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
				"error":   true,
				"message": message,
			})
		},
	})

	// Middleware
	app.Use(recover.New())
	app.Use(logger.New())
	app.Use(cors.New(cors.Config{
		AllowOrigins:     strings.Join(cfg.CORSOrigins, ","),
		AllowHeaders:     "Origin, Content-Type, Accept, X-API-Key, Authorization",
		AllowCredentials: true,
		ExposeHeaders:    "X-Processing-Time-Ms, X-Image-Width, X-Image-Height, X-Cache",
	}))

	// API V1 Config
	api := app.Group("/api/v1")

	// Public Routes
	api.Post("/renders/demo", renderHandler.CreateDemo)

	// Protected Routes
	api.Use(middleware.APIKeyAuth(authService, cfg))

	// Admin Routes
	admin := api.Group("/admin")
	admin.Get("/stats", adminHandler.GetStats)
	admin.Get("/users", adminHandler.ListUsers)
	admin.Get("/users/:id/usage", adminHandler.GetUserUsage)

	// Auth Routes (API Keys)
	auth := api.Group("/auth")
	auth.Post("/api-keys", authHandler.CreateAPIKey)
	auth.Get("/api-keys", authHandler.ListAPIKeys)
	auth.Delete("/api-keys/:id", authHandler.DeleteAPIKey)

	// Public Routes (Webhooks)
	// webhooks := app.Group("/webhooks")
	// webhooks.Post("/stripe", webhookHandler.HandleStripe)

	renders := api.Group("/renders")
	renders.Get("/", renderHandler.FastScreenshot)
	renders.Post("/screenshot", renderHandler.CreateScreenshot)
	renders.Post("/pdf", renderHandler.CreatePDF)
	renders.Post("/sign-url", renderHandler.SignURL)
	renders.Get("/signed", renderHandler.RenderSigned)  // Support GET
	renders.Post("/signed", renderHandler.RenderSigned) // Support POST

	jobs := api.Group("/jobs")
	jobs.Post("/", renderHandler.CreateJob)
	jobs.Get("/", renderHandler.ListJobs)
	jobs.Delete("/:id", renderHandler.DeleteJob)

	// Health Check
	app.Get("/health", func(c *fiber.Ctx) error {
		sqlDB, err := db.DB()
		dbStatus := "connected"
		if err != nil || sqlDB.Ping() != nil {
			dbStatus = "disconnected"
		}

		return c.Status(fiber.StatusOK).JSON(fiber.Map{
			"status":   "healthy",
			"env":      cfg.AppEnv,
			"database": dbStatus,
		})
	})

	// Start server
	log.Printf("Server starting on port %s", cfg.Port)
	if err := app.Listen(":" + cfg.Port); err != nil {
		log.Fatalf("Server failed to start: %v", err)
	}
}
