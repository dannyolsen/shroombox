#!/usr/bin/env python3
"""
Direct test of heater control using PyP115 directly
"""

import asyncio
import logging
import os
import json
from dotenv import load_dotenv
import sys
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('direct_heater_test')

async def test_direct_heater():
    """Test direct control of the heater using P115 API."""
    
    logger.info("=== Starting Direct Heater Test ===")
    
    # Load environment variables for Tapo credentials
    load_dotenv()
    
    # Get credentials
    email = os.getenv('TAPO_EMAIL')
    password = os.getenv('TAPO_PASSWORD')
    
    if not email or not password:
        logger.error("Missing TAPO_EMAIL or TAPO_PASSWORD environment variables")
        return
    
    # Load settings to get heater IP
    settings_path = 'config/settings.json'
    try:
        with open(settings_path, 'r') as f:
            settings = json.load(f)
            logger.info("Successfully loaded settings.json")
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        return
    
    # Find heater in available devices
    heater = None
    for device in settings.get('available_devices', []):
        if device.get('role') == 'heater':
            heater = device
            break
    
    if not heater:
        logger.error("No heater device found in settings!")
        return
    
    heater_ip = heater['ip']
    logger.info(f"Found heater device: {heater['name']} at {heater_ip}")
    
    # Try to import the PyP115 only after we know we need it
    try:
        from PyP100 import PyP115
        logger.info("Successfully imported PyP115")
    except ImportError:
        logger.error("Failed to import PyP115. Please install it with: pip install PyP100")
        return
    
    # Connect to the plug
    try:
        logger.info(f"Connecting to heater at {heater_ip}...")
        p115 = PyP115.P115(heater_ip, email, password)
        
        # Login to the plug
        logger.info("Authenticating with device...")
        p115.handshake()
        p115.login()
        logger.info("Successfully authenticated")
        
        # Get device info
        logger.info("Getting device info...")
        device_info = p115.getDeviceInfo()
        if device_info:
            device_on = device_info.get('result', {}).get('device_on', False)
            logger.info(f"Current device state: {'ON' if device_on else 'OFF'}")
        
        # Turn the device OFF first
        logger.info("Testing control - turning heater OFF...")
        p115.turnOff()
        logger.info("OFF command sent")
        
        # Wait briefly
        await asyncio.sleep(2)
        
        # Check state
        device_info = p115.getDeviceInfo()
        if device_info:
            device_on = device_info.get('result', {}).get('device_on', False)
            logger.info(f"Device state after OFF command: {'ON' if device_on else 'OFF'}")
        
        # Turn the device ON
        logger.info("Testing control - turning heater ON...")
        p115.turnOn()
        logger.info("ON command sent")
        
        # Wait briefly
        await asyncio.sleep(2)
        
        # Check state
        device_info = p115.getDeviceInfo()
        if device_info:
            device_on = device_info.get('result', {}).get('device_on', False)
            logger.info(f"Device state after ON command: {'ON' if device_on else 'OFF'}")
        
        # Update settings.json with the new state
        for device in settings.get('available_devices', []):
            if device.get('role') == 'heater':
                device['state'] = device_on
        
        try:
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=4)
            logger.info(f"Updated settings.json with heater state: {'ON' if device_on else 'OFF'}")
        except Exception as e:
            logger.error(f"Error updating settings.json: {e}")
        
        logger.info("=== Direct Heater Test Complete ===")
        
    except Exception as e:
        logger.error(f"Error during direct heater test: {e}")
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_direct_heater()) 