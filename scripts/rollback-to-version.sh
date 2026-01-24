#!/bin/bash
set -e

VERSION=$1

if [ -z "$VERSION" ]; then
  echo "Usage: $0 <version>"
  echo ""
  echo "Example: $0 20240123-abc1234"
  echo ""
  echo "Available versions:"
  docker images ghcr.io/onurmacit/screenshot-api-go --format "{{.Tag}}" | head -10
  exit 1
fi

echo "====================================="
echo "Rolling back to version: $VERSION"
echo "====================================="
echo ""

# Pull specific version
echo "Step 1: Pulling image version $VERSION"
docker pull ghcr.io/onurmacit/screenshot-api-go:$VERSION
docker tag ghcr.io/onurmacit/screenshot-api-go:$VERSION screenshot-api-go:rollback

# Determine target color
if docker ps | grep -q api-go-blue.*Up; then
  TARGET_COLOR="green"
  TARGET_PORT=8081
else
  TARGET_COLOR="blue"
  TARGET_PORT=8080
fi

echo "Deploying to: $TARGET_COLOR"
echo ""

# Stop and remove target container
echo "Step 2: Preparing target container"
docker stop api-go-$TARGET_COLOR 2>/dev/null || true
docker rm api-go-$TARGET_COLOR 2>/dev/null || true

# Start container with specific version
echo ""
echo "Step 3: Starting container with version $VERSION"
docker run -d \
  --name api-go-$TARGET_COLOR \
  --restart unless-stopped \
  --env-file /root/deploy/api/.env.production \
  -e APP_ENV=production \
  -e INSTANCE_COLOR=$TARGET_COLOR \
  -p 127.0.0.1:$TARGET_PORT:8080 \
  --memory=512m \
  --health-cmd="wget --no-verbose --tries=1 --spider http://localhost:8080/api/v1/health || exit 1" \
  --health-interval=10s \
  --health-timeout=5s \
  --health-retries=3 \
  screenshot-api-go:rollback

# Wait for health
echo ""
echo "Step 4: Waiting for health check"
for i in {1..30}; do
  if [ "$(docker inspect --format='{{.State.Health.Status}}' api-go-$TARGET_COLOR)" = "healthy" ]; then
    echo "✓ Container is healthy"
    break
  fi
  echo -n "."
  sleep 2
done
echo ""

if [ "$(docker inspect --format='{{.State.Health.Status}}' api-go-$TARGET_COLOR)" != "healthy" ]; then
  echo "❌ Container failed health check"
  docker logs api-go-$TARGET_COLOR --tail 50
  exit 1
fi

# Run deployment script to switch traffic
echo ""
echo "Step 5: Switching traffic"
/root/deploy/api/scripts/switch-to-$TARGET_COLOR.sh

echo ""
echo "====================================="
echo "✅ Rollback to $VERSION complete!"
echo "====================================="
