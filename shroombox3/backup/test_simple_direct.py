#!/usr/bin/env python3
"""
Super simplified heater test using only PyP100
"""

import asyncio
import os
import json
from dotenv import load_dotenv
import time
import sys

# Load environment variables
load_dotenv()

# Get credentials
tapo_email = os.getenv('TAPO_EMAIL')
tapo_password = os.getenv('TAPO_PASSWORD')

# Check for PyP100
try:
    from PyP100 import PyP115
    print("PyP115 module loaded successfully")
except ImportError:
    print("Error: PyP100 module not found. Install with:")
    print("pip install PyP100")
    sys.exit(1)

def load_settings():
    """Load settings from file."""
    try:
        with open('config/settings.json', 'r') as f:
            settings = json.load(f)
            print("Settings loaded successfully")
            return settings
    except Exception as e:
        print(f"Error loading settings: {e}")
        return None

def find_heater(settings):
    """Find heater device in settings."""
    if not settings:
        return None
        
    for device in settings.get('available_devices', []):
        if device.get('role') == 'heater':
            print(f"Found heater: {device['name']} at {device['ip']}")
            return device
    
    print("No heater found in settings")
    return None

def test_heater_control():
    """Test heater control using PyP115 directly."""
    
    print("\n===== SIMPLE HEATER TEST =====")
    
    # Load settings and find heater
    settings = load_settings()
    heater = find_heater(settings)
    
    if not heater:
        print("Cannot continue without heater information")
        return
    
    # Get current setting information
    current_phase = settings['environment']['current_phase']
    temp_setpoint = settings['environment']['phases'][current_phase]['temp_setpoint']
    temp_hysteresis = settings['environment']['phases'][current_phase]['temp_hysteresis']
    
    print(f"Current phase: {current_phase}")
    print(f"Temperature setpoint: {temp_setpoint}°C")
    print(f"Hysteresis: {temp_hysteresis}°C")
    print(f"Heat-on threshold: {float(temp_setpoint) - float(temp_hysteresis)}°C")
    
    # Connect to heater
    print(f"\nConnecting to heater at {heater['ip']}...")
    try:
        p115 = PyP115.P115(heater['ip'], tapo_email, tapo_password)
        
        # Login
        print("Authenticating...")
        p115.handshake()
        p115.login()
        print("Authentication successful!")
        
        # Get initial state
        print("Getting device info...")
        device_info = p115.getDeviceInfo()
        device_on = device_info.get('result', {}).get('device_on', False)
        print(f"Current device state: {'ON' if device_on else 'OFF'}")
        
        # Test turning OFF
        print("\nTesting - Turning device OFF...")
        p115.turnOff()
        time.sleep(2)  # Wait for state change
        
        # Verify OFF state
        device_info = p115.getDeviceInfo()
        device_on = device_info.get('result', {}).get('device_on', False)
        print(f"Device state after OFF command: {'ON' if device_on else 'OFF'}")
        
        # Test turning ON
        print("\nTesting - Turning device ON...")
        p115.turnOn()
        time.sleep(2)  # Wait for state change
        
        # Verify ON state
        device_info = p115.getDeviceInfo()
        device_on = device_info.get('result', {}).get('device_on', False)
        print(f"Device state after ON command: {'ON' if device_on else 'OFF'}")
        
        # Update settings
        for device in settings.get('available_devices', []):
            if device.get('role') == 'heater':
                device['state'] = device_on
        
        # Save updated settings
        with open('config/settings.json', 'w') as f:
            json.dump(settings, f, indent=4)
        print(f"Updated settings.json with state: {'ON' if device_on else 'OFF'}")
        
        print("\nTest completed successfully!")
        
    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    test_heater_control() 