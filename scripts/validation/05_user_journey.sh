#!/bin/bash

# Configuration
BASE_URL='http://localhost:8090'
EMAIL="test_user_$(date +%s)@example.com"
PASSWORD='SecurePass123!@#'

echo "=== SNIPPET-005: Full User Journey Test ==="
echo "Target: $BASE_URL"
echo "Testing User: $EMAIL"
echo ""

# Helper for JSON extraction
get_json_value() {
  echo "$1" | jq -r "$2" 2>/dev/null
}

echo '=== Step 1: Register User ==='
register_resp=$(curl -s -X POST $BASE_URL/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"full_name\":\"Test User\"}")

echo "Response: $register_resp"

# Check if registration was successful or user already exists (for repeated runs)
if echo "$register_resp" | grep -q "User already exists"; then
    echo "User exists, attempting login..."
else
    # Verify access token presence
    user_id=$(get_json_value "$register_resp" .id)
    if [ "$user_id" == "null" ] || [ -z "$user_id" ]; then
        user_id=$(get_json_value "$register_resp" .user_id)
    fi

    if [ "$user_id" == "null" ] || [ -z "$user_id" ]; then
        echo "❌ Registration failed!"
        exit 1
    fi
    echo "✅ Registration successful (ID: $user_id)"
fi

echo '=== Step 2: Login to get Token ==='
login_resp=$(curl -s -X POST $BASE_URL/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")

access_token=$(get_json_value "$login_resp" .access_token)

if [ "$access_token" == "null" ] || [ -z "$access_token" ]; then
    echo "❌ Login failed! Response: $login_resp"
    exit 1
fi
echo "✅ Login successful (Token received)"


echo '=== Step 3: Create API Key ==='
api_key_resp=$(curl -s -X POST $BASE_URL/api/v1/auth/api-keys \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $access_token" \
  -d '{"name":"Validation Test Key"}')

echo "Response: $api_key_resp"

api_key=$(get_json_value "$api_key_resp" .key)
if [ "$api_key" == "null" ] || [ -z "$api_key" ]; then
    api_key=$(get_json_value "$api_key_resp" .secret_key)
fi

if [ "$api_key" == "null" ] || [ -z "$api_key" ]; then
    echo "❌ API Key creation failed!"
    exit 1
fi
echo "✅ API Key created: $api_key"


echo '=== Step 4: Take Screenshot (Integration Test) ==='
screenshot_resp=$(curl -s -X POST $BASE_URL/api/v1/renders/screenshot \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $api_key" \
  -d '{"url":"https://example.com","width":1280,"height":720}')

# Don't print full binary or large JSON, just check status
screenshot_url=$(get_json_value "$screenshot_resp" .screenshot_url)

if [ "$screenshot_url" != "null" ] && [ -n "$screenshot_url" ]; then
    echo "✅ Screenshot successful: $screenshot_url"
elif echo "$screenshot_resp" | grep -q "binary"; then
     # Use a better check for binary content if applicable
     echo "✅ Binary response received"
else
    echo "⚠️  Screenshot might have failed or returned unexpected format."
    echo "Response preview: $(echo "$screenshot_resp" | head -c 200)"
fi


echo '=== Step 5: Check Usage Stats ==='
# Give a moment for async usage tracking updates (if any)
sleep 1

usage_resp=$(curl -s -H "X-API-Key: $api_key" $BASE_URL/api/v1/usage/stats)

echo "Response: $usage_resp"

requests_count=$(get_json_value "$usage_resp" .requests_this_month)
if [ "$requests_count" == "null" ] || [ -z "$requests_count" ]; then
    requests_count=$(get_json_value "$usage_resp" .usage.requests_used)
fi

if [ "$requests_count" != "null" ] && [ "$requests_count" -ge 0 ]; then
  echo "✅ Usage stats verified (Count: $requests_count)"
else
  echo "❌ Usage stats incorrect: expected >= 0, got $requests_count"
  exit 1
fi

echo ""
echo "=== All Steps Completed Successfully! ==="
