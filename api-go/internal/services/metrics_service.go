package services

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	// CircuitBreakerState represents the current state of the renderer circuit breaker
	// 0 = closed, 1 = open, 2 = half-open
	CircuitBreakerState = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "renderer_circuit_breaker_state",
		Help: "Current state of the renderer circuit breaker (0:closed, 1:open, 2:half-open)",
	})

	// JobQueueLength represents the number of pending jobs in Redis Streams
	JobQueueLength = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "job_queue_length",
		Help: "Number of pending jobs in the Redis Streams queue",
	})

	// JobProcessingErrors tracks the number of job processing failures
	JobProcessingErrors = promauto.NewCounter(prometheus.CounterOpts{
		Name: "job_processing_errors_total",
		Help: "Total number of background job processing errors",
	})

	// RendererLatency Summary
	RendererLatency = promauto.NewSummary(prometheus.SummaryOpts{
		Name:       "renderer_request_duration_seconds",
		Help:       "Duration of requests to the renderer service",
		Objectives: map[float64]float64{0.5: 0.05, 0.9: 0.01, 0.99: 0.001},
	})
)
