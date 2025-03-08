#!/bin/bash

# status_service.sh - Checks the status of a specified Shroombox service
# Usage: ./status_service.sh [service-name]
# If no service name is provided, the script will prompt for selection

# Function to list available services and let user select one
select_service() {
    echo "Available Shroombox Services:"
    echo "----------------------------"
    
    # Get list of all Shroombox services
    ALL_SERVICES=()
    while read -r service _; do
        if [[ $service == shroombox-* ]]; then
            ALL_SERVICES+=("${service%.service}")
        fi
    done < <(systemctl list-units --type=service --all | grep shroombox)
    
    if [ ${#ALL_SERVICES[@]} -eq 0 ]; then
        echo "No Shroombox services found in systemd."
        echo "Showing default Shroombox services instead."
        ALL_SERVICES=(
            "shroombox-main"
            "shroombox-measurements"
            "shroombox-web"
            "shroombox-tapo-monitor"
        )
    fi
    
    # Display menu for service selection
    echo "Select a service to check status:"
    select SERVICE_NAME in "${ALL_SERVICES[@]}" "Cancel"; do
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

# Display service status
echo "Status of $SERVICE_NAME:"
echo "------------------------"
systemctl status "$SERVICE_NAME"

# Display additional information
echo ""
echo "Service enabled at boot: $(systemctl is-enabled "$SERVICE_NAME")"
echo "Active state: $(systemctl is-active "$SERVICE_NAME")"
echo ""
echo "Last 10 log entries:"
journalctl -u "$SERVICE_NAME" -n 10 --no-pager 