#!/bin/bash

# start_service.sh - Starts a specified Shroombox service
# Usage: ./start_service.sh [service-name]
# If no service name is provided, the script will prompt for selection

# Function to list available services and let user select one
select_service() {
    echo "Available Shroombox Services:"
    echo "----------------------------"
    
    # Get list of services
    SERVICES=(
        "shroombox-main"
        "shroombox-measurements"
        "shroombox-web"
        "shroombox-tapo-monitor"
    )
    
    # Display menu for service selection
    echo "Select a service to start:"
    select SERVICE_NAME in "${SERVICES[@]}" "Cancel"; do
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

# Start the service
echo "Starting $SERVICE_NAME..."
sudo systemctl start "$SERVICE_NAME"

# Check if service started successfully
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "Service $SERVICE_NAME started successfully."
else
    echo "Failed to start $SERVICE_NAME. Check status with: systemctl status $SERVICE_NAME"
    exit 1
fi

# Enable the service to start on boot
echo "Enabling $SERVICE_NAME to start on boot..."
sudo systemctl enable "$SERVICE_NAME"

echo "Service $SERVICE_NAME is now running and enabled to start on boot." 