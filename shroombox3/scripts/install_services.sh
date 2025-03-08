#!/bin/bash

# This script installs the systemd services for Shroombox

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

# Get the absolute path to the project directory
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "Installing services from $PROJECT_DIR"

# Create service files
cat > /etc/systemd/system/shroombox-main.service << EOF
[Unit]
Description=Shroombox Control System
After=network.target

[Service]
Type=simple
User=$(whoami)
Group=$(whoami)
WorkingDirectory=$PROJECT_DIR
Environment=VIRTUAL_ENV=$PROJECT_DIR/venv
Environment=PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/venv/bin/python main.py
# Restart=always
StandardOutput=append:/var/log/shroombox/main.log
StandardError=append:/var/log/shroombox/main.log

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/shroombox-web.service << EOF
[Unit]
Description=Shroombox Web Interface
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$(whoami)
Group=$(whoami)
WorkingDirectory=$PROJECT_DIR

# Environment setup
Environment=PYTHONUNBUFFERED=1
Environment=PATH=$PROJECT_DIR/venv/bin
Environment=PYTHONPATH=$PROJECT_DIR
Environment=QUART_APP=web.web_server:app
Environment=QUART_ENV=production

# Create log directory if it doesn't exist
ExecStartPre=/bin/mkdir -p $PROJECT_DIR/logs

# Start the application
ExecStart=$PROJECT_DIR/venv/bin/hypercorn \\
    --bind 0.0.0.0:5000 \\
    --workers 1 \\
    --log-level debug \\
    web.web_server:app

# Restart configuration
Restart=no

# Logging
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Add the new Tapo device monitoring service
cat > /etc/systemd/system/shroombox-tapo-monitor.service << EOF
[Unit]
Description=Shroombox Tapo Device Monitor
After=network.target
Wants=network.target

[Service]
Type=simple
User=$(whoami)
Group=$(whoami)
WorkingDirectory=$PROJECT_DIR
Environment=VIRTUAL_ENV=$PROJECT_DIR/venv
Environment=PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/scripts/util_monitor_tapo_devices.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=shroombox-tapo-monitor
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# Create log directory
mkdir -p /var/log/shroombox

# Set permissions
chown -R $(whoami):$(whoami) /var/log/shroombox

# Make the monitoring script executable
chmod +x $PROJECT_DIR/scripts/util_monitor_tapo_devices.py

# Reload systemd
systemctl daemon-reload

echo "Services installed successfully!"
echo "You can now start them with:"
echo "  sudo systemctl start shroombox-main shroombox-web shroombox-tapo-monitor"
echo
echo "To enable them to start at boot:"
echo "  sudo systemctl enable shroombox-main shroombox-web shroombox-tapo-monitor" 