#!/bin/bash

# uninstall_all_services.sh - Uninstalls all Shroombox services
# Usage: ./uninstall_all_services.sh

echo "Uninstalling all Shroombox services..."
echo "-------------------------------------"

# Define the services to uninstall
SERVICES=(
    "shroombox-main.service"
    "shroombox-measurements.service"
    "shroombox-web.service"
    "shroombox-tapo-monitor.service"
)

# Uninstall each service
for SERVICE in "${SERVICES[@]}"; do
    echo ""
    echo "Uninstalling $SERVICE..."
    
    # Check if service exists
    if systemctl list-units --all | grep -q "$SERVICE"; then
        # Stop the service if it's running
        if systemctl is-active --quiet "$SERVICE"; then
            echo "Stopping $SERVICE..."
            sudo systemctl stop "$SERVICE"
        fi
        
        # Disable the service
        echo "Disabling $SERVICE..."
        sudo systemctl disable "$SERVICE"
        
        # Remove the service file
        echo "Removing $SERVICE file..."
        sudo rm -f "/etc/systemd/system/$SERVICE"
    else
        echo "Service $SERVICE not found. Skipping."
    fi
done

# Reload systemd to recognize changes
echo ""
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo ""
echo "All services uninstalled successfully." 