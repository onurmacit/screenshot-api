package logger

import (
	"log/slog"
	"os"
)

var Logger *slog.Logger

func Init() {
	opts := &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}

	if os.Getenv("APP_ENV") == "production" {
		// JSON logging for production
		handler := slog.NewJSONHandler(os.Stdout, opts)
		Logger = slog.New(handler)
	} else {
		// Text logging for development
		handler := slog.NewTextHandler(os.Stdout, opts)
		Logger = slog.New(handler)
	}

	Logger.Info("Logger initialized",
		"env", os.Getenv("APP_ENV"),
		"version", os.Getenv("VERSION"),
	)
}

// Convenience methods
func Info(msg string, args ...any) {
	Logger.Info(msg, args...)
}

func Error(msg string, args ...any) {
	Logger.Error(msg, args...)
}

func Warn(msg string, args ...any) {
	Logger.Warn(msg, args...)
}

func Debug(msg string, args ...any) {
	Logger.Debug(msg, args...)
}

// WithContext returns logger with additional context
func WithContext(args ...any) *slog.Logger {
	return Logger.With(args...)
}
