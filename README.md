# Screenshot API

Production-grade Screenshot and PDF rendering SaaS with multi-tenant architecture, background processing, and S3 storage.

## 🚀 Features

- **Async Screenshot/PDF Rendering** - Powered by Playwright (Chromium)
- **Multi-tier Rate Limiting** - Per user, per IP, per plan
- **Background Job Processing** - Celery with Redis broker and retry logic
- **S3-based Persistent Storage** - With CDN support
- **Redis-based Caching** - For rate limiting and caching
- **Usage Tracking & Billing** - Stripe integration
- **Webhook Notifications** - For async job completion
- **API Key Management** - With scopes and expiration
- **Comprehensive Logging** - Structured JSON logging

## 📋 Tech Stack

| Component | Technology |
|-----------|------------|
| API Framework | FastAPI 0.109+ |
| Rendering Engine | Playwright (Chromium) |
| Database | PostgreSQL 15+ |
| Cache & Queue | Redis 7+ |
| Task Queue | Celery 5+ |
| Object Storage | AWS S3 / MinIO |
| Containerization | Docker + Docker Compose |
| Authentication | JWT + API Keys |
| Payments | Stripe |

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Load Balancer                             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Application                          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │  Auth   │  │ Renders │  │  Usage  │  │ Billing │            │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘            │
└─────────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  PostgreSQL │  │    Redis    │  │   Celery    │  │     S3      │
│  (Database) │  │   (Cache)   │  │  (Workers)  │  │  (Storage)  │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
                                         │
                                         ▼
                                ┌─────────────────┐
                                │   Playwright    │
                                │   (Chromium)    │
                                └─────────────────┘
```

## 🛠️ Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/your-org/screenshot-api.git
cd screenshot-api

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Install Playwright browsers
playwright install chromium
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env
```

### 3. Start with Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api
```

### 4. Run Database Migrations

```bash
# Apply migrations
alembic upgrade head

# Seed initial data (plans)
python scripts/seed_db.py
```

### 5. Access the API

- API Documentation: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/api/v1/health

## 📖 API Usage

### Authentication

```bash
# Register a new user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!"}'

# Create API Key
curl -X POST http://localhost:8000/api/v1/auth/api-keys \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "My API Key", "scopes": ["renders:read", "renders:write"]}'
```

### Screenshot

```bash
# Sync Screenshot
curl -X POST http://localhost:8000/api/v1/render/screenshot \
  -H "X-API-Key: sk_live_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "width": 1920,
    "height": 1080,
    "format": "png"
  }'

# Async Screenshot with Webhook
curl -X POST http://localhost:8000/api/v1/render/screenshot \
  -H "X-API-Key: sk_live_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "async": true,
    "webhook_url": "https://your-server.com/webhook"
  }'
```

### PDF Generation

```bash
curl -X POST http://localhost:8000/api/v1/render/pdf \
  -H "X-API-Key: sk_live_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "format": "A4",
    "print_background": true
  }'
```

## 🔒 Rate Limits by Plan

| Plan | Per Minute | Per Hour | Per Day | Per Month |
|------|------------|----------|---------|-----------|
| Free | 10 | 100 | 200 | 100 |
| Starter | 30 | 500 | 2,000 | 5,000 |
| Pro | 100 | 2,000 | 10,000 | 25,000 |
| Business | 500 | 10,000 | 50,000 | 100,000 |

## 🧪 Testing

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit -v

# Run integration tests
pytest tests/integration -v

# Run with coverage
pytest --cov=app --cov-report=html
```

## 🐳 Docker Commands

```bash
# Build and start
docker-compose up --build -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f

# Scale workers
docker-compose up -d --scale worker=5

# Execute command in container
docker-compose exec api python scripts/seed_db.py
```

## 📊 Monitoring

- **Prometheus Metrics**: http://localhost:8000/metrics
- **Flower (Celery)**: http://localhost:5555
- **Health Checks**: http://localhost:8000/api/v1/health

## 📁 Project Structure

```
screenshot-api/
├── app/
│   ├── api/
│   │   ├── routes/          # API endpoints
│   │   └── dependencies.py  # FastAPI dependencies
│   ├── core/                # Core configurations
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── services/            # Business logic
│   ├── workers/             # Celery tasks
│   ├── middleware/          # Custom middleware
│   ├── utils/               # Utilities
│   └── main.py              # Application entry
├── alembic/                 # Database migrations
├── tests/                   # Test suite
├── scripts/                 # Utility scripts
├── docker/                  # Docker files
└── k8s/                     # Kubernetes configs
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

- Documentation: https://docs.screenshotapi.com
- Email: support@screenshotapi.com
- Discord: https://discord.gg/screenshotapi

