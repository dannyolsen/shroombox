#!/usr/bin/env python3
"""
Test script for FanController
Tests the PID control of the fan based on CO2 levels.
"""

import os
import sys
import time
import asyncio
import logging
from typing import Dict, Any

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from devices.fan import NoctuaFan
from managers.settings_manager import SettingsManager
from managers.fan_controller import FanController

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('test_fan_controller')

# Mock callback for setting fan speed
async def mock_set_fan_speed(speed: float) -> None:
    logger.info(f"Mock set_fan_speed called with speed: {speed}%")

async def test_fan_controller():
    """Test the FanController class."""
    try:
        logger.info("Initializing test for FanController")
        
        # Initialize fan
        fan = NoctuaFan()
        
        # Initialize settings manager
        settings_manager = SettingsManager()
        
        # Initialize fan controller
        fan_controller = FanController(
            fan=fan,
            settings_manager=settings_manager,
            set_fan_speed_callback=mock_set_fan_speed
        )
        
        # Load settings
        settings = await settings_manager.load_settings()
        
        # Initialize fan controller from settings
        await fan_controller.initialize_from_settings(settings)
        
        # Get current CO2 setpoint
        co2_setpoint = fan_controller.co2_pid.setpoint
        logger.info(f"Current CO2 setpoint: {co2_setpoint}ppm")
        
        # Test PID control with different CO2 levels
        test_co2_levels = [
            co2_setpoint - 500,  # Below setpoint
            co2_setpoint,        # At setpoint
            co2_setpoint + 500,  # Above setpoint
            co2_setpoint + 1000  # Well above setpoint
        ]
        
        for co2 in test_co2_levels:
            logger.info(f"\nTesting with CO2 level: {co2}ppm (setpoint: {co2_setpoint}ppm)")
            
            # Update CO2 control
            fan_speed = fan_controller.update_co2_control(co2)
            
            # Log result
            logger.info(f"Resulting fan speed: {fan_speed}%")
            
            # Wait for a moment to see the effect
            await asyncio.sleep(1)
        
        # Test updating setpoint
        new_setpoint = co2_setpoint + 200
        logger.info(f"\nUpdating CO2 setpoint to {new_setpoint}ppm")
        fan_controller.update_setpoint(new_setpoint)
        
        # Test with new setpoint
        for co2 in test_co2_levels:
            logger.info(f"\nTesting with CO2 level: {co2}ppm (new setpoint: {new_setpoint}ppm)")
            
            # Update CO2 control
            fan_speed = fan_controller.update_co2_control(co2)
            
            # Log result
            logger.info(f"Resulting fan speed: {fan_speed}%")
            
            # Wait for a moment to see the effect
            await asyncio.sleep(1)
        
        # Test updating PID parameters
        logger.info("\nUpdating PID parameters")
        fan_controller.update_pid_parameters(-2.0, -0.02, -0.01)
        
        # Test with new PID parameters
        for co2 in test_co2_levels:
            logger.info(f"\nTesting with CO2 level: {co2}ppm (new PID parameters)")
            
            # Update CO2 control
            fan_speed = fan_controller.update_co2_control(co2)
            
            # Log result
            logger.info(f"Resulting fan speed: {fan_speed}%")
            
            # Wait for a moment to see the effect
            await asyncio.sleep(1)
        
        # Test sync_fan_speed
        logger.info("\nTesting sync_fan_speed")
        await fan_controller.sync_fan_speed()
        
        # Test update_fan_speed_in_settings
        logger.info("\nTesting update_fan_speed_in_settings")
        await fan_controller.update_fan_speed_in_settings(50)
        
        logger.info("\nTest completed successfully")
    
    except Exception as e:
        logger.error(f"Error in test: {e}")
    finally:
        # Clean up
        if 'fan' in locals():
            fan.cleanup()

if __name__ == "__main__":
    asyncio.run(test_fan_controller()) 