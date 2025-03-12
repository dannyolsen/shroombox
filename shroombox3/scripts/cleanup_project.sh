#!/bin/bash

# Shroombox Project Cleanup Script
# This script reorganizes files in the project root according to the established project structure guidelines.
# It moves files to their appropriate directories and creates necessary directories if they don't exist.

# Exit on error
set -e

# Set the project root directory (assuming the script is run from the project root)
PROJECT_ROOT=$(pwd)
echo "Project root: $PROJECT_ROOT"

# Create necessary directories if they don't exist
echo "Creating necessary directories..."
mkdir -p config/grafana config/services docs/ tests/unit backup/

# Move script files to scripts/ directory
echo "Moving script files..."
[ -f update_rules.sh ] && mv update_rules.sh scripts/util_update_rules.sh
[ -f update_grafana_config.sh ] && mv update_grafana_config.sh scripts/util_update_grafana_config.sh
[ -f make_settings_editable.sh ] && mv make_settings_editable.sh scripts/util_make_settings_editable.sh
[ -f fix_permissions.sh ] && mv fix_permissions.sh scripts/util_fix_permissions.sh
[ -f test_sensor.py ] && mv test_sensor.py scripts/test_sensor.py

# Make scripts executable
chmod +x scripts/*.sh scripts/*.py 2>/dev/null || true

# Move configuration files to config/ directory
echo "Moving configuration files..."
[ -f dashboard.json ] && mv dashboard.json config/grafana/dashboard.json
[ -f influxdb_datasource.json ] && mv influxdb_datasource.json config/grafana/influxdb_datasource.json
[ -f influxdata-archive_compat.key ] && mv influxdata-archive_compat.key config/influxdata-archive_compat.key

# Copy .env to config/ but keep a copy in root for compatibility
[ -f .env ] && cp .env config/.env

# Move documentation files to docs/ directory
echo "Moving documentation files..."
[ -f README_FOLDER_STRUCTURE.md ] && mv README_FOLDER_STRUCTURE.md docs/folder_structure.md
[ -f cleanup_plan.md ] && mv cleanup_plan.md docs/cleanup_plan.md

# Convert todo.txt to markdown if it exists
if [ -f todo.txt ]; then
  echo "# Todo List" > docs/todo.md
  cat todo.txt >> docs/todo.md
  mv todo.txt backup/todo.txt.bak
  echo "Converted todo.txt to docs/todo.md"
fi

# Move test files to tests/ directory
echo "Moving test files..."
[ -f test_environment_controller.py ] && mv test_environment_controller.py tests/unit/test_environment_controller.py

# Move service files to config/services/ directory
echo "Moving service files..."
[ -f shroombox-main.service ] && mv shroombox-main.service config/services/shroombox-main.service
[ -f shroombox-web.service ] && mv shroombox-web.service config/services/shroombox-web.service
[ -f shroombox-measurements.service ] && mv shroombox-measurements.service config/services/shroombox-measurements.service
[ -f shroombox-permissions.service ] && mv shroombox-permissions.service config/services/shroombox-permissions.service
[ -f shroombox-permissions.timer ] && mv shroombox-permissions.timer config/services/shroombox-permissions.timer
[ -f .service ] && mv .service config/services/unnamed.service

# Move backup files to backup/ directory
echo "Moving backup files..."
[ -f main.py.backup ] && mv main.py.backup backup/main.py.backup
[ -f main_simple.py ] && mv main_simple.py backup/main_simple.py
[ -f diagnostic_log.txt ] && mv diagnostic_log.txt backup/diagnostic_log.txt

# Handle directory merges
echo "Handling directory merges..."

# Move controllers to managers directory
if [ -d controllers ]; then
  echo "Moving controllers to managers directory..."
  mkdir -p managers
  cp -r controllers/* managers/
  # Create a README in controllers explaining the move
  mkdir -p controllers
  echo "# Controllers Directory" > controllers/README.md
  echo "The controller files have been moved to the managers/ directory as part of the project reorganization." >> controllers/README.md
  echo "Please update your imports to use the new location." >> controllers/README.md
fi

# Handle deprecated directory
if [ -d deprecated ]; then
  echo "Moving deprecated directory contents to backup..."
  mkdir -p backup/deprecated
  cp -r deprecated/* backup/deprecated/
  echo "# Deprecated Directory" > deprecated/README.md
  echo "The contents of this directory have been moved to backup/deprecated/ as part of the project reorganization." >> deprecated/README.md
fi

# Handle the '~' directory (likely a mistake)
if [ -d "~" ]; then
  echo "Moving '~' directory contents to backup..."
  mkdir -p backup/tilde_dir
  cp -r "~"/* backup/tilde_dir/ 2>/dev/null || true
  rm -rf "~"
  echo "Removed the '~' directory (likely created by mistake)"
fi

# Update .gitignore to include Python cache files if not already
if [ -f .gitignore ]; then
  if ! grep -q "__pycache__" .gitignore; then
    echo "Updating .gitignore to include Python cache files..."
    echo "" >> .gitignore
    echo "# Python cache files" >> .gitignore
    echo "__pycache__/" >> .gitignore
    echo "*.py[cod]" >> .gitignore
    echo "*$py.class" >> .gitignore
  fi
fi

echo "Cleanup complete!"
echo ""
echo "Next steps:"
echo "1. Review the changes to ensure everything is in the right place"
echo "2. Update any imports in your code that might be affected by the file moves"
echo "3. If you need to use the service files from their original location, consider creating symbolic links:"
echo "   sudo ln -s $PROJECT_ROOT/config/services/shroombox-main.service /etc/systemd/system/shroombox-main.service"
echo "4. Test the application to ensure everything still works after reorganization"
echo ""
echo "Note: The api/ and frontend/ directories have been kept as is for now."
echo "Consider merging them with web/ in the future if appropriate." 