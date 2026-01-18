package redis

import (
	"context"
	"log"
	"time"

	"github.com/redis/go-redis/v9"
)

var client *redis.Client

func Connect(redisURL string) (*redis.Client, error) {
	opts, err := redis.ParseURL(redisURL)
	if err != nil {
		return nil, err
	}

	// Connection pool settings for high concurrency
	opts.PoolSize = 100    // Max connections in pool
	opts.MinIdleConns = 10 // Minimum idle connections
	opts.PoolTimeout = 30 * time.Second
	opts.ReadTimeout = 5 * time.Second
	opts.WriteTimeout = 5 * time.Second

	client = redis.NewClient(opts)

	// Verify connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := client.Ping(ctx).Err(); err != nil {
		return nil, err
	}

	log.Printf("Redis connected successfully (pool size: %d)", opts.PoolSize)
	return client, nil
}

func Get() *redis.Client {
	return client
}

func Close() error {
	if client != nil {
		return client.Close()
	}
	return nil
}
