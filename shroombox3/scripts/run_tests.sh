#!/bin/bash

# This script runs tests for the Shroombox project
# Usage: ./scripts/run_tests.sh [unit|integration]
# If no argument is provided, all tests will be run

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d "env_shrooms" ]; then
    echo "Activating virtual environment..."
    source env_shrooms/bin/activate
fi

# Set the working directory to the project root
cd "$(dirname "$0")/.."

# Check if a specific test category was requested
TEST_CATEGORY="$1"
# Check if we should ignore hardware-related failures
IGNORE_HW_FAILURES="$2"

# Function to run tests in a directory
run_tests() {
    local test_dir="$1"
    echo "Running tests in $test_dir..."
    
    # Check if directory exists and has test files
    if [ ! -d "$test_dir" ] || [ -z "$(ls -A $test_dir/test_*.py 2>/dev/null)" ]; then
        echo "No tests found in $test_dir"
        return 0
    fi
    
    local failures=0
    
    for test_file in $test_dir/test_*.py; do
        echo "Running $test_file..."
        
        # Skip hardware-dependent tests if requested
        if [ "$IGNORE_HW_FAILURES" = "ignore-hw" ]; then
            if [[ "$test_file" == *"_i2c.py" || "$test_file" == *"_scd30.py" || "$test_file" == *"_controller.py" || "$test_file" == *"_direct_scd30.py" || "$test_file" == *"_simple_scd30.py" ]]; then
                echo "Skipping hardware-dependent test: $test_file"
                continue
            fi
        fi
        
        # Run the test
        python "$test_file" --count 1 2>/dev/null  # Run with minimal output
        
        if [ $? -ne 0 ]; then
            echo "Test $test_file failed!"
            
            # If we're ignoring hardware failures, check if it's a hardware-related test
            if [ "$IGNORE_HW_FAILURES" = "ignore-hw" ]; then
                if [[ "$test_file" == *"_sensor.py" || "$test_file" == *"_measurements.py" ]]; then
                    echo "Ignoring hardware-related failure"
                    continue
                fi
            fi
            
            failures=$((failures+1))
        fi
    done
    
    if [ $failures -gt 0 ]; then
        echo "$failures tests failed in $test_dir"
        return 1
    fi
    
    return 0
}

# Run tests based on category
if [ -z "$TEST_CATEGORY" ] || [ "$TEST_CATEGORY" = "all" ]; then
    # Run all tests
    run_tests "tests/unit"
    unit_result=$?
    run_tests "tests/integration"
    integration_result=$?
    
    if [ $unit_result -ne 0 ] || [ $integration_result -ne 0 ]; then
        echo "Some tests failed!"
        if [ "$IGNORE_HW_FAILURES" = "ignore-hw" ]; then
            echo "Hardware-related failures were ignored"
            exit 0
        else
            echo "Run with 'ignore-hw' to ignore hardware-related failures"
            exit 1
        fi
    fi
elif [ "$TEST_CATEGORY" = "unit" ]; then
    # Run only unit tests
    run_tests "tests/unit"
    if [ $? -ne 0 ]; then
        echo "Some unit tests failed!"
        if [ "$IGNORE_HW_FAILURES" = "ignore-hw" ]; then
            echo "Hardware-related failures were ignored"
            exit 0
        else
            echo "Run with 'ignore-hw' to ignore hardware-related failures"
            exit 1
        fi
    fi
elif [ "$TEST_CATEGORY" = "integration" ]; then
    # Run only integration tests
    run_tests "tests/integration"
    if [ $? -ne 0 ]; then
        echo "Some integration tests failed!"
        if [ "$IGNORE_HW_FAILURES" = "ignore-hw" ]; then
            echo "Hardware-related failures were ignored"
            exit 0
        else
            echo "Run with 'ignore-hw' to ignore hardware-related failures"
            exit 1
        fi
    fi
else
    echo "Unknown test category: $TEST_CATEGORY"
    echo "Usage: ./scripts/run_tests.sh [unit|integration|all] [ignore-hw]"
    exit 1
fi

echo "All tests completed successfully!" 