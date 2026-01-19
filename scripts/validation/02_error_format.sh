#!/bin/bash

# Configuration
FASTAPI_URL="http://localhost:8000"
GO_URL="http://localhost:8090"

echo "=== SNIPPET-002: Error Response Format Validator ==="
echo ""

test_error_format() {
  local endpoint=$1
  local expected_status=$2
  
  echo "Testing Endpoint: $endpoint"
  
  # Fetch responses
  fastapi_response=$(curl -s -w '\n%{http_code}' $FASTAPI_URL$endpoint 2>/dev/null)
  go_response=$(curl -s -w '\n%{http_code}' $GO_URL$endpoint 2>/dev/null)
  
  # Parse body and status
  fastapi_body=$(echo "$fastapi_response" | head -n -1)
  fastapi_status=$(echo "$fastapi_response" | tail -n 1)
  
  go_body=$(echo "$go_response" | head -n -1)
  go_status=$(echo "$go_response" | tail -n 1)
  
  echo "  FastAPI Status: $fastapi_status, Body: $fastapi_body"
  echo "  Go Status:      $go_status, Body: $go_body"
  
  # Check status code
  if [ "$fastapi_status" = "$go_status" ]; then
    echo "  ✅ Status code match: $fastapi_status"
  else
    echo "  ❌ Status mismatch: FastAPI=$fastapi_status, Go=$go_status"
  fi
  
  # Check 'detail' key exists
  fastapi_has_detail=$(echo "$fastapi_body" | jq 'has("detail")' 2>/dev/null)
  go_has_detail=$(echo "$go_body" | jq 'has("detail")' 2>/dev/null)
  
  if [ "$fastapi_has_detail" = "true" ] && [ "$go_has_detail" = "true" ]; then
    echo "  ✅ Structure match: Both use 'detail' key"
  else
    echo "  ❌ Structure mismatch: Go should use 'detail' key"
    echo "     FastAPI has detail: $fastapi_has_detail"
    echo "     Go has detail: $go_has_detail"
  fi
  
  echo "---------------------------------------------------"
}

# Test scenarios
# 1. No API Key (401/403)
test_error_format '/api/v1/renders' 403

# 2. Validation Error (422) - Sending empty body where JSON expected
# Note: Behavior might differ slightly depending on framework validation
echo "Testing Validation Error (Empty Body)..."
curl -s -H "Content-Type: application/json" -X POST -d '{}' $GO_URL/api/v1/auth/register | jq .

# 3. Not Found (404)
test_error_format '/api/v1/non_existent_endpoint' 404
