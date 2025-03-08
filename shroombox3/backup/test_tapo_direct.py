#!/usr/bin/env python3
"""
Direct test of heater control using the tapo module directly
"""

import asyncio
import os
import json
from dotenv import load_dotenv
import sys
import traceback

print("Starting tapo_direct test...")

# Load environment variables
load_dotenv()

# Get credentials
tapo_email = os.getenv('TAPO_EMAIL')
tapo_password = os.getenv('TAPO_PASSWORD')

# Try importing tapo
try:
    from tapo import ApiClient
    print("Successfully imported tapo.ApiClient")
except ImportError as e:
    print(f"Error importing tapo: {e}")
    # Try to help with debugging
    import site
    print(f"Python path: {sys.path}")
    print(f"Site packages: {site.getsitepackages()}")
    sys.exit(1)

async def test_heater():
    """Test heater control using tapo directly."""
    
    print("\n===== TAPO DIRECT HEATER TEST =====")
    
    # Load settings
    try:
        with open('config/settings.json', 'r') as f:
            settings = json.load(f)
        print("Settings loaded successfully")
    except Exception as e:
        print(f"Error loading settings: {e}")
        return
    
    # Find heater
    heater = None
    for device in settings.get('available_devices', []):
        if device.get('role') == 'heater':
            heater = device
            break
    
    if not heater:
        print("No heater found in settings")
        return
    
    print(f"Found heater: {heater['name']} at {heater['ip']}")
    print(f"Current state in settings: {'ON' if heater.get('state', False) else 'OFF'}")
    
    # Get temperature settings
    try:
        current_phase = settings['environment']['current_phase']
        setpoint = float(settings['environment']['phases'][current_phase]['temp_setpoint'])
        hysteresis = float(settings['environment']['phases'][current_phase]['temp_hysteresis'])
        
        print(f"Current phase: {current_phase}")
        print(f"Temperature setpoint: {setpoint}°C")
        print(f"Hysteresis: {hysteresis}°C")
        print(f"Heat-on threshold: {setpoint - hysteresis}°C")
    except Exception as e:
        print(f"Error reading temperature settings: {e}")
    
    # Connect to heater
    try:
        print(f"\nInitializing ApiClient...")
        client = ApiClient(tapo_email, tapo_password)
        
        print(f"Connecting to heater at {heater['ip']}...")
        device = await client.p115(heater['ip'])
        
        # Get device info
        print("Getting device info...")
        info = await device.get_device_info()
        print(f"Device name: {info.nickname}")
        print(f"Model: {info.model}")
        print(f"MAC: {info.mac}")
        print(f"Current state: {'ON' if info.device_on else 'OFF'}")
        
        # Turn OFF
        print("\nTesting - turning heater OFF...")
        await device.off()
        print("OFF command sent")
        
        # Wait briefly
        await asyncio.sleep(2)
        
        # Check state
        info = await device.get_device_info()
        print(f"State after OFF command: {'ON' if info.device_on else 'OFF'}")
        
        # Turn ON
        print("\nTesting - turning heater ON...")
        await device.on()
        print("ON command sent")
        
        # Wait briefly
        await asyncio.sleep(2)
        
        # Check state
        info = await device.get_device_info()
        print(f"State after ON command: {'ON' if info.device_on else 'OFF'}")
        
        # Update settings
        for device in settings.get('available_devices', []):
            if device.get('role') == 'heater':
                device['state'] = info.device_on
        
        with open('config/settings.json', 'w') as f:
            json.dump(settings, f, indent=4)
        print(f"Updated settings.json with state: {'ON' if info.device_on else 'OFF'}")
        
        print("\nTest completed successfully!")
        
    except Exception as e:
        print(f"Error during test: {e}")
        print(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_heater()) 