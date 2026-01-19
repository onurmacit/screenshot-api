#!/bin/bash

# Configuration
FASTAPI_URL="http://localhost:8000"
GO_URL="http://localhost:8090"
API_KEY="${1:-YOUR_API_KEY}"
TEST_URL="https://example.com"
REQUESTS=100
CONCURRENCY=10

echo "=== SNIPPET-004: Latency Comparison Script ==="
echo "Requests: $REQUESTS | Concurrency: $CONCURRENCY"
echo ""

# Check if ab is installed
if ! command -v ab &> /dev/null; then
  echo "Error: Apache Bench (ab) not found. Please install apache2-utils or httpd-tools."
  exit 1
fi

echo 'Running latency comparison...'

# FastAPI benchmark
echo '=== FastAPI Benchmark ==='
ab -n $REQUESTS -c $CONCURRENCY -H "X-API-Key: $API_KEY" \
  "$FASTAPI_URL/api/v1/renders?url=$TEST_URL" \
  > fastapi_bench.txt 2>/dev/null

if [ $? -ne 0 ]; then
  echo "⚠️  FastAPI benchmark failed (likely not running)"
  fastapi_mean=0
else
  fastapi_mean=$(grep 'Time per request' fastapi_bench.txt | head -1 | awk '{print $4}')
  fastapi_p95=$(grep '95%' fastapi_bench.txt | awk '{print $2}')
  echo "FastAPI Mean: ${fastapi_mean}ms"
  echo "FastAPI p95:  ${fastapi_p95}ms"
fi

echo ""

# Go benchmark
echo '=== Go Benchmark ==='
ab -n $REQUESTS -c $CONCURRENCY -H "X-API-Key: $API_KEY" \
  "$GO_URL/api/v1/renders?url=$TEST_URL" \
  > go_bench.txt 2>/dev/null

if [ $? -ne 0 ]; then
  echo "⚠️  Go benchmark failed (likely not running)"
  go_mean=0
else
  go_mean=$(grep 'Time per request' go_bench.txt | head -1 | awk '{print $4}')
  go_p95=$(grep '95%' go_bench.txt | awk '{print $2}')
  echo "Go Mean: ${go_mean}ms"
  echo "Go p95:  ${go_p95}ms"
fi

echo ""
echo "=== Comparison ==="

if (( $(echo "$fastapi_mean > 0" | bc -l) )) && (( $(echo "$go_mean > 0" | bc -l) )); then
  improvement=$(echo "scale=2; (($fastapi_mean - $go_mean) / $fastapi_mean) * 100" | bc 2>/dev/null)
  
  echo "Improvement: ${improvement}%"

  if (( $(echo "$improvement > 20" | bc -l) )); then
    echo '✅ Go is significantly faster (>20% improvement)'
  else
    echo '⚠️  Performance improvement not significant or Go is slower'
  fi
else
    echo "⚠️  Cannot compare - one or both benchmarks failed."
fi

# Cleanup
rm -f fastapi_bench.txt go_bench.txt
