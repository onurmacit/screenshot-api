#!/bin/bash
set -e

# Configuration
COLORS=("blue" "green")
CURRENT_COLOR=""
OLD_COLOR=""

function detect_current_color() {
  if docker ps --filter "name=api-go-blue" --filter "status=running" | grep -q api-go-blue; then
    if docker ps --filter "name=api-go-green" --filter "status=running" | grep -q api-go-green; then
      # Both running, check nginx config
      if grep -q "server api-go-blue:8080" /root/deploy/api/docker/nginx-blue-green.conf | grep -v "#"; then
        CURRENT_COLOR="blue"
        OLD_COLOR="green"
      else
        CURRENT_COLOR="green"
        OLD_COLOR="blue"
      fi
    else
      CURRENT_COLOR="blue"
      OLD_COLOR="green"
    fi
  elif docker ps --filter "name=api-go-green" --filter "status=running" | grep -q api-go-green; then
    CURRENT_COLOR="green"
    OLD_COLOR="blue"
  else
    echo "❌ No running containers found!"
    exit 1
  fi
}

function rollback() {
  echo "====================================="
  echo "🔄 Starting Rollback Process"
  echo "====================================="
  echo ""
  
  detect_current_color
  
  echo "Current active: $CURRENT_COLOR"
  echo "Rolling back to: $OLD_COLOR"
  echo ""
  
  # Check if old container exists
  if ! docker ps -a --filter "name=api-go-$OLD_COLOR" | grep -q api-go-$OLD_COLOR; then
    echo "❌ Old container (api-go-$OLD_COLOR) not found!"
    echo "Cannot rollback without previous version."
    exit 1
  fi
  
  # Start old container if stopped
  echo "Step 1: Starting old container (api-go-$OLD_COLOR)"
  if ! docker ps --filter "name=api-go-$OLD_COLOR" --filter "status=running" | grep -q api-go-$OLD_COLOR; then
    docker start api-go-$OLD_COLOR
    echo "✓ Container started"
  else
    echo "✓ Container already running"
  fi
  
  # Wait for health check
  echo ""
  echo "Step 2: Waiting for health check"
  for i in {1..30}; do
    if [ "$(docker inspect --format='{{.State.Health.Status}}' api-go-$OLD_COLOR)" = "healthy" ]; then
      echo "✓ Old container is healthy"
      break
    fi
    echo -n "."
    sleep 2
  done
  echo ""
  
  if [ "$(docker inspect --format='{{.State.Health.Status}}' api-go-$OLD_COLOR)" != "healthy" ]; then
    echo "❌ Old container failed health check"
    docker logs api-go-$OLD_COLOR --tail 50
    exit 1
  fi
  
  # Switch nginx upstream
  echo ""
  echo "Step 3: Switching Nginx to $OLD_COLOR"
  
  OLD_PORT=8080
  if [ "$OLD_COLOR" = "green" ]; then
    OLD_PORT=8081
  fi
  
  # Update nginx config
  sed -i "s/server api-go-$CURRENT_COLOR:8080/# server api-go-$CURRENT_COLOR:8080/" /root/deploy/api/docker/nginx-blue-green.conf
  sed -i "s/# server api-go-$OLD_COLOR:8080/server api-go-$OLD_COLOR:8080/" /root/deploy/api/docker/nginx-blue-green.conf
  
  # Test and reload nginx
  if docker exec screenshot-nginx nginx -t; then
    docker exec screenshot-nginx nginx -s reload
    echo "✓ Nginx reloaded"
  else
    echo "❌ Nginx config test failed"
    exit 1
  fi
  
  # Wait for traffic to drain
  echo ""
  echo "Step 4: Draining connections from $CURRENT_COLOR"
  sleep 10
  echo "✓ Connection draining complete"
  
  # Stop current container
  echo ""
  echo "Step 5: Stopping failed container (api-go-$CURRENT_COLOR)"
  docker stop api-go-$CURRENT_COLOR
  echo "✓ Container stopped"
  
  # Verify rollback
  echo ""
  echo "Step 6: Verifying rollback"
  HEALTH_CHECK=$(curl -s http://localhost:$OLD_PORT/api/v1/health | jq -r .status)
  
  if [ "$HEALTH_CHECK" = "healthy" ]; then
    echo "✓ Health check passed"
  else
    echo "❌ Health check failed after rollback"
    exit 1
  fi
  
  echo ""
  echo "====================================="
  echo "✅ Rollback Complete!"
  echo "====================================="
  echo "Active: api-go-$OLD_COLOR"
  echo "Stopped: api-go-$CURRENT_COLOR"
  echo ""
  echo "Next steps:"
  echo "1. Investigate what caused the failure"
  echo "2. Fix the issue"
  echo "3. Deploy again"
}

# Show current state
function show_status() {
  echo "====================================="
  echo "Current Deployment Status"
  echo "====================================="
  echo ""
  
  docker ps --filter "name=api-go" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
  
  echo ""
  echo "Nginx upstream configuration:"
  grep -E "server api-go-" /root/deploy/api/docker/nginx-blue-green.conf | grep -v "#" || echo "No active upstream found"
}

# Main
case "${1:-rollback}" in
  rollback)
    rollback
    ;;
  status)
    show_status
    ;;
  *)
    echo "Usage: $0 {rollback|status}"
    echo ""
    echo "Commands:"
    echo "  rollback  - Rollback to previous deployment"
    echo "  status    - Show current deployment status"
    exit 1
    ;;
esac
