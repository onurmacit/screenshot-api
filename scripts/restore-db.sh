#!/bin/bash
# =============================================================================
# Screenshot API - Database Restore Script
# =============================================================================
# Restores database from a backup file
# Usage: ./restore-db.sh <backup_file.sql.gz>
# =============================================================================

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    echo "Example: $0 /opt/screenshot-api/backups/screenshot_api_20260107_030000.sql.gz"
    echo ""
    echo "Available local backups:"
    ls -la /opt/screenshot-api/backups/*.sql.gz 2>/dev/null || echo "  No local backups found"
    exit 1
fi

BACKUP_FILE="$1"

# Load environment variables
source /opt/screenshot-api/.env

# Extract database credentials
DB_URL="${DATABASE_URL#postgresql+asyncpg://}"
DB_USER=$(echo "$DB_URL" | cut -d: -f1)
DB_PASS=$(echo "$DB_URL" | cut -d: -f2 | cut -d@ -f1)
DB_HOST=$(echo "$DB_URL" | cut -d@ -f2 | cut -d: -f1)
DB_PORT=$(echo "$DB_URL" | cut -d: -f3 | cut -d/ -f1)
DB_NAME=$(echo "$DB_URL" | cut -d/ -f2)

echo "=== DATABASE RESTORE ==="
echo "Backup file: $BACKUP_FILE"
echo "Target: $DB_HOST:$DB_PORT/$DB_NAME"
echo ""
echo "WARNING: This will OVERWRITE the current database!"
read -p "Are you sure? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo ""
echo "Restoring database..."

# Check if file is remote (S3)
if [[ "$BACKUP_FILE" == s3://* ]]; then
    echo "Downloading from S3..."
    TEMP_FILE="/tmp/restore_$(date +%s).sql.gz"
    AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" \
    AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}" \
    aws s3 cp "$BACKUP_FILE" "$TEMP_FILE" \
        --endpoint-url "${AWS_S3_ENDPOINT_URL}"
    BACKUP_FILE="$TEMP_FILE"
fi

# Restore
gunzip -c "$BACKUP_FILE" | PGPASSWORD="$DB_PASS" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --quiet

echo "Database restored successfully!"
