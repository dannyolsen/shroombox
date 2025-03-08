#!/bin/bash

# stop_service.sh - Stops a specified Shroombox service
# Usage: ./stop_service.sh [service-name]
# If no service name is provided, the script will prompt for selection

# Function to list available services and let user select one
select_service() {
    echo "Available Shroombox Services:"
    echo "----------------------------"
    
    # Get list of running services
    echo "Running services:"
    RUNNING_SERVICES=()
    while read -r service _; do
        if [[ $service == shroombox-* ]]; then
            RUNNING_SERVICES+=("${service%.service}")
        fi
    done < <(systemctl list-units --type=service --state=running | grep shroombox)
    
    if [ ${#RUNNING_SERVICES[@]} -eq 0 ]; then
        echo "No Shroombox services are currently running."
        echo "Showing all Shroombox services instead."
        RUNNING_SERVICES=(
            "shroombox-main"
            "shroombox-measurements"
            "shroombox-web"
            "shroombox-tapo-monitor"
        )
    fi
    
    # Display menu for service selection
    echo "Select a service to stop:"
    select SERVICE_NAME in "${RUNNING_SERVICES[@]}" "Cancel"; do
        if [ "$SERVICE_NAME" = "Cancel" ]; then
            echo "Operation cancelled."
            exit 0
        elif [ -n "$SERVICE_NAME" ]; then
            echo "Selected service: $SERVICE_NAME"
            return 0
        else
            echo "Invalid selection. Please try again."
        fi
    done
}

# Check if service name is provided as argument
if [ $# -eq 0 ]; then
    echo "No service name provided as argument."
    select_service
else
    SERVICE_NAME=$1
fi

# Check if service name includes .service extension
if [[ $SERVICE_NAME != *.service ]]; then
    SERVICE_NAME="${SERVICE_NAME}.service"
fi

# Check if the service exists
if ! systemctl list-units --all | grep -q "$SERVICE_NAME"; then
    echo "Error: Service $SERVICE_NAME not found in systemd."
    exit 1
fi

# Stop the service
echo "Stopping $SERVICE_NAME..."
sudo systemctl stop "$SERVICE_NAME"

# Check if service stopped successfully
if ! systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "Service $SERVICE_NAME stopped successfully."
else
    echo "Failed to stop $SERVICE_NAME. Check status with: systemctl status $SERVICE_NAME"
    exit 1
fi

# Ask if user wants to disable the service from starting on boot
read -p "Do you want to disable $SERVICE_NAME from starting on boot? (y/n): " DISABLE_CHOICE

if [[ $DISABLE_CHOICE == "y" || $DISABLE_CHOICE == "Y" ]]; then
    echo "Disabling $SERVICE_NAME from starting on boot..."
    sudo systemctl disable "$SERVICE_NAME"
    echo "Service $SERVICE_NAME is now disabled and will not start on boot."
else
    echo "Service $SERVICE_NAME is stopped but will still start on boot."
fi 