---
description: Deploy API to production server
---

# Deploy to Production

// turbo-all

This workflow deploys the Screenshot API to the production server.

## Prerequisites
- SSH access to server (already configured)
- Code committed and pushed to GitHub

## Steps

1. Run the deploy script:
```bash
cd /Users/onurmacit/screenshot-api && ./scripts/deploy.sh
```

## What the Script Does

1. **SSH to server** - Connects to 138.197.103.137
2. **git pull** - Syncs latest code from GitHub
3. **docker compose build** - Rebuilds Docker image with new code
4. **docker compose up -d** - Starts new container
5. **Health check** - Verifies deployment succeeded

## Manual Deploy (if script fails)

```bash
ssh root@138.197.103.137 << 'EOF'
  cd /opt/screenshot-api
  git pull origin main
  docker compose -f docker-compose.api.yml build api
  docker compose -f docker-compose.api.yml up -d api
  sleep 15
  curl -f http://localhost:8080/api/v1/health
EOF
```

## Verify Deployment

Check container status:
```bash
ssh root@138.197.103.137 "docker ps | grep screenshot"
```

Check logs:
```bash
ssh root@138.197.103.137 "docker logs screenshot-api --tail 50"
```
