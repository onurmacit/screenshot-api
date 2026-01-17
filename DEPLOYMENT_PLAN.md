# 🚀 Go API Deployment Plan (Hybrid Migration)

This plan outlines the steps to deploy the new **Go API** alongside the existing Python API in a "Hybrid" mode.
Core rendering traffic (`/api/v1/renders`) will be routed to Go, while Auth/Billing remains on Python.

## 📋 Prerequisites

1. Ensure you serve `DEPLOYMENT_PLAN.md` file exist in root.
2. Ensure `.env.production` is up to date (check `JWT_SECRET_KEY` and `GO_RENDERER_URL`).
3. Ensure you are on the `main` branch with latest changes.

---

## 🛠️ Step 1: Build Go API Image

We need to build the production Docker image for the Go API locally on the server (or pull from registry if you configured CI/CD).

```bash
# Build the image tagging it as 'prod'
docker build -t screenshot-api-go:prod -f api-go/Dockerfile api-go
```

**Verify Build:**
```bash
docker images | grep screenshot-api-go
# Should show 'prod' tag
```

---

## 🚀 Step 2: Deploy (Hybrid Mode)

We have created a specific Docker Compose file `docker-compose.go-migration.yml` and Nginx config `docker/nginx.go-migration.conf` for this transition.

1. **Stop existing containers (Optional but recommended for clean switch):**
   ```bash
   docker compose -f docker-compose.api.hybrid.prod.yml down
   ```

2. **Start new Hybrid Stack:**
   ```bash
   docker compose -f docker-compose.go-migration.yml up -d
   ```

3. **Check Logs:**
   ```bash
   # Check Nginx
   docker logs -f screenshot-nginx
   
   # Check Go API
   docker logs -f screenshot-api-go
   ```

---

## ✅ Step 3: Verification

1. **Test Health:**
   ```bash
   curl -I https://api.screenshotbeam.com/api/v1/health
   # Should return 200 OK (Served by Python)
   ```

2. **Test Rendering (Go API):**
   ```bash
   # This endpoint should now be served by Go
   curl -X GET "https://api.screenshotbeam.com/api/v1/renders?url=https://example.com" \
     -H "X-API-Key: YOUR_API_KEY"
   ```
   *Tip: Check headers for `X-Powered-By` or response time to verify it's Go.*

---

## 🔄 Rollback Plan

If anything goes wrong (e.g., Go API crashes or Nginx misconfiguration), you can instantly revert to the Python-only stack.

1. **Context Switch:**
   ```bash
   # Bring down the migration stack
   docker compose -f docker-compose.go-migration.yml down
   
   # Bring up the old stable stack
   docker compose -f docker-compose.api.hybrid.prod.yml up -d
   ```

2. **Verify Rollback:**
   ```bash
   curl -I https://api.screenshotbeam.com/api/v1/health
   ```

---

## 📝 Troubleshooting

- **502 Bad Gateway:** Check if `screenshot-api-go` container is running (`docker ps`).
- **403 Forbidden:** Check API Key validity.
- **Database Connection Error:** Ensure `.env.production` has correct `DATABASE_URL` (Go uses sanitized version automatically).

---

**Happy Deploying! 🚀**
