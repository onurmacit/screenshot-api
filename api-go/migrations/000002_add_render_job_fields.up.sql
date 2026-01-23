-- Add missing render_jobs columns and fix constraints
-- This migration syncs the database with the GORM model

BEGIN;

-- Core tracking fields
ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS last_error TEXT;
ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;
ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS error_message TEXT;

-- S3 storage fields
ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS s3_key TEXT;
ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS s3_url TEXT;

-- Webhook integration
ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS webhook_url TEXT;

-- Timing fields
ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS started_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;

-- Performance metrics
ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS processing_time_ms INTEGER;
ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT;

-- Job priority and metadata
ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 5;
ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS result JSONB;
ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS options JSONB;

-- Geo-tracking
ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45);
ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS country_code VARCHAR(2);

-- Screenshot dimensions
ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS width INTEGER;
ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS height INTEGER;
ALTER TABLE render_jobs ADD COLUMN IF NOT EXISTS format VARCHAR(10);

-- Fix NOT NULL constraints that cause issues
ALTER TABLE render_jobs ALTER COLUMN options DROP NOT NULL;
ALTER TABLE render_jobs ALTER COLUMN result DROP NOT NULL;
ALTER TABLE render_jobs ALTER COLUMN max_retries DROP NOT NULL;
ALTER TABLE render_jobs ALTER COLUMN retry_count DROP NOT NULL;
ALTER TABLE render_jobs ALTER COLUMN webhook_sent DROP NOT NULL;
ALTER TABLE render_jobs ALTER COLUMN webhook_attempts DROP NOT NULL;
ALTER TABLE render_jobs ALTER COLUMN priority DROP NOT NULL;

-- Set sensible defaults
ALTER TABLE render_jobs ALTER COLUMN max_retries SET DEFAULT 3;
ALTER TABLE render_jobs ALTER COLUMN retry_count SET DEFAULT 0;
ALTER TABLE render_jobs ALTER COLUMN webhook_sent SET DEFAULT false;
ALTER TABLE render_jobs ALTER COLUMN webhook_attempts SET DEFAULT 0;
ALTER TABLE render_jobs ALTER COLUMN priority SET DEFAULT 5;

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_render_jobs_user_created ON render_jobs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_render_jobs_status ON render_jobs(status) WHERE status != 'completed';
CREATE INDEX IF NOT EXISTS idx_render_jobs_ip_country ON render_jobs(ip_address, country_code) WHERE ip_address IS NOT NULL;

COMMIT;
