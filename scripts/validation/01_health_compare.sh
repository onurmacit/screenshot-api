#!/bin/bash

# Configuration
FASTAPI_URL="http://localhost:8000"
GO_URL="http://localhost:8090"
ENDPOINT="/api/v1/health"

echo "=== SNIPPET-001: Health Check Comparison ==="
echo "FastAPI URL: $FASTAPI_URL"
echo "Go URL: $GO_URL"
echo ""

# Check dependencies
for cmd in curl jq diff; do
    if ! command -v $cmd &> /dev/null; then
        echo "Error: Required command '$cmd' not found."
        exit 1
    fi
done

echo 'Testing FastAPI health...'
fastapi_health=$(curl -s $FASTAPI_URL$ENDPOINT | jq -S . 2>/dev/null)
if [ -z "$fastapi_health" ]; then
    echo "⚠️  FastAPI not reachable or invalid response"
    fastapi_health="{}"
fi

echo 'Testing Go health...'
go_health=$(curl -s $GO_URL$ENDPOINT | jq -S . 2>/dev/null)
if [ -z "$go_health" ]; then
    echo "⚠️  Go API not reachable or invalid response"
    go_health="{}"
fi

echo ""
echo '=== FastAPI Response ==='
echo "$fastapi_health"

echo ""
echo '=== Go Response ==='
echo "$go_health"

echo ""
echo '=== Diff ==='
diff <(echo "$fastapi_health") <(echo "$go_health")
DIFF_EXIT=$?

if [ $DIFF_EXIT -eq 0 ]; then
    echo "✅ Responses match perfectly!"
else
    echo "⚠️  Responses differ (see diff above)"
fi

# Check key fields specifically
echo ""
echo "=== Key Field Check ==="
fastapi_status=$(echo "$fastapi_health" | jq -r .status 2>/dev/null)
go_status=$(echo "$go_health" | jq -r .status 2>/dev/null)

if [ "$fastapi_status" = "$go_status" ] && [ -n "$go_status" ] && [ "$go_status" != "null" ]; then
  echo "✅ Status match: $go_status"
else
  echo "❌ Status mismatch: FastAPI='$fastapi_status', Go='$go_status'"
fi
