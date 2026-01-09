---
description: Deploy API with Go Renderer to production Droplet
---

# Deploy to Production (Hybrid Go Renderer)

// turbo-all

This workflow deploys the Screenshot API with Go Renderer to the production Droplet.

## Prerequisites
- SSH access to server (already configured)
- Code committed and pushed to GitHub

## Steps

1. Run the deploy script:
```bash
cd /Users/onurmacit/screenshot-api && ./scripts/deploy-go-renderer.sh
```

## What the Script Does

1. **SSH to server** - Connects to 138.197.103.137
2. **git pull** - Syncs latest code from GitHub
3. **docker compose build** - Builds API and Go renderer images
4. **docker compose up -d** - Starts both containers
5. **Health check** - Verifies both services are healthy

## Manual Deploy

```bash
ssh root@138.197.103.137 << 'EOF'
  cd /opt/screenshot-api
  git pull origin main
  
  # Stop old Celery workers (if running)
  docker compose -f docker-compose.api.yml down || true
  
  # Start new hybrid architecture
  docker compose -f docker/docker-compose.go-renderer.yml build
  docker compose -f docker/docker-compose.go-renderer.yml up -d
  
  # Wait for services
  sleep 20
  
  # Health checks
  echo "=== Go Renderer Health ==="
  curl -sf http://localhost:8001/health || echo "FAILED"
  
  echo "=== FastAPI Health ==="
  curl -sf http://localhost:8000/api/v1/health || echo "FAILED"
EOF
```

## Verify Deployment

Check container status:
```bash
ssh root@138.197.103.137 "docker ps | grep -E 'screenshot|go-renderer'"
```

Check Go renderer logs:
```bash
ssh root@138.197.103.137 "docker logs screenshot-go-renderer --tail 50"
```

Check API logs:
```bash
ssh root@138.197.103.137 "docker logs screenshot-api --tail 50"
```

## Rollback (if needed)

```bash
ssh root@138.197.103.137 << 'EOF'
  cd /opt/screenshot-api
  docker compose -f docker/docker-compose.go-renderer.yml down
  docker compose -f docker-compose.api.yml up -d
EOF
```
