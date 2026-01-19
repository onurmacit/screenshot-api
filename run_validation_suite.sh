#!/bin/bash

# Required argument: API Key
if [ -z "$1" ]; then
    echo "Usage: ./run_validation_suite.sh <api_key>"
    exit 1
fi

API_KEY=$1
RESULTS_FILE="validation_results.txt"

echo "=== Running Full Validation Suite ===" | tee $RESULTS_FILE
echo "Date: $(date)" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

run_test() {
    script=$1
    echo "---------------------------------------------------" | tee -a $RESULTS_FILE
    echo "Running: $script" | tee -a $RESULTS_FILE
    
    # Run script and capture both stdout and stderr
    # Using 'script' with api key argument
    if ./scripts/validation/$script "$API_KEY" >> $RESULTS_FILE 2>&1; then
        echo "✅ Execution completed (check logs for details)"
    else
        echo "❌ Execution failed!"
    fi
}

# 1. Health Checks
run_test "01_health_compare.sh"

# 2. Error Formats
run_test "02_error_format.sh"

# 3. Pagination
run_test "03_pagination_check.sh"

# 4. Latency Comparison
run_test "04_latency_compare.sh"

# 5. User Journey
run_test "05_user_journey.sh"

# 6. SSRF Security
run_test "06_ssrf_test.sh"

# 7. Cache Logic
run_test "07_cache_check.sh"

# 8. Memory Leak (Short run)
# run_test "09_memory_leak.sh" # Uncomment if needed (takes 5 mins)

# 9. Binary Response
run_test "10_binary_check.sh"

echo "" | tee -a $RESULTS_FILE
echo "=== Validation Suite Complete ===" | tee -a $RESULTS_FILE
echo "Results saved to: $RESULTS_FILE"
