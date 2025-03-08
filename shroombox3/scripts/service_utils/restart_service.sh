#!/bin/bash

# restart_service.sh - Restarts a specified Shroombox service
# Usage: ./restart_service.sh [service-name]
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
    echo "Select a service to restart:"
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
    echo "Service $SERVICE_NAME not found in systemd."
    echo "Checking if service file exists in project..."
    
    # Check if service file exists in project root
    if [ -f "../$SERVICE_NAME" ]; then
        echo "Found service file in project root. Installing service..."
        sudo cp "../$SERVICE_NAME" /etc/systemd/system/
        sudo systemctl daemon-reload
    # Check if service file exists in scripts directory
    elif [ -f "../scripts/$SERVICE_NAME" ]; then
        echo "Found service file in scripts directory. Installing service..."
        sudo cp "../scripts/$SERVICE_NAME" /etc/systemd/system/
        sudo systemctl daemon-reload
    else
        echo "Error: Service file not found."
        exit 1
    fi
fi

# Restart the service
echo "Restarting $SERVICE_NAME..."
sudo systemctl restart "$SERVICE_NAME"

# Check if service restarted successfully
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "Service $SERVICE_NAME restarted successfully."
else
    echo "Failed to restart $SERVICE_NAME. Check status with: systemctl status $SERVICE_NAME"
    exit 1
fi

# Show current status
echo ""
echo "Current status of $SERVICE_NAME:"
systemctl status "$SERVICE_NAME" --no-pager | head -n 10 