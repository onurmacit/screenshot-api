#!/bin/bash
# Quick Test Script - Tests basic functionality

API_URL="${API_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-sk_live_7ec8becd4fb1f78ff53003f1d2ff700f7e39721fcd06a20b316fc6776d361713}"

echo "Quick Screenshot API Test"
echo "========================"

# Test 1: Basic PNG
echo -n "Test 1: Basic PNG... "
response=$(curl -s -X POST "$API_URL/api/v1/renders/screenshot" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"url":"https://example.com","format":"png","width":1920,"height":1080}')

if echo "$response" | grep -q '"status":"completed"'; then
    echo "✅ PASS"
else
    echo "❌ FAIL"
    echo "$response" | head -5
fi

# Test 2: Google with HD
echo -n "Test 2: Google HD Screenshot... "
response=$(curl -s -X POST "$API_URL/api/v1/renders/screenshot" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"url":"https://www.google.com","width":1920,"height":1080,"device_scale_factor":2.0,"wait_until":"networkidle","delay":1000}')

if echo "$response" | grep -q '"status":"completed"'; then
    file_size=$(echo "$response" | grep -o '"file_size":[0-9]*' | cut -d':' -f2)
    echo "✅ PASS (Size: ${file_size} bytes)"
else
    echo "❌ FAIL"
    echo "$response" | head -5
fi

# Test 3: JPEG Quality
echo -n "Test 3: JPEG High Quality... "
response=$(curl -s -X POST "$API_URL/api/v1/renders/screenshot" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"url":"https://example.com","format":"jpeg","quality":100,"width":1920,"height":1080}')

if echo "$response" | grep -q '"status":"completed"'; then
    echo "✅ PASS"
else
    echo "❌ FAIL"
fi

echo ""
echo "Quick test completed!"

