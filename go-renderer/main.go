package main

import (
	"log"
	"os"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/gofiber/fiber/v2/middleware/recover"

	"github.com/onurmacit/screenshot-api/go-renderer/handlers"
	"github.com/onurmacit/screenshot-api/go-renderer/services"
)

func main() {
	// Initialize browser pool
	poolSize := getEnvInt("BROWSER_POOL_SIZE", 2)
	browserPool := services.NewBrowserPool(poolSize)
	defer browserPool.Close()

	// Initialize renderer service
	renderer := services.NewRenderer(browserPool)

	// Initialize screenshot handler
	screenshotHandler := handlers.NewScreenshotHandler(renderer)

	// Create Fiber app
	app := fiber.New(fiber.Config{
		AppName:      "ScreenshotBeam Go Renderer",
		ServerHeader: "Go-Renderer",
		BodyLimit:    10 * 1024 * 1024, // 10MB
		ReadTimeout:  60 * time.Second,
		WriteTimeout: 60 * time.Second,
		IdleTimeout:  120 * time.Second,
	})

	// Middleware
	app.Use(recover.New())
	app.Use(logger.New(logger.Config{
		Format: "[${time}] ${status} - ${latency} ${method} ${path}\n",
	}))
	app.Use(cors.New())

	// Health check
	app.Get("/health", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{
			"status":  "healthy",
			"service": "go-renderer",
		})
	})

	// Screenshot endpoints
	app.Post("/render/screenshot", screenshotHandler.CaptureScreenshot)
	app.Post("/render/pdf", screenshotHandler.GeneratePDF)

	// Get port from environment
	port := os.Getenv("PORT")
	if port == "" {
		port = "8001"
	}

	log.Printf("🚀 Go Renderer starting on port %s with pool size %d", port, poolSize)
	log.Fatal(app.Listen(":" + port))
}

func getEnvInt(key string, defaultVal int) int {
	val := os.Getenv(key)
	if val == "" {
		return defaultVal
	}
	result := 0
	for _, c := range val {
		if c >= '0' && c <= '9' {
			result = result*10 + int(c-'0')
		}
	}
	if result == 0 {
		return defaultVal
	}
	return result
}
