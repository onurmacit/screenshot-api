#!/bin/bash
set -e

# Configuration
BASE_URL=${1:-"http://localhost:8080"}
API_KEY=${API_KEY:-""}
VERBOSE=${VERBOSE:-false}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0

function test_endpoint() {
  local name=$1
  local method=$2
  local endpoint=$3
  local expected_status=$4
  local headers=${5:-""}
  local body=${6:-""}
  
  echo -n "Testing: $name... "
  
  if [ "$VERBOSE" = true ]; then
    echo ""
    echo "  Method: $method"
    echo "  URL: $BASE_URL$endpoint"
  fi
  
  # Build curl command
  CURL_CMD="curl -s -o /dev/null -w '%{http_code}' -X $method"
  
  if [ -n "$headers" ]; then
    CURL_CMD="$CURL_CMD $headers"
  fi
  
  if [ -n "$body" ]; then
    CURL_CMD="$CURL_CMD -d '$body'"
  fi
  
  CURL_CMD="$CURL_CMD $BASE_URL$endpoint"
  
  # Execute
  RESPONSE=$(eval $CURL_CMD)
  
  if [ "$RESPONSE" = "$expected_status" ]; then
    echo -e "${GREEN}✓ PASS${NC} (HTTP $RESPONSE)"
    ((PASSED++))
  else
    echo -e "${RED}✗ FAIL${NC} (Expected: $expected_status, Got: $RESPONSE)"
    ((FAILED++))
  fi
}

echo "====================================="
echo "Screenshot API - Smoke Tests"
echo "Target: $BASE_URL"
echo "====================================="
echo ""

# Test 1: Health Check
test_endpoint "Health Check" "GET" "/api/v1/health" "200"

# Test 2: Readiness
test_endpoint "Readiness Probe" "GET" "/api/v1/health/ready" "200"

# Test 3: Liveness
test_endpoint "Liveness Probe" "GET" "/api/v1/health/live" "200"

# Test 4: Invalid endpoint (404)
test_endpoint "404 Handling" "GET" "/api/v1/invalid" "404"

# Test 5: Public demo (rate limited but should return 200 or 429)
test_endpoint "Demo Endpoint" "POST" "/api/v1/renders/demo" "200" "-H 'Content-Type: application/json'" '{"url":"https://example.com"}'

# Test 6: Auth required endpoint (401)
test_endpoint "Auth Required" "GET" "/api/v1/renders/jobs" "401"

# Test 7: Metrics endpoint (should be 200 from localhost)
if [ "$BASE_URL" = "http://localhost:8080" ] || [ "$BASE_URL" = "http://127.0.0.1:8080" ]; then
  test_endpoint "Metrics Endpoint" "GET" "/metrics" "200"
fi

# Test 8: OPTIONS (CORS preflight)
test_endpoint "CORS Preflight" "OPTIONS" "/api/v1/health" "204" "-H 'Origin: https://dashboard.screenshotbeam.com'"

echo ""
echo "====================================="
echo "Results: ${GREEN}$PASSED passed${NC}, ${RED}$FAILED failed${NC}"
echo "====================================="

if [ $FAILED -gt 0 ]; then
  exit 1
fi

exit 0
