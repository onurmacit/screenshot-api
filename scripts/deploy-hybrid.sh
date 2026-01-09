#!/bin/bash
# =============================================================================
# Deploy Script - Distributed Hybrid Architecture
# =============================================================================
# Deploys Go Renderer to Worker Droplet (167.71.85.169)
# Deploys FastAPI Gateway to API Droplet (138.197.103.137)

set -e

WORKER_DROPLET="root@167.71.85.169"
API_DROPLET="root@138.197.103.137"
REMOTE_PATH="/opt/screenshot-api"

echo "🚀 Deploying Distributed Hybrid Architecture..."
echo "================================================="

# -----------------------------------------------------------------------------
# 1. Deploy Review
# -----------------------------------------------------------------------------
echo ""
echo "📍 Worker Droplet ($WORKER_DROPLET):"
echo "   - Go Renderer (Pool Size: 6)"
echo "   - Port: 8001"
echo ""
echo "📍 API Droplet ($API_DROPLET):"
echo "   - FastAPI Gateway"
echo "   - Nginx (SSL)"
echo "   - Prometheus"
echo "   - Alertmanager"
echo "   - Connects to: http://167.71.85.169:8001"
echo ""
read -p "⚠️  Are you sure you want to deploy to PRODUCTION? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Deployment cancelled."
    exit 1
fi

# -----------------------------------------------------------------------------
# 2. Deploy Worker Droplet (Go Renderer)
# -----------------------------------------------------------------------------
echo ""
echo "📦 [1/2] Deploying Worker Droplet (Go Renderer)..."
ssh $WORKER_DROPLET << 'ENDSSH'
set -e
mkdir -p /opt/screenshot-api
cd /opt/screenshot-api

echo "   -> Pulling latest code..."
git pull origin main || git clone https://github.com/onurmacit/screenshot-api.git .

echo "   -> Cleaning up old Celery workers..."
docker compose -f docker-compose.worker.yml down 2>/dev/null || true
docker rm -f screenshotbeam-celery-worker 2>/dev/null || true

echo "   -> Building Go Renderer..."
docker compose -f docker-compose.worker-renderer.prod.yml build

echo "   -> Starting Go Renderer..."
docker compose -f docker-compose.worker-renderer.prod.yml up -d

echo "   -> Health check..."
sleep 5
if curl -sf http://localhost:8001/health > /dev/null; then
    echo "   ✅ Go Renderer is healthy!"
else
    echo "   ❌ Health check failed!"
    exit 1
fi
ENDSSH

# -----------------------------------------------------------------------------
# 3. Deploy API Droplet (FastAPI)
# -----------------------------------------------------------------------------
echo ""
echo "📦 [2/2] Deploying API Droplet (FastAPI Gateway)..."
ssh $API_DROPLET << 'ENDSSH'
set -e
cd /opt/screenshot-api

echo "   -> Pulling latest code..."
git pull origin main

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
    exit 1
fi
ENDSSH

echo ""
echo "✅ Deployment complete!"
echo "🌐 Verify: curl https://screenshotbeam.com/api/v1/renders/demo?url=https://stripe.com"
