#!/bin/bash

BASE_URL=${1:-"http://localhost:8080"}
CONCURRENT=${2:-10}
REQUESTS=${3:-100}

echo "====================================="
echo "Load Testing"
echo "Target: $BASE_URL"
echo "Concurrent: $CONCURRENT"
echo "Total Requests: $REQUESTS"
echo "====================================="
echo ""

# Check if ab is installed
if ! command -v ab &> /dev/null; then
  echo "Apache Bench (ab) is not installed."
  echo "Install with: apt-get install apache2-utils"
  exit 1
fi

echo "Testing health endpoint..."
ab -n $REQUESTS -c $CONCURRENT "$BASE_URL/api/v1/health"

echo ""
echo "====================================="
echo "Load test complete"
echo "====================================="
