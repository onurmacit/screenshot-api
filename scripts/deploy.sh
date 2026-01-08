#!/bin/bash
# =============================================================================
# Screenshot API - Production Deploy Script
# =============================================================================
# Usage: ./scripts/deploy.sh
#
# This script performs a safe, repeatable deployment:
# 1. SSH to production server
# 2. Pull latest code from git
# 3. Rebuild Docker image (CRITICAL - ensures new code is used)
# 4. Restart container with new image
# 5. Verify deployment with health check
# =============================================================================

set -e  # Exit on any error

# Configuration
SERVER_IP="138.197.103.137"
SERVER_USER="root"
PROJECT_DIR="/opt/screenshot-api"
COMPOSE_FILE="docker-compose.api.yml"
SERVICE_NAME="api"
HEALTH_ENDPOINT="http://localhost:8080/api/v1/health"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 Starting production deployment...${NC}"

# Deploy via SSH
ssh ${SERVER_USER}@${SERVER_IP} << EOF
    set -e
    
    echo "📂 Changing to project directory..."
    cd ${PROJECT_DIR}
    
    echo "📥 Pulling latest code from git..."
    git pull origin main
    
    echo "🔨 Building Docker image (this ensures new code is used)..."
    docker compose -f ${COMPOSE_FILE} build ${SERVICE_NAME}
    
    echo "🔄 Restarting container with new image..."
    docker compose -f ${COMPOSE_FILE} up -d ${SERVICE_NAME}
    
    echo "⏳ Waiting for container to start (15 seconds)..."
    sleep 15
    
    echo "🏥 Running health check..."
    if curl -sf ${HEALTH_ENDPOINT} > /dev/null; then
        echo "✅ Health check passed!"
    else
        echo "❌ Health check failed!"
        docker logs screenshot-api --tail 20
        exit 1
    fi
    
    echo ""
    echo "📊 Container status:"
    docker ps --filter name=screenshot-api --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    echo ""
    echo "🔍 Verifying code version in container..."
    docker exec screenshot-api cat /app/VERSION 2>/dev/null || echo "(no VERSION file)"
EOF

echo ""
echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo ""
echo "Next steps:"
echo "  - Check Sentry for any new errors"
echo "  - Test the API endpoints"
echo "  - Monitor logs: ssh ${SERVER_USER}@${SERVER_IP} 'docker logs -f screenshot-api'"
