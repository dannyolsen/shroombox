#!/usr/bin/env python3
"""
Test script to verify heater control using the existing tapo_controller
"""

import asyncio
import logging
import os
import json
from dotenv import load_dotenv
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('heater_test')

async def run_heater_test():
    """Test the heater control using tapo_controller"""
    logger.info("===== STARTING HEATER CONTROL TEST =====")
    
    # Import the controller here to avoid module import errors
    try:
        from tapo_controller import TapoController
        logger.info("Successfully imported TapoController")
    except ImportError as e:
        logger.error(f"Failed to import TapoController: {e}")
        return
    
    # Load environment variables
    load_dotenv()
    
    # Initialize controller
    tapo_email = os.getenv('TAPO_EMAIL')
    tapo_password = os.getenv('TAPO_PASSWORD')
    
    if not tapo_email or not tapo_password:
        logger.error("Missing TAPO_EMAIL or TAPO_PASSWORD environment variables")
        return
    
    # Load settings to get heater information
    settings_path = 'config/settings.json'
    try:
        with open(settings_path, 'r') as f:
            settings = json.load(f)
        logger.info("Successfully loaded settings.json")
    except Exception as e:
        logger.error(f"Failed to load settings.json: {e}")
        return
    
    # Find heater device
    heater = None
    for device in settings.get('available_devices', []):
        if device.get('role') == 'heater':
            heater = device
            break
    
    if not heater:
        logger.error("No heater device found in settings.json!")
        return
    
    logger.info(f"Found heater: {heater['name']} at {heater['ip']}")
    logger.info(f"Current state in settings: {'ON' if heater.get('state', False) else 'OFF'}")
    
    # Initialize controller
    logger.info("Initializing TapoController...")
    controller = TapoController(
        email=tapo_email,
        password=tapo_password
    )
    
    # Current settings
    current_phase = settings['environment']['current_phase']
    setpoint = float(settings['environment']['phases'][current_phase]['temp_setpoint'])
    hysteresis = float(settings['environment']['phases'][current_phase]['temp_hysteresis'])
    
    logger.info(f"Current phase: {current_phase}")
    logger.info(f"Temperature setpoint: {setpoint}°C")
    logger.info(f"Hysteresis: {hysteresis}°C")
    logger.info(f"Heat-on threshold: {setpoint - hysteresis}°C")
    
    # Test both states - first check current state
    current_state = await controller.get_device_state(heater['ip'])
    logger.info(f"Current heater state from device: {'ON' if current_state else 'OFF'}")
    
    # Test turning OFF
    logger.info("Testing - turning heater OFF...")
    success = await controller.set_device_state(heater['ip'], False)
    logger.info(f"Turn OFF command {'succeeded' if success else 'failed'}")
    
    await asyncio.sleep(2)  # Wait for state change
    
    # Verify OFF state
    off_state = await controller.get_device_state(heater['ip'])
    logger.info(f"Heater state after OFF command: {'ON' if off_state else 'OFF'}")
    
    # Test turning ON
    logger.info("Testing - turning heater ON...")
    success = await controller.set_device_state(heater['ip'], True)
    logger.info(f"Turn ON command {'succeeded' if success else 'failed'}")
    
    await asyncio.sleep(2)  # Wait for state change
    
    # Verify ON state
    on_state = await controller.get_device_state(heater['ip'])
    logger.info(f"Heater state after ON command: {'ON' if on_state else 'OFF'}")
    
    # Update settings with final state
    for device in settings.get('available_devices', []):
        if device.get('role') == 'heater':
            device['state'] = on_state
    
    # Save updated settings
    try:
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=4)
        logger.info(f"Updated settings.json with heater state: {'ON' if on_state else 'OFF'}")
    except Exception as e:
        logger.error(f"Error updating settings.json: {e}")
    
    logger.info("===== HEATER CONTROL TEST COMPLETE =====")

if __name__ == "__main__":
    asyncio.run(run_heater_test()) 