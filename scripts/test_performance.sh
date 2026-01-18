#!/bin/bash
# =============================================================================
# Screenshot API - Performance & Load Test Suite (Q011, Q012)
# =============================================================================
# Requirements: 
#   - ab (Apache Bench): brew install httpd
#   - wrk: brew install wrk
#   - jq: brew install jq
# =============================================================================

API_KEY="${1:-YOUR_API_KEY}"
API_URL="${2:-http://localhost:8080}"
TEST_URL="https://example.com"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=========================================="
echo "Screenshot API - Performance Test Suite"
echo "=========================================="
echo "API URL: $API_URL"
echo "Test URL: $TEST_URL"
echo ""

# Check dependencies
check_deps() {
    local missing=0
    for cmd in ab wrk jq curl; do
        if ! command -v $cmd &> /dev/null; then
            echo -e "${RED}Missing dependency: $cmd${NC}"
            missing=1
        fi
    done
    if [ $missing -eq 1 ]; then
        echo "Please install missing dependencies and try again."
        exit 1
    fi
}

check_deps

# =============================================================================
# Q011: Performance Tests
# =============================================================================

echo -e "\n${BLUE}=== Q011: Performance Tests ===${NC}\n"

# Test 1: Low Load (10 concurrent, 100 requests)
echo -e "${YELLOW}Test 1: Low Load (10 concurrent, 100 requests)${NC}"
echo "Target: mean < 500ms, p95 < 1000ms, RPS > 20"
echo ""

ab -n 100 -c 10 -H "X-API-Key: $API_KEY" \
   "$API_URL/api/v1/renders/?url=$TEST_URL&width=640&height=480" 2>/dev/null | \
   grep -E "(Requests per second|Time per request|Percentage of the requests)"

echo ""

# Test 2: Health endpoint stress test (quick baseline)
echo -e "${YELLOW}Test 2: Health Endpoint Baseline (100 concurrent, 1000 requests)${NC}"
echo ""

ab -n 1000 -c 100 "$API_URL/health" 2>/dev/null | \
   grep -E "(Requests per second|Time per request|Failed requests)"

echo ""

# Test 3: wrk short burst
echo -e "${YELLOW}Test 3: wrk Short Burst (4 threads, 50 connections, 10 seconds)${NC}"
echo ""

wrk -t4 -c50 -d10s --latency -H "X-API-Key: $API_KEY" \
    "$API_URL/api/v1/renders/?url=$TEST_URL" 2>/dev/null

echo ""

# =============================================================================
# Q012: Memory Usage Check
# =============================================================================

echo -e "\n${BLUE}=== Q012: Memory Usage Check ===${NC}\n"

# Get initial memory from /metrics endpoint
echo "Fetching memory metrics from Prometheus endpoint..."

METRICS=$(curl -s "$API_URL/metrics" 2>/dev/null)

if [ -n "$METRICS" ]; then
    echo "Process Metrics:"
    echo "$METRICS" | grep -E "^(go_memstats_|go_goroutines|process_)" | head -20
    
    # Extract key metrics
    GOROUTINES=$(echo "$METRICS" | grep "^go_goroutines " | awk '{print $2}')
    HEAP_ALLOC=$(echo "$METRICS" | grep "^go_memstats_heap_alloc_bytes " | awk '{print $2}')
    HEAP_MB=$(echo "scale=2; ${HEAP_ALLOC:-0} / 1048576" | bc 2>/dev/null || echo "N/A")
    
    echo ""
    echo -e "Current Goroutines: ${GREEN}${GOROUTINES:-N/A}${NC}"
    echo -e "Current Heap (MB): ${GREEN}${HEAP_MB:-N/A}${NC}"
else
    echo -e "${YELLOW}Cannot fetch /metrics. Make sure Prometheus middleware is enabled.${NC}"
fi

echo ""

# =============================================================================
# Q013: Goroutine Leak Detection
# =============================================================================

echo -e "\n${BLUE}=== Q013: Goroutine Leak Detection ===${NC}\n"

# Get baseline goroutines
BEFORE=$(curl -s "$API_URL/metrics" 2>/dev/null | grep "^go_goroutines " | awk '{print $2}')

if [ -n "$BEFORE" ]; then
    echo "Baseline Goroutines: $BEFORE"
    echo "Sending 100 requests..."
    
    # Send burst of requests
    for i in {1..100}; do
        curl -s -o /dev/null -H "X-API-Key: $API_KEY" \
            "$API_URL/api/v1/health" &
    done
    wait
    
    echo "Waiting 5 seconds for cleanup..."
    sleep 5
    
    AFTER=$(curl -s "$API_URL/metrics" 2>/dev/null | grep "^go_goroutines " | awk '{print $2}')
    
    echo "After Goroutines: $AFTER"
    
    DIFF=$(echo "$AFTER - $BEFORE" | bc 2>/dev/null || echo "0")
    
    if [ "$DIFF" -lt 10 ]; then
        echo -e "${GREEN}✓ No significant goroutine leak detected (diff: $DIFF)${NC}"
    else
        echo -e "${RED}⚠ Potential goroutine leak detected (diff: $DIFF)${NC}"
    fi
else
    echo -e "${YELLOW}Cannot fetch goroutine count from /metrics${NC}"
fi

echo ""

# =============================================================================
# Summary
# =============================================================================

echo "=========================================="
echo "TEST SUMMARY"
echo "=========================================="
echo ""
echo "Performance tests completed. Review output above for:"
echo "  - Q011: Mean latency, P95 latency, RPS"
echo "  - Q012: Memory usage stability"
echo "  - Q013: Goroutine leak detection"
echo ""
echo "For extended testing, run:"
echo "  wrk -t4 -c100 -d1h --latency -H 'X-API-Key: KEY' $API_URL/health"
echo ""
