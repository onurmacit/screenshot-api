#!/bin/bash
# =============================================================================
# Screenshot API - Deploy to Worker Droplet
# =============================================================================
# Usage: ./scripts/deploy-worker.sh

set -e

WORKER_HOST="root@167.71.85.169"
PROJECT_NAME="screenshot-api"
REMOTE_DIR="/opt/$PROJECT_NAME"

echo "🚀 Deploying Screenshot API to Worker Droplet..."

# Create remote directory
echo "📁 Creating remote directory..."
ssh $WORKER_HOST "mkdir -p $REMOTE_DIR/docker"

# Sync project files (excluding unnecessary files)
echo "📦 Syncing project files..."
rsync -avz --progress \
    --exclude 'venv' \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.git' \
    --exclude 'node_modules' \
    --exclude '.pytest_cache' \
    --exclude '.ruff_cache' \
    --exclude 'coverage_html' \
    --exclude '.coverage' \
    --exclude 'data' \
    --exclude 'dashboard' \
    --exclude 'tests' \
    --exclude '.env' \
    --exclude '.env.local' \
    ./ $WORKER_HOST:$REMOTE_DIR/

# Copy environment file
echo "🔐 Copying environment file..."
if [ -f ".env.production" ]; then
    scp .env.production $WORKER_HOST:$REMOTE_DIR/.env
else
    echo "⚠️  Warning: .env.production not found! Copy .env.production.template to .env.production and fill in values."
    exit 1
fi

# Build and start containers
echo "🐳 Building and starting containers..."
ssh $WORKER_HOST "cd $REMOTE_DIR && docker compose -f docker-compose.worker.yml build --no-cache"
ssh $WORKER_HOST "cd $REMOTE_DIR && docker compose -f docker-compose.worker.yml up -d"

# Show status
echo "📊 Container status:"
ssh $WORKER_HOST "cd $REMOTE_DIR && docker compose -f docker-compose.worker.yml ps"

echo ""
echo "✅ Worker Deployment complete!"
echo "🔧 Workers are running and connected to Redis queue"
echo ""
echo "📋 Useful commands:"
echo "   - View logs: ssh $WORKER_HOST 'docker logs -f screenshot-worker'"
echo "   - View high priority logs: ssh $WORKER_HOST 'docker logs -f screenshot-worker-high'"
echo "   - Restart workers: ssh $WORKER_HOST 'cd $REMOTE_DIR && docker compose -f docker-compose.worker.yml restart'"
