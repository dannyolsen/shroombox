# Shroombox Project Cleanup Plan

## Files to Move

### Move to scripts/ directory:
- `update_rules.sh` → `scripts/util_update_rules.sh`
- `update_grafana_config.sh` → `scripts/util_update_grafana_config.sh`
- `test_sensor.py` → `scripts/test_sensor.py`
- `make_settings_editable.sh` → `scripts/util_make_settings_editable.sh`
- `fix_permissions.sh` → `scripts/util_fix_permissions.sh`

### Move to config/ directory:
- `dashboard.json` → `config/grafana/dashboard.json`
- `influxdb_datasource.json` → `config/grafana/influxdb_datasource.json`
- `.env` (keep a copy in root for compatibility, but also store in config)
- `influxdata-archive_compat.key` → `config/influxdata-archive_compat.key`

### Move to docs/ directory:
- `README_FOLDER_STRUCTURE.md` → `docs/folder_structure.md`
- `todo.txt` → `docs/todo.md` (convert to markdown format)

### Move to tests/ directory:
- `test_environment_controller.py` → `tests/unit/test_environment_controller.py`

### Move to config/services/ directory:
- `shroombox-main.service` → `config/services/shroombox-main.service`
- `shroombox-web.service` → `config/services/shroombox-web.service`
- `shroombox-measurements.service` → `config/services/shroombox-measurements.service`
- `shroombox-permissions.service` → `config/services/shroombox-permissions.service`
- `shroombox-permissions.timer` → `config/services/shroombox-permissions.timer`
- `.service` → `config/services/unnamed.service` (rename appropriately if needed)

### Move to backup/ directory:
- `main.py.backup` → `backup/main.py.backup`
- `main_simple.py` → `backup/main_simple.py`
- `diagnostic_log.txt` → `backup/diagnostic_log.txt`

### Files to keep in root:
- `main.py` (main application entry point)
- `README.md` (project documentation)
- `.gitignore`
- `shroombox3.code-workspace` (IDE configuration)

## Directory Merges

Based on the directory analysis:

### api/ directory:
- The `api/` directory is empty except for a routes subdirectory
- **Action**: Keep as is for now, but consider merging with `web/` in the future if it contains API endpoints

### frontend/ directory:
- The `frontend/` directory is empty except for a structure with src/components and src/services
- **Action**: Keep as is for now, but consider merging with `web/` in the future if it contains frontend code

### controllers/ directory:
- The `controllers/` directory contains several controller classes:
  - `environment_controller.py`
  - `fan_controller.py`
  - `humidity_controller.py`
  - `temperature_controller.py`
- These appear to be higher-level controllers that coordinate between devices
- **Action**: Move to `managers/` directory since they coordinate between devices and services

## Implementation Steps

1. Create any missing directories:
   ```bash
   mkdir -p config/grafana config/services docs/ tests/unit
   ```

2. Move files to their new locations using the plan above

3. Move controllers to managers directory:
   ```bash
   cp -r controllers/* managers/
   ```

4. Update any imports or references in the code that might be affected by the file moves

5. Update documentation to reflect the new structure

6. Test the application to ensure everything still works after reorganization

## Benefits

- Cleaner root directory
- Better organization according to project structure guidelines
- Easier navigation and maintenance
- Improved developer experience 