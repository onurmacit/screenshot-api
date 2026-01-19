#!/bin/bash

# Configuration
GO_URL="http://localhost:8090"
API_KEY="${1:-YOUR_API_KEY}"

echo "=== SNIPPET-006: SSRF Prevention Test ==="
echo ""

test_ssrf() {
  local url=$1
  
  echo "Testing SSRF protection: $url"
  
  # Perform request
  response=$(curl -s -w '\n%{http_code}' -X POST \
    $GO_URL/api/v1/renders/screenshot \
    -H 'Content-Type: application/json' \
    -H "X-API-Key: $API_KEY" \
    -d "{\"url\":\"$url\"}")
  
  status_code=$(echo "$response" | tail -n 1)
  body=$(echo "$response" | head -n -1)
  
  if [ "$status_code" = "422" ]; then
    echo "  ✅ Blocked: 422 Unprocessable Entity - Expected for blocked URLs/IPs"
  elif [ "$status_code" = "400" ]; then
    echo "  ✅ Blocked: 400 Bad Request - Acceptable blocking response"
  else
    echo "  ❌ POTENTIAL VULNERABILITY: Not blocked! Status: $status_code"
    echo "     Body: $(echo "$body" | head -c 100)..."
  fi
  echo "---------------------------------------------------"
}

# Test internal IPs and sensitive endpoints
test_ssrf 'http://localhost:5432'
test_ssrf 'http://127.0.0.1:6379'
test_ssrf 'http://169.254.169.254/latest/meta-data/'
test_ssrf 'http://192.168.1.1'
test_ssrf 'http://10.0.0.1'

echo ''
echo 'Testing valid URL (should work):'
valid_response=$(curl -s -w '\n%{http_code}' -X POST \
  $GO_URL/api/v1/renders/screenshot \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $API_KEY" \
  -d '{"url":"https://example.com"}')

valid_status=$(echo "$valid_response" | tail -n 1)

if [ "$valid_status" = "200" ]; then
  echo '✅ Valid URL works correctly'
else
  echo "❌ Valid URL failed (Status: $valid_status)"
fi
