package config

import (
	"os"
	"strconv"
	"time"
)

// SelectorConfig holds configuration for selector capture operations
type SelectorConfig struct {
	FindTimeout   time.Duration
	StableTimeout time.Duration
	ScrollDelay   time.Duration
	MaxRetries    int
	RetryBackoff  time.Duration
}

// LoadSelectorConfig loads selector configuration from environment variables
func LoadSelectorConfig() SelectorConfig {
	return SelectorConfig{
		FindTimeout:   getDuration("SELECTOR_FIND_TIMEOUT", 10*time.Second),
		StableTimeout: getDuration("SELECTOR_STABLE_TIMEOUT", 500*time.Millisecond),
		ScrollDelay:   getDuration("SELECTOR_SCROLL_DELAY", 100*time.Millisecond),
		MaxRetries:    getInt("SELECTOR_MAX_RETRIES", 2),
		RetryBackoff:  getDuration("SELECTOR_RETRY_BACKOFF", 200*time.Millisecond),
	}
}

func getDuration(key string, def time.Duration) time.Duration {
	if v := os.Getenv(key); v != "" {
		if d, err := time.ParseDuration(v); err == nil {
			return d
		}
	}
	return def
}

func getInt(key string, def int) int {
	if v := os.Getenv(key); v != "" {
		if i, err := strconv.Atoi(v); err == nil {
			return i
		}
	}
	return def
}
