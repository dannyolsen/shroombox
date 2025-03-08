#!/bin/bash

# install_all_services.sh - Installs all Shroombox services
# Usage: ./install_all_services.sh

echo "Installing all Shroombox services..."
echo "-----------------------------------"

# Define the services to install
SERVICES=(
    "shroombox-main.service"
    "shroombox-measurements.service"
    "shroombox-web.service"
    "shroombox-tapo-monitor.service"
)

# Install each service
for SERVICE in "${SERVICES[@]}"; do
    echo ""
    echo "Installing $SERVICE..."
    
    # Check if service file exists in project root
    if [ -f "../../$SERVICE" ]; then
        echo "Found $SERVICE in project root."
        sudo cp "../../$SERVICE" /etc/systemd/system/
    # Check if service file exists in scripts directory
    elif [ -f "../../scripts/$SERVICE" ]; then
        echo "Found $SERVICE in scripts directory."
        sudo cp "../../scripts/$SERVICE" /etc/systemd/system/
    else
        echo "Warning: Service file $SERVICE not found. Skipping."
        continue
    fi
    
    echo "Service file $SERVICE copied to /etc/systemd/system/"
done

# Reload systemd to recognize new services
echo ""
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo ""
echo "All services installed successfully."
echo ""
echo "To start services, use:"
echo "  ./start_service.sh <service-name>"
echo ""
echo "Available services:"
./list_services.sh 