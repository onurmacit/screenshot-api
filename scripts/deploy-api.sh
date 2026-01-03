#!/bin/bash
# =============================================================================
# Screenshot API - Deploy to API Droplet
# =============================================================================
# Usage: ./scripts/deploy-api.sh

set -e

API_HOST="root@138.197.103.137"
PROJECT_NAME="screenshot-api"
REMOTE_DIR="/opt/$PROJECT_NAME"

echo "🚀 Deploying Screenshot API to API Droplet..."

# Create remote directory
echo "📁 Creating remote directory..."
ssh $API_HOST "mkdir -p $REMOTE_DIR/docker"

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
    ./ $API_HOST:$REMOTE_DIR/

# Copy environment file
echo "🔐 Copying environment file..."
if [ -f ".env.production" ]; then
    scp .env.production $API_HOST:$REMOTE_DIR/.env
else
    echo "⚠️  Warning: .env.production not found! Copy .env.production.template to .env.production and fill in values."
    exit 1
fi

# Build and start containers
echo "🐳 Building and starting containers..."
ssh $API_HOST "cd $REMOTE_DIR && docker compose -f docker-compose.api.yml build --no-cache"
ssh $API_HOST "cd $REMOTE_DIR && docker compose -f docker-compose.api.yml up -d"

# Show status
echo "📊 Container status:"
ssh $API_HOST "cd $REMOTE_DIR && docker compose -f docker-compose.api.yml ps"

echo ""
echo "✅ API Deployment complete!"
echo "🌐 API is running at: http://138.197.103.137:8000"
echo ""
echo "📋 Next steps:"
echo "   1. Set up SSL with: ssh $API_HOST 'certbot --nginx -d api.yourdomain.com'"
echo "   2. Update DNS to point to 138.197.103.137"
