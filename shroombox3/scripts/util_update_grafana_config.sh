#!/bin/bash

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

# Backup the original file
cp /etc/grafana/grafana.ini /etc/grafana/grafana.ini.bak

# Update the allow_embedding setting
if grep -q "^;allow_embedding" /etc/grafana/grafana.ini; then
  # Uncomment and set to true if it exists but is commented
  sed -i 's/^;allow_embedding.*/allow_embedding = true/' /etc/grafana/grafana.ini
elif grep -q "^allow_embedding" /etc/grafana/grafana.ini; then
  # Update if it exists and is not commented
  sed -i 's/^allow_embedding.*/allow_embedding = true/' /etc/grafana/grafana.ini
else
  # Add it to the [security] section if it doesn't exist
  if grep -q "^\[security\]" /etc/grafana/grafana.ini; then
    # Add after [security] section
    sed -i '/^\[security\]/a allow_embedding = true' /etc/grafana/grafana.ini
  else
    # Create [security] section if it doesn't exist
    echo -e "\n[security]\nallow_embedding = true" >> /etc/grafana/grafana.ini
  fi
fi

# Update the cookie_samesite setting
if grep -q "^;cookie_samesite" /etc/grafana/grafana.ini; then
  # Uncomment and set to none if it exists but is commented
  sed -i 's/^;cookie_samesite.*/cookie_samesite = none/' /etc/grafana/grafana.ini
elif grep -q "^cookie_samesite" /etc/grafana/grafana.ini; then
  # Update if it exists and is not commented
  sed -i 's/^cookie_samesite.*/cookie_samesite = none/' /etc/grafana/grafana.ini
else
  # Add it to the [security] section if it doesn't exist
  if grep -q "^\[security\]" /etc/grafana/grafana.ini; then
    # Add after [security] section
    sed -i '/^\[security\]/a cookie_samesite = none' /etc/grafana/grafana.ini
  else
    # Create [security] section if it doesn't exist
    echo -e "\n[security]\ncookie_samesite = none" >> /etc/grafana/grafana.ini
  fi
fi

# Restart Grafana
systemctl restart grafana-server

echo "Grafana configuration updated and service restarted." 