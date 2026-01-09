#!/bin/bash
# =============================================================================
# Deploy Script - Distributed Hybrid Architecture
# =============================================================================
# Usage: ./scripts/deploy-hybrid.sh
# Method: Push-based (tar | ssh) to bypass git auth issues on servers

set -e

WORKER_1_DROPLET="root@167.71.85.169"
WORKER_2_DROPLET="root@161.35.129.129"
API_DROPLET="root@138.197.103.137"
REMOTE_PATH="/opt/screenshot-api"

echo "🚀 Deploying Distributed Hybrid Architecture..."
echo "================================================="
echo "📍 Method: Direct Code Push (Local -> Server)"
echo "📍 Workers: 2 (Load Balanced)"
echo ""

# -----------------------------------------------------------------------------
# Helper Function: Sync Code
# -----------------------------------------------------------------------------
sync_code() {
    local target=$1
    echo "   -> Syncing code to $target..."
    
    # Create remote dir
    ssh $target "mkdir -p $REMOTE_PATH"
    
    # Tar local files and extract on remote
    # Excludes heavy/unnecessary folders
    tar czf - \
        --exclude='.git' \
        --exclude='.github' \
        --exclude='.idea' \
        --exclude='.vscode' \
        --exclude='node_modules' \
        --exclude='venv' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='metrics_data' \
        --exclude='prometheus_data' \
        --exclude='alertmanager_data' \
        . | ssh $target "cd $REMOTE_PATH && tar xzf -"
        
    echo "   ✅ Code synced."
}

# -----------------------------------------------------------------------------
# 1. Deploy Review
# -----------------------------------------------------------------------------
read -p "⚠️  Are you sure you want to deploy to PRODUCTION? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Deployment cancelled."
    exit 1
fi

# -----------------------------------------------------------------------------
# 2. Deploy Worker 1 (Go Renderer)
# -----------------------------------------------------------------------------
echo ""
echo "📦 [1/3] Deploying Worker 1 (Go Renderer)..."

sync_code $WORKER_1_DROPLET

ssh $WORKER_1_DROPLET << 'ENDSSH'
set -e
cd /opt/screenshot-api

echo "   -> Building Go Renderer..."
docker compose -f docker-compose.worker-renderer.prod.yml build

echo "   -> Starting Go Renderer..."
docker compose -f docker-compose.worker-renderer.prod.yml up -d

echo "   -> Health check..."
sleep 5
if curl -sf http://localhost:8001/health > /dev/null; then
    echo "   ✅ Worker 1 Go Renderer is healthy!"
else
    echo "   ❌ Health check failed!"
    docker logs screenshot-go-renderer
    exit 1
fi
ENDSSH

# -----------------------------------------------------------------------------
# 3. Deploy Worker 2 (Go Renderer)
# -----------------------------------------------------------------------------
echo ""
echo "📦 [2/3] Deploying Worker 2 (Go Renderer)..."

sync_code $WORKER_2_DROPLET

ssh $WORKER_2_DROPLET << 'ENDSSH'
set -e
cd /opt/screenshot-api

echo "   -> Building Go Renderer..."
docker compose -f docker-compose.worker-renderer.prod.yml build

echo "   -> Starting Go Renderer..."
docker compose -f docker-compose.worker-renderer.prod.yml up -d

echo "   -> Health check..."
sleep 5
if curl -sf http://localhost:8001/health > /dev/null; then
    echo "   ✅ Worker 2 Go Renderer is healthy!"
else
    echo "   ❌ Health check failed!"
    docker logs screenshot-go-renderer
    exit 1
fi
ENDSSH

# -----------------------------------------------------------------------------
# 4. Deploy API Droplet (FastAPI)
# -----------------------------------------------------------------------------
echo ""
echo "📦 [3/3] Deploying API Droplet (FastAPI Gateway)..."

sync_code $API_DROPLET

ssh $API_DROPLET << 'ENDSSH'
set -e
cd /opt/screenshot-api

echo "   -> Stopping old services..."
docker compose -f docker-compose.api.yml down 2>/dev/null || true

echo "   -> Building API..."
docker compose -f docker-compose.api.hybrid.prod.yml build

echo "   -> Starting API..."
docker compose -f docker-compose.api.hybrid.prod.yml up -d

echo "   -> Health check..."
sleep 15
if curl -sf http://localhost:8000/api/v1/health > /dev/null; then
    echo "   ✅ API is healthy!"
else
    echo "   ❌ Health check failed!"
    docker logs screenshot-api
    exit 1
fi
ENDSSH

echo ""
echo "✅ Deployment complete!"
echo "🌐 Verify: curl https://screenshotbeam.com/api/v1/renders/demo?url=https://stripe.com"
