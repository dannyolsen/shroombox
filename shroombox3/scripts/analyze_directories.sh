#!/bin/bash

# Shroombox Directory Analysis Script
# This script analyzes directories that need to be reviewed for potential merging

# Exit on error
set -e

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "Analyzing directories for potential reorganization..."
echo "Project root: $PROJECT_ROOT"

# Function to analyze a directory
analyze_directory() {
    local dir=$1
    local name=$2
    
    if [ ! -d "$dir" ]; then
        echo "$name directory not found."
        return
    fi
    
    echo "=== $name Directory Analysis ==="
    echo "Location: $dir"
    echo "File count: $(find "$dir" -type f | wc -l)"
    echo "Directory structure:"
    find "$dir" -type d | sort | sed -e "s|$dir|$name|" -e 's/^/  /'
    echo ""
    echo "File types:"
    find "$dir" -type f -name "*.*" | grep -o '\.[^\.]*$' | sort | uniq -c | sort -nr
    echo ""
    echo "Top-level files:"
    ls -la "$dir" | grep -v '^d' | grep -v '^total' | awk '{print "  " $9}'
    echo ""
    
    # Check for Python files and analyze imports
    if [ $(find "$dir" -name "*.py" | wc -l) -gt 0 ]; then
        echo "Python imports (top 10):"
        grep -r "^import\|^from" "$dir" --include="*.py" | sed 's/:.*//' | sort | uniq -c | sort -nr | head -10 | awk '{print "  " $0}'
        echo ""
    fi
    
    echo "Recommendation:"
    case "$name" in
        "api")
            echo "  Consider merging with web/ directory if it contains API endpoints"
            ;;
        "frontend")
            echo "  Consider merging with web/ directory if it contains frontend code"
            ;;
        "controllers")
            echo "  Consider merging with devices/ or managers/ based on functionality"
            ;;
        *)
            echo "  No specific recommendation"
            ;;
    esac
    echo "==============================="
    echo ""
}

# Analyze directories that need to be reviewed
analyze_directory "api" "api"
analyze_directory "frontend" "frontend"
analyze_directory "controllers" "controllers"

echo "Analysis complete!"
echo ""
echo "Next steps:"
echo "1. Review the analysis and decide which directories to merge"
echo "2. Update the cleanup_project.sh script to include these merges"
echo "3. Run the cleanup_project.sh script to reorganize the project" 