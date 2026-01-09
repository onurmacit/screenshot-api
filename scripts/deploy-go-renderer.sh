#!/bin/bash
# =============================================================================
# Deploy Script - Go Renderer Hybrid Architecture
# =============================================================================
# Deploys FastAPI + Go Renderer to production Droplet

set -e

SERVER="root@138.197.103.137"
REMOTE_PATH="/opt/screenshot-api"

echo "🚀 Deploying Go Renderer Hybrid Architecture..."
echo "================================================"

# Deploy to server
ssh $SERVER << 'ENDSSH'
set -e

echo "📦 Pulling latest code..."
cd /opt/screenshot-api
git pull origin main

echo "🛑 Stopping old containers..."
docker compose -f docker-compose.api.yml down 2>/dev/null || true
docker compose -f docker-compose.go-renderer.prod.yml down 2>/dev/null || true

echo "🔨 Building new images..."
docker compose -f docker-compose.go-renderer.prod.yml build

echo "🚀 Starting services..."
docker compose -f docker-compose.go-renderer.prod.yml up -d

echo "⏳ Waiting for services to start..."
sleep 25

echo ""
echo "🔍 Health Checks:"
echo "=================="

echo -n "Go Renderer: "
if curl -sf http://localhost:8001/health > /dev/null 2>&1; then
    echo "✅ Healthy"
else
    echo "❌ Failed"
fi

echo -n "FastAPI:     "
if curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo "✅ Healthy"
else
    echo "❌ Failed"
fi

echo ""
echo "📊 Running containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "screenshot|go-renderer|NAMES"

ENDSSH

echo ""
echo "✅ Deployment complete!"
echo "🌐 Test: curl https://screenshotbeam.com/api/v1/renders/demo?url=https://example.com"
