# Go Renderer Microservice

High-performance screenshot and PDF rendering service built with Go and Rod (Chromium DevTools Protocol).

## Features

- 🚀 **Fast** - Native Go performance with minimal overhead
- 🔒 **Secure** - SSRF protection, private IP blocking
- 🛡️ **Ad Blocking** - Built-in blocking for ads, trackers, cookie banners
- 📦 **Lightweight** - ~50MB RAM idle, ~200MB under load
- 🔄 **Browser Pool** - Reusable browser instances for efficiency

## API Endpoints

### Health Check
```
GET /health
```

### Screenshot
```
POST /render/screenshot
Content-Type: application/json

{
  "url": "https://example.com",
  "width": 1920,
  "height": 1080,
  "format": "jpeg",
  "quality": 80,
  "full_page": false,
  "delay": 0,
  "block_ads": true,
  "block_cookie_banners": true
}
```

### PDF
```
POST /render/pdf
Content-Type: application/json

{
  "url": "https://example.com",
  "format": "A4",
  "landscape": false,
  "print_background": true
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| PORT | 8001 | HTTP server port |
| BROWSER_POOL_SIZE | 2 | Number of browser instances |

## Local Development

```bash
# Download dependencies
go mod download

# Run server
go run .

# Test
curl http://localhost:8001/health
```

## Docker

```bash
# Build
docker build -t go-renderer .

# Run
docker run -p 8001:8001 go-renderer

# Test
curl http://localhost:8001/health
```
