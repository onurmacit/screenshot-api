#!/bin/bash
set -e

BASE_URL=${1:-"http://localhost:8080"}
TEST_EMAIL="test_$(date +%s)@example.com"
TEST_PASSWORD="TestPass123!"

echo "====================================="
echo "Integration Tests"
echo "====================================="

# Test 1: Register user
echo "Test 1: Register new user"
REGISTER_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASSWORD\",\"full_name\":\"Test User\"}")

ACCESS_TOKEN=$(echo "$REGISTER_RESPONSE" | jq -r .access_token)

if [ "$ACCESS_TOKEN" = "null" ] || [ -z "$ACCESS_TOKEN" ]; then
  echo "✗ Registration failed"
  echo "Response: $REGISTER_RESPONSE"
  exit 1
fi

echo "✓ User registered, token: ${ACCESS_TOKEN:0:20}..."

# Test 2: Create API key
echo ""
echo "Test 2: Create API key"
API_KEY_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/api-keys" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{"name":"Integration Test Key"}')

API_KEY=$(echo "$API_KEY_RESPONSE" | jq -r .key)

if [ "$API_KEY" = "null" ] || [ -z "$API_KEY" ]; then
  echo "✗ API key creation failed"
  echo "Response: $API_KEY_RESPONSE"
  exit 1
fi

echo "✓ API key created: ${API_KEY:0:20}..."

# Test 3: Take screenshot
echo ""
echo "Test 3: Capture screenshot"
SCREENSHOT_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/renders/screenshot" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"url":"https://example.com","width":1920,"height":1080}')

SCREENSHOT_URL=$(echo "$SCREENSHOT_RESPONSE" | jq -r .screenshot_url)

if [ "$SCREENSHOT_URL" = "null" ] || [ -z "$SCREENSHOT_URL" ]; then
  echo "✗ Screenshot failed"
  echo "Response: $SCREENSHOT_RESPONSE"
  exit 1
fi

echo "✓ Screenshot captured: $SCREENSHOT_URL"

# Test 4: Check usage stats
echo ""
echo "Test 4: Check usage stats"
USAGE_RESPONSE=$(curl -s -H "X-API-Key: $API_KEY" "$BASE_URL/api/v1/usage/stats")

REQUESTS_COUNT=$(echo "$USAGE_RESPONSE" | jq -r .requests_this_month)

if [ "$REQUESTS_COUNT" != "1" ]; then
  echo "✗ Usage stats incorrect (expected 1, got $REQUESTS_COUNT)"
  exit 1
fi

echo "✓ Usage stats correct: $REQUESTS_COUNT request"

# Test 5: List jobs
echo ""
echo "Test 5: List render jobs"
JOBS_RESPONSE=$(curl -s -H "X-API-Key: $API_KEY" "$BASE_URL/api/v1/renders/jobs")

JOBS_COUNT=$(echo "$JOBS_RESPONSE" | jq -r '.jobs | length')

if [ "$JOBS_COUNT" -lt "1" ]; then
  echo "✗ No jobs found"
  exit 1
fi

echo "✓ Found $JOBS_COUNT job(s)"

echo ""
echo "====================================="
echo "✅ All integration tests passed!"
echo "====================================="
