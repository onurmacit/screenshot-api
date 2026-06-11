# Screenshot API

[![CI/CD](https://github.com/onurmacit/screenshot-api/actions/workflows/ci.yml/badge.svg)](https://github.com/onurmacit/screenshot-api/actions/workflows/ci.yml)
[![Go 1.22+](https://img.shields.io/badge/go-1.22+-00ADD8.svg)](https://go.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-00a393.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

Production-grade Screenshot and PDF rendering SaaS with multi-tenant architecture, a high-performance Go rendering engine, and S3 storage.

## Architecture

The system uses a **microservice architecture** — a FastAPI orchestration layer handles auth, billing, and job management, while a dedicated **Go renderer** handles the actual browser operations for maximum performance.

```
┌─────────────────────────────────────────────────────────────────┐
│                         Load Balancer                            │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Orchestrator                          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │  Auth   │  │  Jobs   │  │  Usage  │  │ Billing │           │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘           │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│               Go Renderer (Fiber + go-rod)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Browser Pool │  │ Ad Blocking  │  │SSRF Protection│          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└───────────────────────────────┬─────────────────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                  ▼
┌─────────────────┐  ┌─────────────┐  ┌─────────────────┐
│   PostgreSQL    │  │    Redis    │  │   S3 / MinIO    │
│   (Database)    │  │   (Cache)   │  │   (Storage)     │
└─────────────────┘  └─────────────┘  └─────────────────┘
```

## Tech Stack

| Component | Technology | Why |
|-----------|------------|-----|
| Rendering Engine | **Go + go-rod** (Chrome DevTools Protocol) | ~50MB RAM idle, native concurrency, browser pool |
| API Orchestrator | FastAPI (Python) | Async, auto-docs, Pydantic validation |
| Database | PostgreSQL 15+ | JSONB support, async via asyncpg |
| Cache & Queue | Redis 7+ | Rate limiting, caching, Celery broker |
| Task Queue | Celery 5+ | Background jobs, retry logic |
| Object Storage | AWS S3 / MinIO | Presigned URLs, CDN-ready |
| Web Framework (Go) | Fiber v2 | Express-like, high throughput |
| Authentication | JWT + API Keys | Scoped keys with expiration |
| Payments | Stripe | Subscriptions, usage-based billing |
| Containerization | Docker + Docker Compose | Multi-stage builds, health checks |
| CI/CD | GitHub Actions | Automated tests, Docker image builds |

## Go Renderer — Performance

The rendering microservice is built in Go for maximum throughput and minimal resource usage.

**Key design decisions:**

- **Browser Pool** — Round-robin allocation of pre-warmed Chromium instances. Eliminates cold-start penalty (~2s saved per request).
- **go-rod over Playwright** — Direct Chrome DevTools Protocol communication. ~50MB idle RAM vs ~200MB+ for Playwright. No Node.js dependency.
- **SSRF Protection** — URL validation with private IP blocking (RFC 1918). DNS resolution check before navigation.
- **Ad/Tracker Blocking** — Request interception at network level. Blocks 30+ ad networks, analytics providers, and chat widgets.
- **Cookie Banner Blocking** — Domain-level blocking for 15+ consent management platforms.
- **Smart Element Capture** — Fast JS pre-check (~0ms) before Rod timeout. Progressive scroll for lazy-loaded elements. 10s time budget with early exit.

### Rendering Capabilities

- Screenshot: PNG, JPEG, WebP with configurable quality
- PDF: A4, A3, Letter, Legal, Tabloid with custom margins
- Full-page capture with auto-scroll
- Element selector (CSS + XPath) with visibility/stability checks
- Scroll-into-view with pixel-level adjustment
- Custom viewport, device scale factor, user agent
- Dark mode emulation
- HTML/Markdown direct rendering (no URL required)

## API Endpoints

### Screenshot
```bash
curl -X POST http://localhost:8001/render/screenshot \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://stripe.com",
    "width": 1920,
    "height": 1080,
    "format": "jpeg",
    "quality": 85,
    "full_page": false,
    "block_ads": true,
    "block_cookie_banners": true,
    "selector": ".pricing-table",
    "scroll_into_view": "footer"
  }'
```

### PDF Generation
```bash
curl -X POST http://localhost:8001/render/pdf \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "format": "A4",
    "landscape": false,
    "print_background": true
  }'
```

### Health Check
```bash
curl http://localhost:8001/health
# {"status": "healthy", "service": "go-renderer"}
```

## Rate Limits by Plan

| Plan | Price | Per Minute | Per Month | Features |
|------|-------|------------|-----------|----------|
| Free | $0 | 10 | 100 | Basic screenshots |
| Starter | $19 | 100 | 5,000 | Full page, webhooks |
| Pro | $49 | 500 | 25,000 | Custom CSS, element selector |
| Business | $149 | 2,000 | 100,000 | All Pro + SLA |

## Quick Start

### Go Renderer (standalone)

```bash
cd go-renderer
go mod download
go run .
# Server starts on :8001
```

### Full Stack (Docker Compose)

```bash
docker-compose up -d
# API: http://localhost:8000
# Go Renderer: http://localhost:8001
# PostgreSQL: localhost:5433
# Redis: localhost:6379
```

### Production

```bash
docker-compose -f docker-compose.production.yml up -d
```

## Project Structure

```
screenshot-api/
├── go-renderer/              # High-performance Go rendering service
│   ├── main.go               # Fiber server, routes, browser pool init
│   ├── handlers/             # HTTP handlers (screenshot, PDF)
│   ├── services/
│   │   ├── browser_pool.go   # Round-robin browser instance management
│   │   ├── renderer.go       # Core rendering logic, SSRF protection
│   │   ├── screenshot.go     # Screenshot-specific logic
│   │   └── errors.go         # Typed error handling
│   ├── config/               # Environment configuration
│   └── Dockerfile            # Multi-stage Go build
├── api-go/                   # Go API rewrite (in progress)
│   ├── cmd/                  # Entry points
│   ├── internal/             # Private application code
│   ├── pkg/                  # Shared packages
│   └── migrations/           # Database migrations
├── app/                      # FastAPI orchestrator
│   ├── api/routes/           # Auth, renders, billing, webhooks
│   ├── core/                 # Config, database, Redis, S3
│   ├── models/               # SQLAlchemy models
│   ├── schemas/              # Pydantic request/response schemas
│   ├── services/             # Business logic
│   ├── workers/              # Celery tasks
│   └── middleware/           # Rate limiting, audit logging
├── dashboard/                # Admin dashboard
├── monitoring/               # Prometheus, Grafana configs
├── docker/                   # Dockerfiles
├── k8s/                      # Kubernetes deployment configs
├── tests/                    # Test suite (97+ unit, 10 stress)
├── scripts/                  # Utility scripts
└── docs/                     # API documentation
```

## Testing

```bash
# Unit tests (97 passing)
pytest tests/unit -v

# Stress tests (10 passing)
pytest tests/stress -v

# Go renderer tests
cd go-renderer && go test ./...
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8001 | Go renderer port |
| `BROWSER_POOL_SIZE` | 2 | Concurrent browser instances |
| `DATABASE_URL` | — | PostgreSQL connection string |
| `REDIS_URL` | redis://localhost:6379/0 | Redis connection |
| `STRIPE_SECRET_KEY` | — | Stripe API key |
| `STORAGE_BUCKET` | — | S3 bucket name |
| `STORAGE_ENDPOINT` | — | S3-compatible endpoint |

## Deployment

- **Backend API**: Docker → DigitalOcean / AWS / GCP
- **Landing Page**: Vercel ([live](https://screenshot-web-five.vercel.app/))
- **Docker Images**: GitHub Container Registry (`ghcr.io/onurmacit/screenshot-api`)
- **CI/CD**: GitHub Actions (test → build → push)

## License

MIT License — see [LICENSE](LICENSE) for details.
