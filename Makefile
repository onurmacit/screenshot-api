# =============================================================================
# Screenshot API - Makefile (Go Only)
# =============================================================================

.PHONY: help dev build test deploy clean logs

# Default target
help:
	@echo "Screenshot API - Go Backend"
	@echo ""
	@echo "Development:"
	@echo "  make dev        - Run Go API locally"
	@echo "  make build      - Build Go API binary"
	@echo "  make test       - Run Go tests"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build   - Build Docker image"
	@echo "  make docker-up      - Start containers"
	@echo "  make docker-down    - Stop containers"
	@echo "  make docker-logs    - View container logs"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy     - Deploy to production"
	@echo ""

# =============================================================================
# Development
# =============================================================================

dev:
	cd api-go && go run ./cmd/api/main.go

build:
	cd api-go && go build -o bin/api ./cmd/api/main.go

test:
	cd api-go && go test ./...

test-verbose:
	cd api-go && go test -v ./...

lint:
	cd api-go && golangci-lint run

# =============================================================================
# Docker
# =============================================================================

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f api-go

docker-restart:
	docker compose restart api-go

# =============================================================================
# Deployment
# =============================================================================

deploy:
	@echo "Deploying to production..."
	tar czf - --exclude='.git' --exclude='node_modules' --exclude='venv' . | \
		ssh root@138.197.103.137 "cd /root/screenshot-api && tar xzf -"
	ssh root@138.197.103.137 "cd /root/screenshot-api && docker compose up -d --build"
	@echo "Deployment complete!"

deploy-go:
	@echo "Deploying Go API only..."
	tar czf - --exclude='.git' -C api-go . | \
		ssh root@138.197.103.137 "cd /root/screenshot-api/api-go && tar xzf -"
	ssh root@138.197.103.137 "cd /root/screenshot-api && docker compose up -d --build api-go"
	@echo "Go API deployed!"

# =============================================================================
# Utilities
# =============================================================================

clean:
	cd api-go && rm -rf bin/
	docker system prune -f

logs:
	ssh root@138.197.103.137 "docker logs --tail 50 -f screenshot-api-go"

status:
	ssh root@138.197.103.137 "docker ps | grep screenshot"

health:
	curl -s https://api.screenshotbeam.com/health | jq

db-shell:
	@echo "Connecting to Supabase PostgreSQL..."
	psql "$(DATABASE_URL)"
