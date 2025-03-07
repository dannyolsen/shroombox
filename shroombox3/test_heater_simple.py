#!/usr/bin/env python3
"""
Simplified test script to diagnose heater control issues without requiring the SCD30 sensor
"""

import asyncio
import logging
import os
import json
from dotenv import load_dotenv
from datetime import datetime

# Import TapoController directly
from tapo_controller import TapoController

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('heater_test')

async def test_heater_control():
    """Test direct control of the heater."""
    
    logger.info("=== Starting Simplified Heater Test ===")
    
    # Load environment variables for Tapo credentials
    load_dotenv()
    
    # Initialize the Tapo controller
    tapo = TapoController(
        email=os.getenv('TAPO_EMAIL'),
        password=os.getenv('TAPO_PASSWORD')
    )
    
    # Load settings
    settings_path = 'config/settings.json'
    try:
        with open(settings_path, 'r') as f:
            settings = json.load(f)
            logger.info("Successfully loaded settings.json")
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        return
    
    # Get current phase and temperature settings
    try:
        current_phase = settings['environment']['current_phase']
        setpoint = float(settings['environment']['phases'][current_phase]['temp_setpoint'])
        hysteresis = float(settings['environment']['phases'][current_phase]['temp_hysteresis'])
        logger.info(f"Current phase: {current_phase}")
        logger.info(f"Temperature setpoint: {setpoint}°C")
        logger.info(f"Hysteresis: {hysteresis}°C")
        logger.info(f"Heater should turn ON below: {setpoint - hysteresis}°C")
    except Exception as e:
        logger.error(f"Error reading temperature settings: {e}")
    
    # Find heater in available devices
    heater = None
    for device in settings.get('available_devices', []):
        if device.get('role') == 'heater':
            heater = device
            break
    
    if not heater:
        logger.error("No heater device found in settings!")
        return
    
    logger.info(f"Found heater device: {heater['name']} at {heater['ip']}")
    
    # Check current state in settings
    logger.info(f"Current state in settings.json: {'ON' if heater.get('state', False) else 'OFF'}")
    
    # Check actual state from device
    actual_state = await tapo.get_device_state(heater['ip'])
    logger.info(f"Actual device state from Tapo: {'ON' if actual_state else 'OFF'}")
    
    # Make two diagnostic state changes to verify control works
    
    # 1. First, turn the heater OFF
    logger.info("Testing heater control - turning heater OFF...")
    success = await tapo.set_device_state(heater['ip'], False)
    if not success:
        logger.error("Failed to turn heater OFF!")
    else:
        logger.info("Successfully turned heater OFF")
    
    # Wait briefly
    await asyncio.sleep(2)
    
    # Check state again
    actual_state = await tapo.get_device_state(heater['ip'])
    logger.info(f"Device state after OFF command: {'ON' if actual_state else 'OFF'}")
    
    # 2. Now turn the heater ON
    logger.info("Testing heater control - turning heater ON...")
    success = await tapo.set_device_state(heater['ip'], True)
    if not success:
        logger.error("Failed to turn heater ON!")
    else:
        logger.info("Successfully turned heater ON")
    
    # Wait briefly
    await asyncio.sleep(2)
    
    # Check state again
    actual_state = await tapo.get_device_state(heater['ip'])
    logger.info(f"Device state after ON command: {'ON' if actual_state else 'OFF'}")
    
    # Update settings.json with the new state
    for device in settings.get('available_devices', []):
        if device.get('role') == 'heater':
            device['state'] = actual_state
    
    try:
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=4)
        logger.info(f"Updated settings.json with heater state: {'ON' if actual_state else 'OFF'}")
    except Exception as e:
        logger.error(f"Error updating settings.json: {e}")
    
    logger.info("=== Heater Test Complete ===")

async def main():
    await test_heater_control()

if __name__ == "__main__":
    asyncio.run(main()) 