#!/bin/bash

# stop_all_services.sh - Stops all Shroombox services
# Usage: ./stop_all_services.sh

# If not running as root, relaunch the script with sudo
if [ "$EUID" -ne 0 ]; then
    exec sudo "$0" "$@"
fi

echo "Stopping all Shroombox services..."
echo "-------------------------------------"

# First stop and disable the permissions timer if it exists
if systemctl list-units --all | grep -q "shroombox-permissions.timer"; then
    echo ""
    echo "Found shroombox-permissions.timer. Stopping and disabling it..."
    systemctl stop shroombox-permissions.timer
    systemctl disable shroombox-permissions.timer
    echo "Timer stopped and disabled."
fi

# Define all services to stop
SERVICES=(
    "shroombox-main.service"
    "shroombox-measurements.service"
    "shroombox-web.service"
    "shroombox-tapo-monitor.service"
)

# Stop each service
for SERVICE in "${SERVICES[@]}"; do
    echo ""
    echo "Stopping $SERVICE..."
    
    # Check if service exists and is active
    if systemctl list-units --all | grep -q "$SERVICE"; then
        if systemctl is-active --quiet "$SERVICE"; then
            echo "Service $SERVICE is running. Stopping it..."
            systemctl stop "$SERVICE"
            if [ $? -eq 0 ]; then
                echo "Successfully stopped $SERVICE"
            else
                echo "Failed to stop $SERVICE"
            fi
        else
            echo "Service $SERVICE is not running"
        fi
    else
        echo "Service $SERVICE not found"
    fi
done

echo ""
echo "All services have been processed."
echo "You can verify the status of services with: systemctl status 'shroombox-*'" 