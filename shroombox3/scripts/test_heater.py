#!/usr/bin/env python3
"""
Test script for heater control.
"""

import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from managers.device_manager import DeviceManager

# Create logs directory if it doesn't exist
os.makedirs('logs/tests', exist_ok=True)

# Set up logging with timestamp in filename
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_file = f'logs/tests/heater_test_{timestamp}.log'

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler(log_file)  # Log to file with timestamp
    ]
)
logger = logging.getLogger("heater_test")
logger.info(f"Starting heater test, logging to: {log_file}")

async def test_heater():
    """Test heater control."""
    try:
        # Load environment variables
        load_dotenv()
        logger.info("Environment variables loaded")
        
        # Initialize device manager
        logger.info("Initializing device manager...")
        device_manager = DeviceManager()
        await device_manager.initialize()
        logger.info("Device manager initialized")
        
        # Get settings
        settings = await device_manager.get_settings()
        heater = next((d for d in settings.get('available_devices', []) 
                      if d.get('role') == 'heater'), None)
        if not heater:
            logger.error("No heater device found in settings!")
            return
        logger.info(f"Found heater device: {heater['name']} at {heater['ip']}")
        
        # Get current heater state
        current_state = await device_manager.get_device_state('heater')
        logger.info(f"Current heater state: {'ON' if current_state else 'OFF'}")
        
        # Test turning heater OFF
        logger.info("Testing - turning heater OFF...")
        success = await device_manager.set_device_state('heater', False)
        logger.info(f"Turn OFF command {'succeeded' if success else 'failed'}")
        
        await asyncio.sleep(2)  # Wait for state change
        
        # Verify OFF state
        off_state = await device_manager.get_device_state('heater')
        logger.info(f"Heater state after OFF command: {'ON' if off_state else 'OFF'}")
        
        # Test turning heater ON
        logger.info("Testing - turning heater ON...")
        success = await device_manager.set_device_state('heater', True)
        logger.info(f"Turn ON command {'succeeded' if success else 'failed'}")
        
        await asyncio.sleep(2)  # Wait for state change
        
        # Verify ON state
        on_state = await device_manager.get_device_state('heater')
        logger.info(f"Heater state after ON command: {'ON' if on_state else 'OFF'}")
        
        logger.info("Heater test completed successfully")
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_heater()) 