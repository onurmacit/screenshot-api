# Monitoring Quick Start Guide

## Starting the Monitoring Stack

```bash
# Start with monitoring profile
docker compose -f docker-compose.production.yml --profile monitoring up -d

# Or just monitoring services
docker compose -f docker-compose.production.yml up -d prometheus grafana alertmanager
```

## Accessing Services

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3001 | admin / admin |
| Prometheus | http://localhost:9090 | - |
| Alertmanager | http://localhost:9093 | - |

## Initial Setup

### 1. Configure Grafana Data Source

1. Log into Grafana at http://localhost:3001
2. Go to Configuration → Data Sources
3. Add Prometheus:
   - URL: `http://prometheus:9090`
   - Access: Server (default)
4. Save & Test

### 2. Import Dashboards

1. Go to Dashboards → Import
2. Upload `monitoring/grafana-dashboards/api-dashboard.json`
3. Select Prometheus data source
4. Import

### 3. Configure Slack Alerts

1. Create Slack Incoming Webhook:
   - Go to https://api.slack.com/apps
   - Create new app → Incoming Webhooks
   - Create webhook for your channel
   
2. Set environment variable:
   ```bash
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
   ```

3. Update alertmanager.yml with your webhook URL

### 4. Test Alerts

```bash
# Stop an instance to trigger alert
docker stop api-go-blue

# Check Alertmanager UI
open http://localhost:9093

# Start it back
docker start api-go-blue
```

## Available Metrics

### HTTP Metrics
- `http_requests_total{method, endpoint, status}` - Total requests counter
- `http_request_duration_seconds{method, endpoint}` - Request latency histogram
- `http_active_connections` - Current active connections

### Screenshot Metrics
- `screenshot_requests_total{status, format}` - Screenshot request counter
- `screenshot_duration_seconds{format}` - Screenshot capture duration

### System Metrics (via node-exporter)
- `node_cpu_seconds_total` - CPU usage
- `node_memory_MemAvailable_bytes` - Available memory
- `node_filesystem_avail_bytes` - Disk space

## Alert Rules

| Alert | Condition | Severity |
|-------|-----------|----------|
| HighErrorRate | >5% errors for 2m | Critical |
| APIDown | Instance down for 1m | Critical |
| HighLatency | p95 >2s for 5m | Warning |
| HighMemoryUsage | >90% memory for 5m | Warning |
| HighCPUUsage | >80% CPU for 10m | Warning |

## Useful PromQL Queries

```promql
# Request rate per second
sum(rate(http_requests_total[5m]))

# Error rate percentage
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))

# 95th percentile latency
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# Memory usage percentage
container_memory_usage_bytes{name=~"api-go-.*"} / container_spec_memory_limit_bytes{name=~"api-go-.*"}

# Screenshot success rate
sum(rate(screenshot_requests_total{status="success"}[5m])) / sum(rate(screenshot_requests_total[5m]))
```

## Troubleshooting

### Prometheus not scraping targets

```bash
# Check targets
curl http://localhost:9090/api/v1/targets

# Check container connectivity
docker exec prometheus wget -qO- http://api-go-blue:8080/metrics
```

### Alertmanager not sending alerts

```bash
# Check alertmanager logs
docker logs screenshot-alertmanager

# Test webhook manually
curl -X POST $SLACK_WEBHOOK_URL -d '{"text":"Test alert"}'
```

### Grafana dashboard not loading

```bash
# Check Prometheus connection
docker exec grafana wget -qO- http://prometheus:9090/api/v1/query?query=up
```
