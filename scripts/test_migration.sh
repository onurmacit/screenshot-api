#!/bin/bash
# =============================================================================
# Screenshot API - Migration Test Suite
# =============================================================================
# Usage: ./test_migration.sh <API_KEY> [API_URL]
# =============================================================================

API_KEY="${1:-YOUR_API_KEY}"
API_URL="${2:-http://localhost:8080}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Screenshot API - Migration Test Suite"
echo "=========================================="
echo "API URL: $API_URL"
echo "API Key: ${API_KEY:0:10}..."
echo ""

PASS=0
FAIL=0

# Helper function
test_result() {
    if [ "$1" = "PASS" ]; then
        echo -e "${GREEN}✓ PASS${NC}: $2"
        ((PASS++))
    else
        echo -e "${RED}✗ FAIL${NC}: $2"
        ((FAIL++))
    fi
}

# =============================================================================
# REG-001: Screenshot Endpoint Regression
# =============================================================================
echo ""
echo "=== REG-001: Screenshot Endpoint Test ==="

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/v1/renders/screenshot" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"url":"https://example.com","width":1280,"height":720}')

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    # Check required fields
    if echo "$BODY" | jq -e '.url' > /dev/null 2>&1; then
        test_result "PASS" "Screenshot returns URL"
    else
        test_result "FAIL" "Screenshot missing URL field"
    fi
    
    if echo "$BODY" | jq -e '.status' > /dev/null 2>&1; then
        test_result "PASS" "Screenshot returns status"
    else
        test_result "FAIL" "Screenshot missing status field"
    fi
else
    test_result "FAIL" "Screenshot endpoint returned $HTTP_CODE"
fi

# =============================================================================
# REG-002: Binary Response Test (Check 2 Fix)
# =============================================================================
echo ""
echo "=== REG-002: Binary Response Test ==="

BINARY_RESPONSE=$(curl -s -o /tmp/test_image.jpg -w "%{http_code}|%{content_type}" \
    -H "Accept: image/jpeg" \
    -H "X-API-Key: $API_KEY" \
    "$API_URL/api/v1/renders/?url=https://example.com&width=640&height=480")

HTTP_CODE=$(echo "$BINARY_RESPONSE" | cut -d'|' -f1)
CONTENT_TYPE=$(echo "$BINARY_RESPONSE" | cut -d'|' -f2)

if [ "$HTTP_CODE" = "200" ]; then
    test_result "PASS" "Binary response returns 200"
    
    if [[ "$CONTENT_TYPE" == *"image"* ]]; then
        test_result "PASS" "Content-Type is image ($CONTENT_TYPE)"
    else
        test_result "FAIL" "Content-Type is not image: $CONTENT_TYPE"
    fi
    
    # Check file size
    FILE_SIZE=$(stat -f%z /tmp/test_image.jpg 2>/dev/null || stat -c%s /tmp/test_image.jpg 2>/dev/null)
    if [ "$FILE_SIZE" -gt 1000 ]; then
        test_result "PASS" "Image file has content (${FILE_SIZE} bytes)"
    else
        test_result "FAIL" "Image file too small: ${FILE_SIZE} bytes"
    fi
else
    test_result "FAIL" "Binary response returned $HTTP_CODE"
fi

# =============================================================================
# REG-004: Rate Limiting Test (Check 5 Fix)
# =============================================================================
echo ""
echo "=== REG-004: Rate Limiting Headers Test ==="

RATE_RESPONSE=$(curl -s -D- -o /dev/null \
    -H "X-API-Key: $API_KEY" \
    "$API_URL/api/v1/renders/?url=https://example.com")

if echo "$RATE_RESPONSE" | grep -q "X-RateLimit-Limit"; then
    test_result "PASS" "X-RateLimit-Limit header present"
else
    test_result "FAIL" "X-RateLimit-Limit header missing"
fi

if echo "$RATE_RESPONSE" | grep -q "X-RateLimit-Remaining"; then
    test_result "PASS" "X-RateLimit-Remaining header present"
else
    test_result "FAIL" "X-RateLimit-Remaining header missing"
fi

# =============================================================================
# Error Format Test (Check 8 Fix)
# =============================================================================
echo ""
echo "=== Error Format Parity Test ==="

# Test invalid API key error format
ERROR_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/renders/screenshot" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: invalid_key_12345" \
    -d '{"url":"https://example.com"}')

if echo "$ERROR_RESPONSE" | jq -e '.detail' > /dev/null 2>&1; then
    test_result "PASS" "Error response uses 'detail' field"
else
    test_result "FAIL" "Error response does not use 'detail' field"
    echo "  Response: $ERROR_RESPONSE"
fi

# =============================================================================
# SEC-003: SSRF Prevention Test
# =============================================================================
echo ""
echo "=== SEC-003: SSRF Prevention Test ==="

SSRF_URLS=("http://localhost:5432" "http://127.0.0.1:22" "http://169.254.169.254")

for URL in "${SSRF_URLS[@]}"; do
    SSRF_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/v1/renders/screenshot" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $API_KEY" \
        -d "{\"url\":\"$URL\"}")
    
    HTTP_CODE=$(echo "$SSRF_RESPONSE" | tail -n1)
    
    if [ "$HTTP_CODE" = "422" ] || [ "$HTTP_CODE" = "400" ]; then
        test_result "PASS" "SSRF blocked: $URL"
    else
        test_result "FAIL" "SSRF not blocked: $URL (got $HTTP_CODE)"
    fi
done

# =============================================================================
# SEC-004: JWT Token Validation
# =============================================================================
echo ""
echo "=== SEC-004: JWT Token Validation Test ==="

JWT_RESPONSE=$(curl -s -w "\n%{http_code}" \
    -H "Authorization: Bearer invalid_jwt_token" \
    "$API_URL/api/v1/renders/?url=https://example.com")

HTTP_CODE=$(echo "$JWT_RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "401" ]; then
    test_result "PASS" "Invalid JWT returns 401"
else
    test_result "FAIL" "Invalid JWT returned $HTTP_CODE"
fi

# =============================================================================
# EDGE-006: Redis Degradation Test (Health Check)
# =============================================================================
echo ""
echo "=== Health Check Test ==="

HEALTH_RESPONSE=$(curl -s "$API_URL/health")

if echo "$HEALTH_RESPONSE" | jq -e '.status' > /dev/null 2>&1; then
    STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.status')
    if [ "$STATUS" = "healthy" ] || [ "$STATUS" = "ok" ]; then
        test_result "PASS" "Health check returns healthy status"
    else
        test_result "FAIL" "Health check status: $STATUS"
    fi
else
    test_result "FAIL" "Health check response invalid"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "=========================================="
echo "TEST SUMMARY"
echo "=========================================="
echo -e "Passed: ${GREEN}$PASS${NC}"
echo -e "Failed: ${RED}$FAIL${NC}"
TOTAL=$((PASS + FAIL))
PERCENT=$((PASS * 100 / TOTAL))
echo "Total:  $TOTAL"
echo "Pass Rate: $PERCENT%"
echo ""

if [ "$FAIL" -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${YELLOW}Some tests failed. Review output above.${NC}"
    exit 1
fi
