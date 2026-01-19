#!/bin/bash

# Configuration
CONTAINER_NAME='screenshot-api-go'
DURATION=300       # 5 minutes for quick test (or 86400 for full day)
INTERVAL=10        # Check every 10 seconds

echo "=== SNIPPET-009: Memory Leak Detection ==="
echo "Monitoring container: $CONTAINER_NAME"
echo "Duration: ${DURATION}s | Interval: ${INTERVAL}s"
echo ""

# Check if container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ Container '$CONTAINER_NAME' is not running!"
    exit 1
fi

echo 'Timestamp,Memory(MB),Goroutines' > memory_log.csv

echo "Starting monitoring..."

start_ts=$(date +%s)
end_ts=$((start_ts + DURATION))

while [ $(date +%s) -lt $end_ts ]; do
  timestamp=$(date '+%Y-%m-%d %H:%M:%S')
  
  # Get memory usage
  # Note: docker stats format {{.MemUsage}} returns like "20MiB / 1GiB", we extract the first part
  mem_info=$(docker stats $CONTAINER_NAME --no-stream --format "{{.MemUsage}}")
  mem_val=$(echo "$mem_info" | awk '{print $1}')
  
  # Convert to MB numeric (strip units)
  # Simple handling for MiB/GiB
  if [[ "$mem_val" == *"GiB"* ]]; then
      mem_num=$(echo "$mem_val" | sed 's/GiB//' | awk '{print $1 * 1024}')
  else
      mem_num=$(echo "$mem_val" | sed 's/MiB//' | sed 's/kB//') # Simplify
  fi
  
  # Get goroutine count via /metrics endpoint (requires prometheus middleware enabled)
  # Alternative: /debug/pprof/goroutine?debug=1 if pprof is enabled
  # Using metrics endpoint as it's more standard in this setup
  goroutines=$(curl -s http://localhost:8090/metrics | grep "go_goroutines" | awk '{print $2}' | tail -1)
  
  if [ -z "$goroutines" ]; then
      goroutines="0"
  fi
  
  echo "$timestamp,$mem_num,$goroutines" >> memory_log.csv
  echo "[$timestamp] Memory: ${mem_num} MB (raw: $mem_val), Goroutines: $goroutines"
  
  sleep $INTERVAL
done

echo ""
echo '=== Analysis ==='

# Analyze for memory leak (simple growth check)
initial_mem=$(head -2 memory_log.csv | tail -1 | cut -d, -f2)
final_mem=$(tail -1 memory_log.csv | cut -d, -f2)

mem_growth=$(echo "$final_mem - $initial_mem" | bc 2>/dev/null)

if [ -z "$mem_growth" ]; then mem_growth=0; fi

echo "Initial memory: ${initial_mem} MB"
echo "Final memory:   ${final_mem} MB"
echo "Growth:         ${mem_growth} MB"

THRESHOLD=50 # 50MB growth over test duration would be bad for short test

if (( $(echo "$mem_growth < $THRESHOLD" | bc -l) )); then
  echo '✅ No significant memory leak detected'
else
  echo '⚠️  Potential memory leak! Growth: '${mem_growth}' MB'
fi
