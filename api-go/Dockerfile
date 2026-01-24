# Build Stage
FROM golang:1.24-alpine AS builder
WORKDIR /app

# Install git for private modules if needed
# RUN apk add --no-cache git

COPY go.mod go.sum ./
RUN go mod download

COPY . .

# Build main API binary
# CGO_ENABLED=0 for static binary (no libc dependency issues)
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /api ./cmd/api/main.go

# Build migration binary
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /migrate ./cmd/migrate/main.go

# Run Stage
FROM alpine:3.19

# Install ca-certificates for HTTPS and wget for health checks
RUN apk --no-cache add ca-certificates tzdata wget

WORKDIR /app

# Copy binaries to root for easy access
COPY --from=builder /api /api
COPY --from=builder /migrate /migrate

# Copy migrations
COPY --from=builder /app/migrations /migrations

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8080/api/v1/health || exit 1

# Expose port (default 8080)
EXPOSE 8080

# Environment variables should be injected by deployment platform
CMD ["/api"]
