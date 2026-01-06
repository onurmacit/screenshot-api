#!/bin/bash
# =============================================================================
# Screenshot API - Database Backup Script
# =============================================================================
# Backs up Supabase PostgreSQL to DigitalOcean Spaces
# Run via cron: 0 3 * * * /opt/screenshot-api/scripts/backup-db.sh
# =============================================================================

set -e

# Configuration
BACKUP_DIR="/opt/screenshot-api/backups"
RETENTION_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="screenshot_api_${TIMESTAMP}.sql.gz"

# Load environment variables
source /opt/screenshot-api/.env

# Extract database credentials from DATABASE_URL
# Format: postgresql+asyncpg://user:pass@host:port/dbname
DB_URL="${DATABASE_URL#postgresql+asyncpg://}"
DB_USER=$(echo "$DB_URL" | cut -d: -f1)
DB_PASS=$(echo "$DB_URL" | cut -d: -f2 | cut -d@ -f1)
DB_HOST=$(echo "$DB_URL" | cut -d@ -f2 | cut -d: -f1)
DB_PORT=$(echo "$DB_URL" | cut -d: -f3 | cut -d/ -f1)
DB_NAME=$(echo "$DB_URL" | cut -d/ -f2)

# S3 Configuration (DO Spaces)
S3_BUCKET="${AWS_S3_BUCKET}"
S3_ENDPOINT="${AWS_S3_ENDPOINT_URL}"
S3_BACKUP_PATH="backups/database"

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting database backup..."

# Create backup directory if not exists
mkdir -p "$BACKUP_DIR"

# Perform backup (use PostgreSQL 17 pg_dump to match Supabase server)
log "Dumping database to $BACKUP_FILE..."
PGPASSWORD="$DB_PASS" /usr/lib/postgresql/17/bin/pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    | gzip > "$BACKUP_DIR/$BACKUP_FILE"

BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
log "Backup created: $BACKUP_FILE (${BACKUP_SIZE})"

# Upload to DO Spaces
log "Uploading to DO Spaces..."
AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" \
AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}" \
aws s3 cp "$BACKUP_DIR/$BACKUP_FILE" \
    "s3://${S3_BUCKET}/${S3_BACKUP_PATH}/${BACKUP_FILE}" \
    --endpoint-url "$S3_ENDPOINT" \
    --quiet

log "Uploaded to s3://${S3_BUCKET}/${S3_BACKUP_PATH}/${BACKUP_FILE}"

# Clean up old local backups
log "Cleaning up local backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_DIR" -name "screenshot_api_*.sql.gz" -mtime +$RETENTION_DAYS -delete

# Clean up old S3 backups
log "Cleaning up S3 backups older than ${RETENTION_DAYS} days..."
CUTOFF_DATE=$(date -d "-${RETENTION_DAYS} days" +%Y%m%d 2>/dev/null || date -v-${RETENTION_DAYS}d +%Y%m%d)

AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" \
AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}" \
aws s3 ls "s3://${S3_BUCKET}/${S3_BACKUP_PATH}/" \
    --endpoint-url "$S3_ENDPOINT" \
    | while read -r line; do
        FILE=$(echo "$line" | awk '{print $4}')
        if [[ -n "$FILE" ]]; then
            FILE_DATE=$(echo "$FILE" | grep -oE '[0-9]{8}' | head -1)
            if [[ -n "$FILE_DATE" && "$FILE_DATE" < "$CUTOFF_DATE" ]]; then
                log "Deleting old backup: $FILE"
                AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" \
                AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}" \
                aws s3 rm "s3://${S3_BUCKET}/${S3_BACKUP_PATH}/${FILE}" \
                    --endpoint-url "$S3_ENDPOINT" \
                    --quiet
            fi
        fi
    done

log "Backup completed successfully!"
log "Local: $BACKUP_DIR/$BACKUP_FILE"
log "Remote: s3://${S3_BUCKET}/${S3_BACKUP_PATH}/${BACKUP_FILE}"

# Exit success
exit 0
