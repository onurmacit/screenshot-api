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
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o api ./cmd/api/main.go

# Build migration binary
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o migrate ./cmd/migrate/main.go

# Run Stage
FROM alpine:latest

# Install ca-certificates for HTTPS
RUN apk --no-cache add ca-certificates

WORKDIR /app

# Copy binaries
COPY --from=builder /app/api .
COPY --from=builder /app/migrate .

# Copy migrations
COPY --from=builder /app/migrations ./migrations

# Expose port (default 8080)
EXPOSE 8080

# Environment variables should be injected by deployment platform
CMD ["./api"]
