#!/bin/bash

# Configuration
URL="http://localhost:8090"
API_KEY="${1:-YOUR_API_KEY}"
TEST_URL='https://example.com'

echo "=== SNIPPET-007: Cache Hit/Miss Validator ==="
echo ""

echo '=== Test 1: Cache Miss (First Request) ==='
start_time=$(date +%s%3N)
first_resp=$(curl -s -X POST $URL/api/v1/renders/screenshot \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $API_KEY" \
  -d "{\"url\":\"$TEST_URL\",\"width\":1920}")
end_time=$(date +%s%3N)
first_latency=$((end_time - start_time))

echo "First request latency: ${first_latency}ms"
# echo "Response: $first_resp"

echo ''
echo '=== Test 2: Cache Hit (Second Request) ==='
sleep 1 # Ensure distinct request times if not cached

start_time=$(date +%s%3N)
second_resp=$(curl -s -X POST $URL/api/v1/renders/screenshot \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $API_KEY" \
  -d "{\"url\":\"$TEST_URL\",\"width\":1920}")
end_time=$(date +%s%3N)
second_latency=$((end_time - start_time))

echo "Second request latency: ${second_latency}ms"
# echo "Response: $second_resp"

echo ''
echo '=== Analysis ==='

# Criteria: Cache hit should be significantly faster (e.g., < 100ms or 50% faster)
if (( second_latency < 200 )); then
  echo "✅ Cache hit detected (latency < 200ms)"
else
  echo "⚠️  Cache might not be working (latency: ${second_latency}ms)"
fi

if (( second_latency < first_latency / 2 )); then
  echo "✅ Cache provides significant speedup"
else
  echo "⚠️  Cache speedup not significant (First: ${first_latency}ms, Second: ${second_latency}ms)"
fi

# Check if URLs are the same (S3 URL should match)
first_url=$(echo "$first_resp" | jq -r .screenshot_url)
second_url=$(echo "$second_resp" | jq -r .screenshot_url)

if [ "$first_url" != "null" ] && [ "$first_url" = "$second_url" ]; then
  echo "✅ Same S3 URL returned (cache working)"
else
  echo "❌ Different URLs or error returned (cache not working)"
  echo "First: $first_url"
  echo "Second: $second_url"
fi
