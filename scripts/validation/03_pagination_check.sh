#!/bin/bash

# Configuration
FASTAPI_URL="http://localhost:8000"
GO_URL="http://localhost:8090"
API_KEY="${1:-YOUR_API_KEY}"

if [ "$API_KEY" = "YOUR_API_KEY" ]; then
    echo "⚠️  Warning: API_KEY not provided as argument."
    echo "Usage: ./03_pagination_check.sh <api_key>"
fi

echo "=== SNIPPET-003: Pagination Format Validator ==="
echo ""

test_pagination() {
  local endpoint=$1
  
  echo "Testing pagination: $endpoint"
  
  # Fetch responses
  fastapi_resp=$(curl -s -H "X-API-Key: $API_KEY" $FASTAPI_URL$endpoint 2>/dev/null)
  go_resp=$(curl -s -H "X-API-Key: $API_KEY" $GO_URL$endpoint 2>/dev/null)
  
  # Expected keys
  for key in items total page size pages; do
    # Only check if response is valid JSON
    if ! echo "$fastapi_resp" | jq -e . >/dev/null 2>&1; then
        echo "  ⚠️  FastAPI response is not valid JSON (skipping checks)"
        continue
    fi
    
    if ! echo "$go_resp" | jq -e . >/dev/null 2>&1; then
        echo "  ⚠️  Go response is not valid JSON (skipping checks)"
        if echo "$go_resp" | grep -q "401"; then
             echo "     Go returned 401 Unauthorized - Check API Key"
        fi
        continue
    fi

    # Check key existence
    # Note: Using jq -e to check for existence (exit code 0 if found)
    fastapi_has=$(echo "$fastapi_resp" | jq -r "if has(\"$key\") then \"true\" else \"false\" end")
    go_has=$(echo "$go_resp" | jq -r "if has(\"$key\") then \"true\" else \"false\" end")
    
    if [ "$fastapi_has" = "true" ] && [ "$go_has" = "true" ]; then
      echo "  ✅ Key '$key' exists in both"
    else
      echo "  ❌ Key '$key' mismatch! FastAPI=$fastapi_has, Go=$go_has"
    fi
  done
  echo "---------------------------------------------------"
}

# Test scenarios
# Note: Ensure these endpoints support pagination and the API Key is valid
test_pagination '/api/v1/renders?page=1&size=20'
test_pagination '/api/v1/admin/users?page=1&size=10'
