# =============================================================================
# Go Renderer - Multi-stage Dockerfile
# =============================================================================
# Stage 1: Builder - Compile Go binary
# Stage 2: Runtime - Minimal image with Chromium
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder
# -----------------------------------------------------------------------------
FROM golang:1.22-alpine AS builder

# Install git for go mod download
RUN apk add --no-cache git

WORKDIR /app

# Copy go.mod and download dependencies
COPY go.mod go.sum* ./
RUN go mod download

# Copy source code
COPY . .

# Build static binary
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o renderer .

# -----------------------------------------------------------------------------
# Stage 2: Runtime with Chromium
# -----------------------------------------------------------------------------
FROM chromedp/headless-shell:latest

# Labels
LABEL maintainer="ScreenshotBeam <support@screenshotbeam.com>" \
      version="1.0.0" \
      description="ScreenshotBeam Go Renderer - Rod/Chromium Microservice"

# Install ca-certificates for HTTPS and dumb-init for proper signal handling
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    dumb-init \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy binary from builder
COPY --from=builder /app/renderer /usr/local/bin/renderer

# Note: Running as root because Chrome in chromedp image requires it
# The container is isolated and Chrome runs with sandbox disabled anyway

# Expose port
EXPOSE 8001

# Health check - longer start period for browser initialization
HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -sf http://localhost:8001/health || exit 1

# Use dumb-init for proper signal handling
ENTRYPOINT ["dumb-init", "--"]
CMD ["/usr/local/bin/renderer"]
