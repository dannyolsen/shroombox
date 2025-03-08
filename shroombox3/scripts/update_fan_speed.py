#!/usr/bin/env python3
"""
Script to update the measurements.json file with the fan speed.
"""

import os
import sys
import json
import time
import logging
from datetime import datetime

# Add parent directory to Python path so we can import from root
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Import from project
from managers.device_manager import DeviceManager
from managers.settings_manager import SettingsManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('fan_speed_updater')

# Path to the measurements file
MEASUREMENTS_FILE = os.path.join(parent_dir, 'data', 'measurements.json')
# Path to the settings file
SETTINGS_FILE = os.path.join(parent_dir, 'config', 'settings.json')

def update_fan_speed():
    """Update the measurements.json file with the fan speed."""
    try:
        # Get the DeviceManager instance (it's a singleton)
        device_manager = DeviceManager()
        
        # Get fan speed from device manager
        fan_speed = device_manager.get_fan_speed()
        fan_speed_rounded = round(float(fan_speed), 1)
        
        logger.info(f"Got fan speed from device manager: {fan_speed_rounded}%")
        
        # Read the current measurements file
        if os.path.exists(MEASUREMENTS_FILE):
            with open(MEASUREMENTS_FILE, 'r') as f:
                data = json.load(f)
        else:
            logger.warning(f"Measurements file not found: {MEASUREMENTS_FILE}")
            data = {
                'co2': 0,
                'temperature': 0,
                'humidity': 0,
                'source': 'unknown',
                'timestamp': datetime.now().isoformat(),
                'unix_timestamp': time.time()
            }
        
        # Add fan speed to the data
        data['fan_speed'] = fan_speed_rounded
        
        # Write to file (using atomic write pattern)
        temp_file = f"{MEASUREMENTS_FILE}.tmp"
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(temp_file, MEASUREMENTS_FILE)
        
        logger.info(f"Updated measurements.json with fan speed: {fan_speed_rounded}%")
        
        # Also update the fan speed in settings.json for backward compatibility
        try:
            # Initialize settings manager
            settings_manager = SettingsManager(SETTINGS_FILE)
            
            # Update settings
            updates = {
                'fan': {
                    'speed': fan_speed_rounded
                }
            }
            
            # Use the update_settings method to properly merge changes
            success = settings_manager.update_settings_sync(updates)
            if success:
                logger.info(f"Updated fan speed in settings.json to {fan_speed_rounded}%")
            else:
                logger.error("Failed to save settings with updated fan speed")
        except Exception as e:
            logger.error(f"Error updating fan speed in settings.json: {e}")
        
    except Exception as e:
        logger.error(f"Error updating fan speed: {e}")

if __name__ == "__main__":
    update_fan_speed() 