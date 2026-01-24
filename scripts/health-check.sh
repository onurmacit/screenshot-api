#!/bin/bash

COLOR=$1
if [ -z "$COLOR" ]; then
  echo "Usage: ./health-check.sh [blue|green]"
  exit 1
fi

PORT=8080
if [ "$COLOR" = "green" ]; then
  PORT=8081
fi

echo "Checking health of $COLOR (port $PORT)..."

for i in {1..30}; do
  RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT/api/v1/health)
  
  if [ "$RESPONSE" = "200" ]; then
    echo "✅ $COLOR is healthy (attempt $i)"
    
    # Also check Docker health status
    DOCKER_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' api-go-$COLOR)
    echo "Docker health status: $DOCKER_HEALTH"
    
    if [ "$DOCKER_HEALTH" = "healthy" ]; then
      echo "✅ All checks passed for $COLOR"
      exit 0
    fi
  fi
  
  echo "Waiting... ($i/30)"
  sleep 2
done

echo "❌ $COLOR failed health check after 60s"
exit 1
