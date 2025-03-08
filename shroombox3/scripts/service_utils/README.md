# Shroombox Service Utilities

This directory contains utility scripts for managing Shroombox services.

## Available Scripts

- `list_services.sh`: Lists all available Shroombox services
- `start_service.sh`: Starts a specified Shroombox service
- `stop_service.sh`: Stops a specified Shroombox service
- `restart_service.sh`: Restarts a specified Shroombox service
- `status_service.sh`: Checks the status of a specified Shroombox service
- `install_all_services.sh`: Installs all Shroombox services
- `uninstall_all_services.sh`: Uninstalls all Shroombox services
- `stop_all_services.sh`: Stops all running Shroombox services

## Usage

### List Services

```bash
./list_services.sh
```

### Start a Service

```bash
./start_service.sh <service-name>
```

Example:
```bash
./start_service.sh shroombox-web
```

### Stop a Service

```bash
./stop_service.sh <service-name>
```

Example:
```bash
./stop_service.sh shroombox-web
```

### Restart a Service

```bash
./restart_service.sh <service-name>
```

Example:
```bash
./restart_service.sh shroombox-web
```

### Check Service Status

```bash
./status_service.sh <service-name>
```

Example:
```bash
./status_service.sh shroombox-web
```

### Install All Services

```bash
./install_all_services.sh
```

### Uninstall All Services

```bash
./uninstall_all_services.sh
```

### Stop All Services

```bash
sudo ./stop_all_services.sh
```

This will stop all running Shroombox services:
- shroombox-main
- shroombox-measurements
- shroombox-web
- shroombox-tapo-monitor

## Available Services

- `shroombox-main.service`: Main Shroombox application service
- `shroombox-measurements.service`: Service for collecting sensor measurements
- `shroombox-web.service`: Web interface service
- `shroombox-tapo-monitor.service`: Service for monitoring Tapo smart plugs

## Notes

- All scripts require sudo privileges to manage systemd services
- Service names can be provided with or without the `.service` extension
- If a service is not installed, the start and restart scripts will attempt to install it from the project files 