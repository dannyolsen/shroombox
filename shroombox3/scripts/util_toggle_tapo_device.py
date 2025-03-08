#!/usr/bin/env python3
"""
Utility script to toggle the state of a Tapo device.
This script is used for testing the Tapo device monitoring service.
"""

import os
import sys
import asyncio
import argparse
import logging
import json

# Add parent directory to Python path so we can import from root
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # Go up one level
sys.path.insert(0, parent_dir)

# Import the TapoController
from devices.smart_plug import TapoController

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('tapo_toggle')

# Default settings path
SETTINGS_PATH = os.path.join(parent_dir, 'config', 'settings.json')

async def toggle_device_by_ip(ip_address):
    """Toggle the state of a Tapo device by IP address."""
    logger.info(f"Toggling device at IP: {ip_address}")
    
    # Create TapoController
    controller = TapoController()
    
    # Check if controller initialized successfully
    if not controller.is_initialized:
        logger.error("Failed to initialize TapoController")
        return False
    
    try:
        # Get current state
        current_state = await controller.get_device_state(ip_address)
        if current_state is None:
            logger.error(f"Failed to get state for device at IP: {ip_address}")
            return False
        
        # Toggle state
        new_state = not current_state
        logger.info(f"Toggling device at {ip_address} from {current_state} to {new_state}")
        
        # Set new state
        result = await controller.set_device_state(ip_address, new_state)
        if result:
            logger.info(f"Successfully toggled device at {ip_address} to {new_state}")
            return True
        else:
            logger.error(f"Failed to toggle device at {ip_address}")
            return False
    except Exception as e:
        logger.error(f"Error toggling device: {e}")
        return False
    finally:
        # Clean up
        controller.cleanup()

async def toggle_device_by_name(device_name):
    """Toggle the state of a Tapo device by name from settings.json."""
    logger.info(f"Looking for device named: {device_name} in settings.json")
    
    # Load settings
    try:
        with open(SETTINGS_PATH, 'r') as f:
            settings = json.load(f)
    except Exception as e:
        logger.error(f"Error loading settings file: {e}")
        return False
    
    # Find device by name
    device_ip = None
    for device in settings.get('available_devices', []):
        if device.get('name') == device_name:
            device_ip = device.get('ip')
            break
    
    if not device_ip:
        logger.error(f"Device not found in settings.json: {device_name}")
        return False
    
    # Toggle device by IP
    return await toggle_device_by_ip(device_ip)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Toggle a Tapo device')
    parser.add_argument('device', type=str, help='Name or IP address of the device to toggle')
    parser.add_argument('--ip', action='store_true', help='Treat the device argument as an IP address')
    return parser.parse_args()

async def main():
    """Main function."""
    args = parse_arguments()
    
    if args.ip:
        # Toggle by IP
        await toggle_device_by_ip(args.device)
    else:
        # Toggle by name
        await toggle_device_by_name(args.device)

if __name__ == "__main__":
    asyncio.run(main()) 