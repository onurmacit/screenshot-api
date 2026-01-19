#!/bin/bash

# Configuration
URL="http://localhost:8090"
API_KEY="${1:-YOUR_API_KEY}"
TEST_URL='https://example.com'

echo "=== SNIPPET-010: Binary vs JSON Response Validator ==="
echo ""

echo '=== Test 1: Binary PNG Response ==='
# Request with Accept: image/png
curl -s -H "Accept: image/png" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  "$URL/api/v1/renders/screenshot" \
  -d "{\"url\":\"$TEST_URL\",\"width\":800}" \
  > test_image.png

if file test_image.png | grep -q "PNG image data"; then
  echo "✅ Correct PNG binary response (Magic bytes verified)"
else
  echo "❌ Not a valid PNG file"
  file test_image.png
  echo "Preview: $(head -c 50 test_image.png)"
fi

echo ''
echo '=== Test 2: JSON Response ==='
# Request with Accept: application/json
json_resp=$(curl -s -H "Accept: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  "$URL/api/v1/renders/screenshot" \
  -d "{\"url\":\"$TEST_URL\",\"width\":800}")

if echo "$json_resp" | jq -e . > /dev/null 2>&1; then
  echo "✅ Valid JSON response"
  # Optional: Check if it contains screenshot_url
  if echo "$json_resp" | jq -e 'has("screenshot_url")' > /dev/null; then
       echo "   Contains 'screenshot_url'"
  fi
else
  echo "❌ Invalid JSON response"
  echo "$json_resp" | head -c 100
fi

echo ''
echo '=== Test 3: Content-Type Headers ==='
# Check headers for image request
headers=$(curl -s -I -H "Accept: image/png" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  "$URL/api/v1/renders/screenshot" \
  -d "{\"url\":\"$TEST_URL\",\"width\":800}")

if echo "$headers" | grep -i "Content-Type: image/png" > /dev/null; then
  echo "✅ Correct Content-Type header: image/png"
else
  echo "❌ Wrong Content-Type header"
  echo "$headers" | grep -i "Content-Type"
fi

# Cleanup
rm -f test_image.png
