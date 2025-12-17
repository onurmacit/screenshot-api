#!/bin/bash
# Comprehensive Screenshot API Test Suite
# This script runs all tests and generates a detailed report

API_URL="${API_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-sk_live_7ec8becd4fb1f78ff53003f1d2ff700f7e39721fcd06a20b316fc6776d361713}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Results storage
declare -a TEST_RESULTS=()

echo ""
echo "=========================================="
echo "  Screenshot API - Comprehensive Tests"
echo "=========================================="
echo "API URL: $API_URL"
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Helper function
run_test() {
    local test_name="$1"
    local expected_status="$2"
    shift 2
    local response="$*"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    if echo "$response" | grep -q "\"status\":\"$expected_status\""; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
        echo -e "${GREEN}✅ PASS${NC} - $test_name"
        TEST_RESULTS+=("✅ $test_name")
        return 0
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
        echo -e "${RED}❌ FAIL${NC} - $test_name"
        echo "   Response: $(echo "$response" | head -c 200)"
        TEST_RESULTS+=("❌ $test_name")
        return 1
    fi
}

run_status_test() {
    local test_name="$1"
    local expected_code="$2"
    local actual_code="$3"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    if [ "$actual_code" = "$expected_code" ]; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
        echo -e "${GREEN}✅ PASS${NC} - $test_name (HTTP $actual_code)"
        TEST_RESULTS+=("✅ $test_name")
        return 0
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
        echo -e "${RED}❌ FAIL${NC} - $test_name (Expected: $expected_code, Got: $actual_code)"
        TEST_RESULTS+=("❌ $test_name")
        return 1
    fi
}

echo "-------------------------------------------"
echo "1. HEALTH CHECK TESTS"
echo "-------------------------------------------"

# Test 1: Health Check
response=$(curl -s -w "\n%{http_code}" "$API_URL/api/v1/health")
http_code=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -1)

TOTAL_TESTS=$((TOTAL_TESTS + 1))
if echo "$body" | grep -q '"status":"healthy"'; then
    PASSED_TESTS=$((PASSED_TESTS + 1))
    echo -e "${GREEN}✅ PASS${NC} - Health Check Endpoint"
    TEST_RESULTS+=("✅ Health Check")
else
    FAILED_TESTS=$((FAILED_TESTS + 1))
    echo -e "${RED}❌ FAIL${NC} - Health Check Endpoint"
    TEST_RESULTS+=("❌ Health Check")
fi

# Test individual services from health check
for service in database redis s3 celery; do
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if echo "$body" | grep -q "\"$service\":\"healthy\""; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
        echo -e "${GREEN}✅ PASS${NC} - $service Service Health"
        TEST_RESULTS+=("✅ $service Service")
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
        echo -e "${RED}❌ FAIL${NC} - $service Service Health"
        TEST_RESULTS+=("❌ $service Service")
    fi
done

echo ""
echo "-------------------------------------------"
echo "2. SCREENSHOT FORMAT TESTS"
echo "-------------------------------------------"

# Test PNG Format
echo -n "Testing PNG format... "
response=$(curl -s -X POST "$API_URL/api/v1/renders/screenshot" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"url":"https://example.com","format":"png","width":1920,"height":1080}')
run_test "PNG Screenshot" "completed" "$response"

# Test JPEG Format
echo -n "Testing JPEG format... "
response=$(curl -s -X POST "$API_URL/api/v1/renders/screenshot" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"url":"https://example.com","format":"jpeg","quality":100,"width":1920,"height":1080}')
run_test "JPEG Screenshot (Quality 100)" "completed" "$response"

# Test WebP Format
echo -n "Testing WebP format... "
response=$(curl -s -X POST "$API_URL/api/v1/renders/screenshot" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"url":"https://example.com","format":"webp","quality":100,"width":1920,"height":1080}')
run_test "WebP Screenshot (Quality 100)" "completed" "$response"

echo ""
echo "-------------------------------------------"
echo "3. RESOLUTION & SCALE TESTS"
echo "-------------------------------------------"

# Test 1x Scale Factor
echo -n "Testing 1x scale factor... "
response=$(curl -s -X POST "$API_URL/api/v1/renders/screenshot" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"url":"https://example.com","width":1920,"height":1080,"device_scale_factor":1}')
run_test "1x Scale Factor" "completed" "$response"

# Test 2x Scale Factor (HD)
echo -n "Testing 2x HD scale factor... "
response=$(curl -s -X POST "$API_URL/api/v1/renders/screenshot" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"url":"https://example.com","width":1920,"height":1080,"device_scale_factor":2}')
run_test "2x HD Scale Factor" "completed" "$response"

# Test Custom Resolution
echo -n "Testing custom resolution 1280x720... "
response=$(curl -s -X POST "$API_URL/api/v1/renders/screenshot" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"url":"https://example.com","width":1280,"height":720}')
run_test "Custom Resolution 1280x720" "completed" "$response"

echo ""
echo "-------------------------------------------"
echo "4. WEBSITE COMPATIBILITY TESTS"
echo "-------------------------------------------"

# Test Google
echo -n "Testing Google.com... "
response=$(curl -s -X POST "$API_URL/api/v1/renders/screenshot" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"url":"https://www.google.com","width":1920,"height":1080,"wait_until":"networkidle","delay":500}')
run_test "Google.com Screenshot" "completed" "$response"

# Test GitHub
echo -n "Testing GitHub.com... "
response=$(curl -s -X POST "$API_URL/api/v1/renders/screenshot" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"url":"https://github.com","width":1920,"height":1080,"wait_until":"domcontentloaded"}')
run_test "GitHub.com Screenshot" "completed" "$response"

echo ""
echo "-------------------------------------------"
echo "5. ERROR HANDLING TESTS"
echo "-------------------------------------------"

# Test Localhost Blocking
echo -n "Testing localhost blocking... "
response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/v1/renders/screenshot" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"url":"http://localhost:8000","width":1920,"height":1080}')
http_code=$(echo "$response" | tail -1)
# Both 400 and 422 are acceptable for blocking localhost
if [ "$http_code" = "422" ] || [ "$http_code" = "400" ]; then
    PASSED_TESTS=$((PASSED_TESTS + 1))
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo -e "${GREEN}✅ PASS${NC} - Localhost Blocking (HTTP $http_code)"
    TEST_RESULTS+=("✅ Localhost Blocking")
else
    run_status_test "Localhost Blocking" "400 or 422" "$http_code"
fi

# Test Invalid URL
echo -n "Testing invalid URL handling... "
response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/v1/renders/screenshot" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"url":"not-a-valid-url","width":1920,"height":1080}')
http_code=$(echo "$response" | tail -1)
run_status_test "Invalid URL Rejection" "422" "$http_code"

# Test Missing API Key
echo -n "Testing missing API key... "
response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/v1/renders/screenshot" \
    -H "Content-Type: application/json" \
    -d '{"url":"https://example.com"}')
http_code=$(echo "$response" | tail -1)
run_status_test "Missing API Key Rejection" "401" "$http_code"

echo ""
echo "-------------------------------------------"
echo "6. API ENDPOINT TESTS"
echo "-------------------------------------------"

# Test Root Endpoint
echo -n "Testing root endpoint... "
response=$(curl -s -w "\n%{http_code}" "$API_URL/")
http_code=$(echo "$response" | tail -1)
run_status_test "Root Endpoint" "200" "$http_code"

# Test Docs Endpoint
echo -n "Testing docs endpoint... "
response=$(curl -s -w "\n%{http_code}" "$API_URL/docs")
http_code=$(echo "$response" | tail -1)
run_status_test "Docs Endpoint" "200" "$http_code"

# Test OpenAPI Endpoint
echo -n "Testing OpenAPI endpoint... "
response=$(curl -s -w "\n%{http_code}" "$API_URL/openapi.json")
http_code=$(echo "$response" | tail -1)
run_status_test "OpenAPI Endpoint" "200" "$http_code"

echo ""
echo "=========================================="
echo "            TEST SUMMARY"
echo "=========================================="
echo ""
echo -e "Total Tests:  $TOTAL_TESTS"
echo -e "Passed:       ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed:       ${RED}$FAILED_TESTS${NC}"
echo ""

# Calculate percentage
if [ $TOTAL_TESTS -gt 0 ]; then
    PASS_RATE=$((PASSED_TESTS * 100 / TOTAL_TESTS))
    echo -e "Pass Rate:    ${GREEN}$PASS_RATE%${NC}"
else
    PASS_RATE=0
fi

echo ""
echo "-------------------------------------------"
echo "Detailed Results:"
echo "-------------------------------------------"
for result in "${TEST_RESULTS[@]}"; do
    echo "  $result"
done

echo ""
echo "=========================================="
echo "Test completed at $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# Exit with failure if any test failed
if [ $FAILED_TESTS -gt 0 ]; then
    exit 1
fi
exit 0
