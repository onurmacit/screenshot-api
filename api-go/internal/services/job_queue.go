package services

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/redis/go-redis/v9"
)

const (
	StreamName    = "screenshot:jobs"
	ConsumerGroup = "workers"
	MaxRetries    = 3
)

// JobPayload represents a job in the queue
type JobPayload struct {
	JobID      string          `json:"job_id"`
	Type       string          `json:"type"` // screenshot, pdf
	UserID     string          `json:"user_id"`
	Request    json.RawMessage `json:"request"`
	Priority   int             `json:"priority"` // 0=normal, 1=high
	CreatedAt  time.Time       `json:"created_at"`
	RetryCount int             `json:"retry_count"`
}

// JobHandler is a function that processes a job
type JobHandler func(ctx context.Context, job *JobPayload) error

// JobQueue manages job queue operations using Redis Streams
type JobQueue struct {
	redis      *redis.Client
	streamName string
	groupName  string
}

// NewJobQueue creates a new JobQueue instance
func NewJobQueue(redisClient *redis.Client) *JobQueue {
	return &JobQueue{
		redis:      redisClient,
		streamName: StreamName,
		groupName:  ConsumerGroup,
	}
}

// Initialize creates the consumer group if it doesn't exist
func (q *JobQueue) Initialize(ctx context.Context) error {
	// Try to create consumer group, ignore error if already exists
	err := q.redis.XGroupCreateMkStream(ctx, q.streamName, q.groupName, "0").Err()
	if err != nil && err.Error() != "BUSYGROUP Consumer Group name already exists" {
		return fmt.Errorf("failed to create consumer group: %w", err)
	}
	log.Printf("JobQueue initialized: stream=%s, group=%s", q.streamName, q.groupName)
	return nil
}

// StartMetricsUpdater periodically updates the job queue length metric
func (q *JobQueue) StartMetricsUpdater(ctx context.Context) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			count, err := q.GetPendingCount(ctx)
			if err == nil {
				JobQueueLength.Set(float64(count))
			}
		}
	}
}

// Enqueue adds a job to the queue
func (q *JobQueue) Enqueue(ctx context.Context, job *JobPayload) error {
	// Serialize job to JSON
	jobData, err := json.Marshal(job)
	if err != nil {
		return fmt.Errorf("failed to marshal job: %w", err)
	}

	// Add to stream with auto-generated ID
	_, err = q.redis.XAdd(ctx, &redis.XAddArgs{
		Stream: q.streamName,
		Values: map[string]interface{}{
			"data": string(jobData),
		},
	}).Result()

	if err != nil {
		return fmt.Errorf("failed to enqueue job: %w", err)
	}

	log.Printf("Job enqueued: job_id=%s, type=%s", job.JobID, job.Type)
	return nil
}

// Consume starts consuming jobs from the queue
// This should be run in a goroutine
func (q *JobQueue) Consume(ctx context.Context, consumerName string, handler JobHandler) error {
	log.Printf("Worker started: consumer=%s", consumerName)

	for {
		select {
		case <-ctx.Done():
			log.Printf("Worker stopping: consumer=%s", consumerName)
			return ctx.Err()
		default:
			// Read new messages from the stream
			streams, err := q.redis.XReadGroup(ctx, &redis.XReadGroupArgs{
				Group:    q.groupName,
				Consumer: consumerName,
				Streams:  []string{q.streamName, ">"},
				Count:    1,
				Block:    5 * time.Second,
			}).Result()

			if err != nil {
				if err == redis.Nil {
					// No new messages, continue polling
					continue
				}
				log.Printf("Error reading from stream: %v", err)
				time.Sleep(1 * time.Second)
				continue
			}

			// Process messages
			for _, stream := range streams {
				for _, msg := range stream.Messages {
					if err := q.processMessage(ctx, msg, handler); err != nil {
						log.Printf("Error processing message %s: %v", msg.ID, err)
						// Don't ACK failed messages, they will be redelivered
						continue
					}

					// ACK successful message
					if err := q.Ack(ctx, msg.ID); err != nil {
						log.Printf("Error ACKing message %s: %v", msg.ID, err)
					}
				}
			}
		}
	}
}

// processMessage processes a single message from the queue
func (q *JobQueue) processMessage(ctx context.Context, msg redis.XMessage, handler JobHandler) error {
	// Parse job data
	dataStr, ok := msg.Values["data"].(string)
	if !ok {
		return fmt.Errorf("invalid message format")
	}

	var job JobPayload
	if err := json.Unmarshal([]byte(dataStr), &job); err != nil {
		return fmt.Errorf("failed to unmarshal job: %w", err)
	}

	log.Printf("Processing job: job_id=%s, type=%s, retry=%d", job.JobID, job.Type, job.RetryCount)

	// Call handler
	return handler(ctx, &job)
}

// Ack acknowledges a processed message
func (q *JobQueue) Ack(ctx context.Context, messageID string) error {
	return q.redis.XAck(ctx, q.streamName, q.groupName, messageID).Err()
}

// GetPendingCount returns the number of pending messages in the queue
func (q *JobQueue) GetPendingCount(ctx context.Context) (int64, error) {
	info, err := q.redis.XPending(ctx, q.streamName, q.groupName).Result()
	if err != nil {
		return 0, err
	}
	return info.Count, nil
}

// ClaimStaleMessages reclaims messages that have been pending for too long
// This is useful for recovering from worker crashes
func (q *JobQueue) ClaimStaleMessages(ctx context.Context, consumerName string, minIdleTime time.Duration) ([]redis.XMessage, error) {
	// Find stale messages
	pending, err := q.redis.XPendingExt(ctx, &redis.XPendingExtArgs{
		Stream: q.streamName,
		Group:  q.groupName,
		Start:  "-",
		End:    "+",
		Count:  10,
	}).Result()

	if err != nil {
		return nil, err
	}

	var staleIDs []string
	for _, p := range pending {
		if p.Idle >= minIdleTime {
			staleIDs = append(staleIDs, p.ID)
		}
	}

	if len(staleIDs) == 0 {
		return nil, nil
	}

	// Claim stale messages
	messages, err := q.redis.XClaim(ctx, &redis.XClaimArgs{
		Stream:   q.streamName,
		Group:    q.groupName,
		Consumer: consumerName,
		MinIdle:  minIdleTime,
		Messages: staleIDs,
	}).Result()

	if err != nil {
		return nil, err
	}

	log.Printf("Claimed %d stale messages", len(messages))
	return messages, nil
}
