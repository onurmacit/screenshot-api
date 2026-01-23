-- Rollback: Remove columns added in 000002
-- Note: This is destructive and will lose data

BEGIN;

DROP INDEX IF EXISTS idx_render_jobs_ip_country;
DROP INDEX IF EXISTS idx_render_jobs_status;
DROP INDEX IF EXISTS idx_render_jobs_user_created;

ALTER TABLE render_jobs DROP COLUMN IF EXISTS format;
ALTER TABLE render_jobs DROP COLUMN IF EXISTS height;
ALTER TABLE render_jobs DROP COLUMN IF EXISTS width;
ALTER TABLE render_jobs DROP COLUMN IF EXISTS country_code;
ALTER TABLE render_jobs DROP COLUMN IF EXISTS ip_address;
ALTER TABLE render_jobs DROP COLUMN IF EXISTS last_error;

COMMIT;
