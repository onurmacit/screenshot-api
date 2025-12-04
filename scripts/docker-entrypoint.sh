#!/bin/bash
# =============================================================================
# Screenshot API - Docker Entrypoint Script
# =============================================================================

set -e

# Print environment info
echo "Starting Screenshot API..."
echo "Environment: ${APP_ENV:-development}"
echo "Python: $(python --version)"

# Wait for services
wait_for_service() {
    local host="$1"
    local port="$2"
    local name="$3"
    local timeout="${4:-30}"
    local count=0
    
    echo "Waiting for $name ($host:$port)..."
    
    while ! nc -z "$host" "$port" 2>/dev/null; do
        count=$((count + 1))
        if [ "$count" -ge "$timeout" ]; then
            echo "ERROR: Timeout waiting for $name"
            exit 1
        fi
        sleep 1
    done
    
    echo "$name is ready!"
}

# Wait for PostgreSQL
if [ -n "$DATABASE_URL" ]; then
    # Extract host and port from DATABASE_URL
    DB_HOST=$(echo "$DATABASE_URL" | sed -E 's/.*@([^:]+).*/\1/')
    DB_PORT=$(echo "$DATABASE_URL" | sed -E 's/.*:([0-9]+)\/.*/\1/')
    wait_for_service "$DB_HOST" "$DB_PORT" "PostgreSQL"
fi

# Wait for Redis
if [ -n "$REDIS_URL" ]; then
    REDIS_HOST=$(echo "$REDIS_URL" | sed -E 's/redis:\/\/([^:]+).*/\1/')
    REDIS_PORT=$(echo "$REDIS_URL" | sed -E 's/.*:([0-9]+).*/\1/')
    wait_for_service "$REDIS_HOST" "$REDIS_PORT" "Redis"
fi

# Run migrations if this is the API service
if [ "$1" = "api" ]; then
    echo "Running database migrations..."
    alembic upgrade head
    
    echo "Starting API server..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "${@:2}"

elif [ "$1" = "worker" ]; then
    echo "Starting Celery worker..."
    exec celery -A app.workers.celery_app worker "${@:2}"

elif [ "$1" = "beat" ]; then
    echo "Starting Celery beat..."
    exec celery -A app.workers.celery_app beat "${@:2}"

elif [ "$1" = "flower" ]; then
    echo "Starting Flower..."
    exec celery -A app.workers.celery_app flower "${@:2}"

else
    # Run command as-is
    exec "$@"
fi

