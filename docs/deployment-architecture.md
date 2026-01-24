# Screenshot API - Deployment Architecture

## Overview

This document describes the deployment architecture for **ScreenshotBeam**, a screenshot-as-a-service API built with Go/Fiber.

---

## System Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DEVELOPMENT ENVIRONMENT                            │
│                                                                              │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────┐  │
│   │   VS Code   │────▶│   Git CLI   │────▶│    GitHub Repository       │  │
│   │   (Local)   │     │   (Local)   │     │  onurmacit/screenshot-api  │  │
│   └─────────────┘     └─────────────┘     └─────────────────────────────┘  │
│                                                      │                       │
└──────────────────────────────────────────────────────│───────────────────────┘
                                                       │
                                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CI/CD PIPELINE                                  │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                       GitHub Actions Workflow                        │   │
│   │                       (.github/workflows/deploy-go.yml)              │   │
│   │                                                                      │   │
│   │   ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐   │   │
│   │   │ Build & Push │────▶│  SSH Deploy  │────▶│  Health Check    │   │   │
│   │   │ (GHCR Image) │     │ (to Droplet) │     │  Verification    │   │   │
│   │   └──────────────┘     └──────────────┘     └──────────────────┘   │   │
│   │          │                    │                                     │   │
│   │          ▼                    │  ❌ FAILING                         │   │
│   │   ┌──────────────┐           │  SSH key not configured             │   │
│   │   │ GitHub       │           │                                     │   │
│   │   │ Container    │           │                                     │   │
│   │   │ Registry     │           │                                     │   │
│   │   │ (GHCR)       │           │                                     │   │
│   │   └──────────────┘           │                                     │   │
│   └──────────────────────────────│─────────────────────────────────────┘   │
│                                  │                                          │
└──────────────────────────────────│──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PRODUCTION ENVIRONMENT                                │
│                        DigitalOcean Droplet                                 │
│                        64.23.183.104                                        │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                         Docker Environment                           │   │
│   │                                                                      │   │
│   │   ┌───────────────┐    ┌───────────────┐    ┌───────────────────┐  │   │
│   │   │  Nginx        │    │ screenshot-   │    │   Prometheus      │  │   │
│   │   │  (Reverse     │───▶│ api-go        │───▶│   + Grafana       │  │   │
│   │   │   Proxy)      │    │ :8090->8080   │    │   + Alertmanager  │  │   │
│   │   │  :80/:443     │    └───────────────┘    └───────────────────┘  │   │
│   │   └───────────────┘            │                                   │   │
│   │                                │                                   │   │
│   │                                ▼                                   │   │
│   │   ┌──────────────────────────────────────────────────────────────┐ │   │
│   │   │                     External Services                        │ │   │
│   │   │   ┌──────────┐   ┌──────────┐   ┌──────────────────────┐   │ │   │
│   │   │   │ Supabase │   │ Upstash  │   │ DigitalOcean Spaces  │   │ │   │
│   │   │   │ Postgres │   │ Redis    │   │ (S3 Storage)         │   │ │   │
│   │   │   └──────────┘   └──────────┘   └──────────────────────┘   │ │   │
│   │   └──────────────────────────────────────────────────────────────┘ │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                       Manual Deployment                              │   │
│   │                       (Currently Used)                               │   │
│   │                                                                      │   │
│   │   $ deploy-go   ─────▶  git pull                                    │   │
│   │                        docker build --no-cache                      │   │
│   │                        docker compose up -d --force-recreate        │   │
│   │                        docker logs                                  │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SEPARATE RENDERER DROPLET                               │
│                        167.71.85.169                                        │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    Go Renderer Service                               │   │
│   │                    (Playwright + Chromium)                           │   │
│   │                                                                      │   │
│   │   • Handles actual screenshot/PDF rendering                         │   │
│   │   • Isolated for resource management                                │   │
│   │   • Called via HTTP from main API                                   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Current Deployment Flow

### Manual Deployment (Working ✅)

```bash
# On server (via SSH or DigitalOcean Console)
deploy-go

# This runs:
# 1. git pull (with GitHub PAT authentication)
# 2. docker compose build --no-cache api-go
# 3. docker compose up -d --force-recreate api-go
# 4. docker logs screenshot-api-go --tail 20
```

### GitHub Actions (Broken ❌)

The CI/CD pipeline fails at SSH step with:
```
ssh: unable to authenticate, attempted methods [none publickey]
```

**Root Cause:** `SSH_PRIVATE_KEY` secret in GitHub doesn't match any authorized key on server.

---

## File Structure

```
screenshot-api/
├── .github/
│   └── workflows/
│       └── deploy-go.yml          # CI/CD workflow
│
├── api-go/
│   ├── cmd/
│   │   ├── api/main.go            # Main API entrypoint
│   │   └── migrate/main.go        # Database migration CLI
│   │
│   ├── migrations/                 # SQL migration files
│   │   ├── 000001_initial_schema.up.sql
│   │   ├── 000002_add_render_job_fields.up.sql
│   │   └── README.md
│   │
│   ├── internal/
│   │   ├── handlers/              # HTTP handlers
│   │   ├── services/              # Business logic
│   │   ├── models/                # GORM models
│   │   └── repository/            # Database access
│   │
│   ├── Dockerfile                  # Multi-stage Docker build
│   └── go.mod
│
├── dashboard/                      # Next.js frontend (Vercel)
│
├── docker-compose.go-only.yml     # Production compose file
└── production-hotfix.sql          # Emergency SQL fixes
```

---

## Docker Compose Configuration

```yaml
# docker-compose.go-only.yml
services:
  api-go:
    build: ./api-go
    image: ghcr.io/onurmacit/screenshot-api-go:latest
    container_name: screenshot-api-go
    ports:
      - "127.0.0.1:8090:8080"
    environment:
      - APP_ENV=production
      - GO_RENDERER_URL=http://167.71.85.169:8001
    env_file:
      - .env.production
    mem_limit: 512m

  nginx:
    image: nginx:alpine
    container_name: screenshot-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx.go-only.conf:/etc/nginx/nginx.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
```

---

## Database Migration System

### golang-migrate Implementation

```bash
# Check current version
docker exec screenshot-api-go ./migrate version
# Output: Current version: 2

# Apply new migrations
docker exec screenshot-api-go ./migrate up

# Rollback last migration
docker exec screenshot-api-go ./migrate down

# Force version (emergency)
docker exec screenshot-api-go ./migrate force 2
```

### Migration Files

| Version | File | Description |
|---------|------|-------------|
| 1 | 000001_initial_schema.up.sql | Baseline (tables exist) |
| 2 | 000002_add_render_job_fields.up.sql | render_jobs columns + constraints |

---

## Server Authentication

### GitHub PAT (Configured ✅)

```bash
# Stored in /root/.github_token
# Used by deploy-go alias for git pull
export GITHUB_TOKEN=$(cat /root/.github_token)
```

### SSH Key (Not Configured ❌)

GitHub Actions needs:
1. New SSH key pair generated
2. Public key added to server's ~/.ssh/authorized_keys
3. Private key added to GitHub Secrets as SSH_PRIVATE_KEY

---

## Known Issues

### 1. GitHub Actions SSH Failure
- **Status:** ❌ Broken
- **Error:** `ssh: unable to authenticate`
- **Fix:** Configure SSH key pair

### 2. GORM AutoMigrate Errors
- **Status:** ✅ Fixed
- **Error:** `constraint "uni_plans_name" does not exist`
- **Fix:** Disabled AutoMigrate, using golang-migrate

### 3. RenderJob NOT NULL Constraints
- **Status:** ✅ Fixed
- **Error:** `null value in column "options" violates not-null constraint`
- **Fix:** Dropped NOT NULL on optional columns

---

## Environment Variables

### Production (.env.production)

```env
DATABASE_URL=postgresql+asyncpg://...@supabase.com:5432/postgres
REDIS_URL=redis://...@upstash.io:6379
S3_BUCKET=screenshotbeam-renders
S3_ENDPOINT=nyc3.digitaloceanspaces.com
JWT_SECRET=...
ADMIN_EMAILS=onurmacit@gmail.com
GO_RENDERER_URL=http://167.71.85.169:8001
```

---

## Questions for Review

1. **Should we switch from GHCR to DockerHub?** GHCR requires authentication which complicates deployments.

2. **Is building on server (current approach) scalable?** Currently builds take ~5 minutes on small Droplet.

3. **Should we add database migration step to CI/CD?** Currently migrations are run manually.

4. **How to handle zero-downtime deployments?** Current approach has ~10s downtime during recreate.

5. **Should we separate Nginx into its own deployment?** Currently it's recreated with API.
