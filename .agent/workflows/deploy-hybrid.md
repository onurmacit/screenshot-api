---
description: Deploy Distributed Hybrid Architecture to Production Droplets
---

# Deploy Distributed Hybrid Architecture

// turbo-all

This workflow deploys the Distributed Hybrid Architecture to production droplets.

## Prerequisites
- SSH access to `root@167.71.85.169` (Worker) and `root@138.197.103.137` (API)
- Code committed and pushed to GitHub
- Droplets must have Docker and Git installed

## Steps

1. Run the deploy script:
```bash
cd /Users/onurmacit/screenshot-api && ./scripts/deploy-hybrid.sh
```

## Architecture Overview

**1. Worker Droplet (167.71.85.169)**
- Runs `screenshot-go-renderer`
- Exposed on port 8001
- `BROWSER_POOL_SIZE=6` (Optimized for 4GB RAM)

**2. API Droplet (138.197.103.137)**
- Runs `screenshot-api` (FastAPI)
- Runs `screenshot-nginx`
- Runs Monitoring stack
- Connects to Worker via `http://167.71.85.169:8001`

## Manual Verification

Check Worker 1:
```bash
ssh root@167.71.85.169 "curl -v http://localhost:8001/health"
```

Check Worker 2:
```bash
ssh root@161.35.129.129 "curl -v http://localhost:8001/health"
```

Check API connectivity to Workers:
```bash
ssh root@138.197.103.137 "curl -v http://167.71.85.169:8001/health && curl -v http://161.35.129.129:8001/health"
```
