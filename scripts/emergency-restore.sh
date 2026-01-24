#!/bin/bash
# Emergency Restore Script
# Use when complete service failure occurs

set -e

# UPDATE THIS with your last known good version
LAST_GOOD_VERSION=${1:-"latest"}

echo "====================================="
echo "🚨 EMERGENCY RESTORE"
echo "====================================="
echo ""
echo "This will:"
echo "1. Stop all API containers"
echo "2. Pull last known good version: $LAST_GOOD_VERSION"
echo "3. Start emergency container"
echo ""

read -p "Are you sure? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 1
fi

echo ""
echo "Step 1: Stopping all API containers"
docker stop $(docker ps -aq --filter "name=api-go") 2>/dev/null || true
echo "✓ Containers stopped"

echo ""
echo "Step 2: Pulling image $LAST_GOOD_VERSION"
docker pull ghcr.io/onurmacit/screenshot-api-go:$LAST_GOOD_VERSION
echo "✓ Image pulled"

echo ""
echo "Step 3: Starting emergency container"
docker run -d \
  --name api-go-emergency \
  --restart unless-stopped \
  --env-file /root/deploy/api/.env.production \
  -e APP_ENV=production \
  -e INSTANCE_COLOR=emergency \
  -p 127.0.0.1:8080:8080 \
  --memory=512m \
  --health-cmd="wget --no-verbose --tries=1 --spider http://localhost:8080/api/v1/health || exit 1" \
  --health-interval=10s \
  --health-timeout=5s \
  --health-retries=3 \
  ghcr.io/onurmacit/screenshot-api-go:$LAST_GOOD_VERSION
echo "✓ Container started"

echo ""
echo "Step 4: Waiting for health check"
sleep 15

HEALTH=$(curl -s http://localhost:8080/api/v1/health | jq -r .status)
if [ "$HEALTH" = "healthy" ]; then
  echo "✓ Health check passed"
else
  echo "❌ Health check failed"
  docker logs api-go-emergency --tail 50
  exit 1
fi

echo ""
echo "Step 5: Update Nginx to point to emergency container"
echo "Run: sed -i 's/api-go-blue:8080/api-go-emergency:8080/' /root/deploy/api/docker/nginx-blue-green.conf"
echo "Then: docker exec screenshot-nginx nginx -s reload"

echo ""
echo "====================================="
echo "✅ Emergency container is running!"
echo "====================================="
echo ""
echo "Container: api-go-emergency"
echo "Port: 8080"
echo ""
echo "Next steps:"
echo "1. Verify service is working"
echo "2. Investigate root cause"
echo "3. Deploy proper fix"
echo "4. Remove emergency container and switch back to blue/green"
