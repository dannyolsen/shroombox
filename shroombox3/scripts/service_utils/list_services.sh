#!/bin/bash

# list_services.sh - Lists all available Shroombox services
# Usage: ./list_services.sh

echo "Available Shroombox Services:"
echo "----------------------------"

# Check systemd services
echo "System Services (systemd):"
systemctl list-units --type=service --all | grep shroombox | awk '{print "  - " $1 " (" $4 ")"}'

echo ""
echo "Service Files in Project:"
echo "  - shroombox-main.service"
echo "  - shroombox-measurements.service"
echo "  - shroombox-web.service"
echo "  - shroombox-tapo-monitor.service"

echo ""
echo "To start a service: ./start_service.sh <service-name>"
echo "To stop a service:  ./stop_service.sh <service-name>"
echo "Example: ./start_service.sh shroombox-web" 