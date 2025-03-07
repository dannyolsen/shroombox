#!/usr/bin/env python3
import asyncio
import os
import sys
import json
from dotenv import load_dotenv
from main import EnvironmentController

# Load environment variables
load_dotenv()

async def toggle_device(device_role):
    """Toggle the state of a device with the specified role."""
    try:
        # Initialize EnvironmentController
        controller = EnvironmentController()
        await controller.start()  # Initialize async resources
        
        # Load settings to get device info
        with open('config/settings.json', 'r') as f:
            settings = json.load(f)
        
        # Find device with the specified role
        device = next((d for d in settings['available_devices'] if d.get('role') == device_role), None)
        if not device:
            print(f"No device found with role: {device_role}")
            return
        
        # Get current device state
        current_state = device['state']
        print(f"Current {device_role} state in settings: {'ON' if current_state else 'OFF'}")
        
        # Make sure device assignments are loaded
        controller._load_device_assignments()
        
        # Initialize devices
        await controller.initialize_devices()
        
        # Toggle the state
        new_state = not current_state
        print(f"Setting {device_role} to {'ON' if new_state else 'OFF'}...")
        
        if device_role == 'heater':
            success = await controller.set_heater_state(new_state)
        elif device_role == 'humidifier':
            await controller.set_humidifier_state(new_state)
            success = True  # set_humidifier_state doesn't return a value
        
        if success:
            print(f"Successfully set {device_role} to {'ON' if new_state else 'OFF'}")
        else:
            print(f"Failed to set {device_role} state")
        
        # Don't clean up controller resources to keep the device state
        print("Skipping cleanup to keep device state")
    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_device_toggle.py [heater|humidifier]")
        sys.exit(1)
    
    device_role = sys.argv[1].lower()
    if device_role not in ['heater', 'humidifier']:
        print("Invalid device role. Use 'heater' or 'humidifier'")
        sys.exit(1)
    
    asyncio.run(toggle_device(device_role)) 