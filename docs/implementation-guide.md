# Enterprise Deployment System - Implementation Guide

## Overview

This guide provides step-by-step instructions for implementing the complete enterprise deployment system for Screenshot API.

**Estimated Time:** 4-6 hours

---

## Prerequisites Checklist

- [ ] SSH access to production server (138.197.103.137)
- [ ] GitHub repository admin access
- [ ] DigitalOcean account access
- [ ] Slack workspace (optional, for notifications)

---

## Phase 1: Preparation (30 minutes)

### Step 1: Backup Current System

```bash
ssh root@138.197.103.137
cd /root/deploy/api

# Create backup
tar -czf backup-$(date +%Y%m%d-%H%M%S).tar.gz .
docker save screenshot-api-go:latest > api-go-backup.tar
cp docker-compose.go-only.yml docker-compose.backup.yml
```

### Step 2: Create Directory Structure

```bash
mkdir -p /root/deploy/api/scripts
mkdir -p /root/deploy/api/monitoring/alerts
mkdir -p /root/deploy/api/monitoring/grafana-dashboards
mkdir -p /root/deploy/api/docker
mkdir -p /var/log/screenshot-api/blue
mkdir -p /var/log/screenshot-api/green
```

### Step 3: Install Required Tools

```bash
# Install age for encryption
curl -LO https://github.com/FiloSottile/age/releases/download/v1.1.1/age-v1.1.1-linux-amd64.tar.gz
tar xzf age-v1.1.1-linux-amd64.tar.gz
sudo mv age/age* /usr/local/bin/
rm -rf age age-v1.1.1-linux-amd64.tar.gz

# Verify
age --version

# Install jq for JSON parsing
apt-get update && apt-get install -y jq
```

---

## Phase 2: Secrets Management (30 minutes)

### Step 1: Generate Encryption Key (on server)

```bash
mkdir -p ~/.age
age-keygen -o ~/.age/key.txt
age-keygen -y ~/.age/key.txt > ~/.age/key.pub
cat ~/.age/key.pub  # Save this public key
```

### Step 2: Encrypt Production Secrets

```bash
cd /root/deploy/api
age --encrypt --recipient $(cat ~/.age/key.pub) --output .env.production.age .env.production
```

### Step 3: Add Secrets to GitHub

Go to: https://github.com/onurmacit/screenshot-api/settings/secrets/actions

Add these secrets:

| Name | Value |
|------|-------|
| `SERVER_IP` | `138.197.103.137` |
| `SSH_PRIVATE_KEY` | (content of `~/.ssh/github_actions_deploy`) |
| `AGE_PRIVATE_KEY` | (content of `~/.age/key.txt`) |
| `SLACK_WEBHOOK_URL` | (optional - from Slack) |

---

## Phase 3: SSH Setup (15 minutes)

### Step 1: Generate SSH Key (Mac/Local)

```bash
ssh-keygen -t ed25519 -C 'github-actions@screenshotbeam' -f ~/.ssh/github_actions_deploy -N ''
cat ~/.ssh/github_actions_deploy.pub
```

### Step 2: Add Public Key to Server

```bash
ssh root@138.197.103.137
echo 'YOUR_PUBLIC_KEY_HERE' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### Step 3: Test SSH Connection

```bash
ssh -i ~/.ssh/github_actions_deploy root@138.197.103.137 'echo Connected successfully'
```

### Step 4: Add Private Key to GitHub

```bash
# Copy private key
cat ~/.ssh/github_actions_deploy
```

Add to GitHub Secrets as `SSH_PRIVATE_KEY`.

---

## Phase 4: Deploy Files to Server (30 minutes)

### Step 1: Pull Latest Code

```bash
ssh root@138.197.103.137
cd /root/deploy/api
git pull origin main
```

### Step 2: Copy Scripts

```bash
chmod +x scripts/*.sh
```

### Step 3: Test Docker Compose

```bash
docker compose -f docker-compose.production.yml config
# Should show no errors
```

---

## Phase 5: Initial Deployment (1 hour)

### Step 1: Stop Current Deployment

```bash
docker compose -f docker-compose.go-only.yml down
mv docker-compose.go-only.yml docker-compose.go-only.yml.old
```

### Step 2: Start Blue Instance

```bash
docker compose -f docker-compose.production.yml up -d api-go-blue nginx
```

### Step 3: Check Logs

```bash
docker logs api-go-blue --follow
```

### Step 4: Verify Health

```bash
./scripts/health-check.sh blue
curl http://localhost:8080/api/v1/health | jq .
```

### Step 5: Run Tests

```bash
./scripts/smoke-tests.sh http://localhost:8080
```

### Step 6: Verify Production

```bash
curl https://api.screenshotbeam.com/api/v1/health | jq .
```

---

## Phase 6: Monitoring Setup (Optional - 1 hour)

### Step 1: Start Monitoring Stack

```bash
docker compose -f docker-compose.production.yml --profile monitoring up -d
```

### Step 2: Access Dashboards

| Service | URL | Credentials |
|---------|-----|-------------|
| Prometheus | http://138.197.103.137:9090 | - |
| Grafana | http://138.197.103.137:3001 | admin/admin |
| Alertmanager | http://138.197.103.137:9093 | - |

### Step 3: Configure Grafana

1. Log in to Grafana
2. Add Prometheus data source: `http://prometheus:9090`
3. Import dashboards from `monitoring/grafana-dashboards/`

---

## Phase 7: Testing (30 minutes)

### Test 1: Blue-Green Deployment

1. Make a small code change locally
2. Commit and push to main
3. Watch GitHub Actions
4. Verify green container starts
5. Verify traffic switches
6. Verify API works

### Test 2: Rollback

```bash
./scripts/rollback.sh status
./scripts/rollback.sh
curl https://api.screenshotbeam.com/api/v1/health
```

### Test 3: Health Checks

```bash
./scripts/health-check.sh blue
./scripts/smoke-tests.sh https://api.screenshotbeam.com
```

---

## Verification Checklist

### Deployment
- [ ] GitHub Actions workflow runs successfully
- [ ] Docker images build and push to GHCR
- [ ] Database migrations run automatically
- [ ] Blue-green deployment switches traffic
- [ ] Health checks pass
- [ ] Smoke tests pass
- [ ] Old container stops after traffic switch

### Rollback
- [ ] Manual rollback script works
- [ ] Automatic rollback on health check failure
- [ ] Database rollback possible
- [ ] Rollback to specific version works

### Security
- [ ] Secrets encrypted at rest
- [ ] .env.production not in Git
- [ ] SSH key authentication working
- [ ] No plain-text secrets in logs

### Monitoring (Optional)
- [ ] Prometheus scraping metrics
- [ ] Grafana dashboards showing data
- [ ] Alerts triggering on test failures
- [ ] Slack notifications working

---

## Troubleshooting

### Deployment Fails

**Symptom:** GitHub Actions fails at deploy step

**Checks:**
```bash
# Test SSH manually
ssh -i ~/.ssh/github_actions_deploy root@138.197.103.137

# Check server logs
docker logs api-go-blue

# Verify secrets
age --decrypt --identity ~/.age/key.txt .env.production.age
```

### Health Check Fails

**Symptom:** New container marked unhealthy

**Checks:**
```bash
# Check app logs
docker logs api-go-green --tail 100

# Verify database
docker exec api-go-green /migrate version

# Test health endpoint
curl http://localhost:8081/api/v1/health

# Check resources
docker stats
```

### Traffic Not Switching

**Symptom:** Nginx still serving old instance

**Checks:**
```bash
# Check nginx config
cat /root/deploy/api/docker/nginx-blue-green.conf

# Test config
docker exec screenshot-nginx nginx -t

# Reload
docker exec screenshot-nginx nginx -s reload

# Check logs
docker logs screenshot-nginx
```

---

## Daily Operations

### Deploy New Version
```bash
git add . && git commit -m "feat: New feature" && git push
# GitHub Actions handles the rest
```

### Check Status
```bash
./scripts/rollback.sh status
docker ps | grep api-go
```

### View Logs
```bash
docker logs api-go-blue --tail 100 --follow
docker logs api-go-green --tail 100 --follow
```

### Manual Rollback
```bash
./scripts/rollback.sh
```

### Rotate Secrets
```bash
./scripts/emergency-key-rotation.sh JWT_SECRET
```

---

## Next Steps

### Immediate
1. Run first production deployment
2. Monitor for 24 hours
3. Document any issues
4. Train team on rollback procedures

### Short Term
1. Set up external uptime monitoring (UptimeRobot)
2. Create runbook for common issues
3. Schedule deployment practice sessions
4. Implement automated backups

### Long Term
1. Consider Kubernetes for multi-node scaling
2. Implement canary deployments (1% traffic test)
3. Add feature flags for gradual rollout
4. Set up disaster recovery procedures
