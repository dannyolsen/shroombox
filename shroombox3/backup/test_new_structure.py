#!/usr/bin/env python3
"""
Test script to verify the new structure.
"""

import asyncio
import logging
from utils import logging_setup
from devices.fan import NoctuaFan
from devices.sensor import SCD30Controller
from managers.device_manager import DeviceManager

# Set up logging
logging_setup.setup_logging()
logger = logging_setup.get_logger('test')

async def test_fan():
    """Test the fan controller."""
    logger.info("Testing fan controller...")
    
    fan = NoctuaFan()
    logger.info(f"Fan initialized: {fan.is_initialized}")
    logger.info(f"Fan name: {fan.name}")
    
    # Test fan speed
    logger.info("Setting fan speed to 50%")
    fan.set_speed(50)
    logger.info(f"Current fan speed: {fan.get_speed()}%")
    
    # Test CPU temperature
    cpu_temp = fan.get_cpu_temp()
    logger.info(f"CPU temperature: {cpu_temp}°C")
    
    # Test cleanup
    logger.info("Cleaning up fan")
    fan.cleanup()
    
    return True

async def test_sensor():
    """Test the sensor controller."""
    logger.info("Testing sensor controller...")
    
    sensor = SCD30Controller()
    logger.info(f"Sensor initialized: {sensor.is_initialized}")
    logger.info(f"Sensor name: {sensor.name}")
    
    # Test measurements
    logger.info("Getting measurements...")
    measurements = await sensor.get_measurements()
    
    if measurements:
        co2, temp, rh = measurements
        logger.info(f"CO2: {co2} ppm")
        logger.info(f"Temperature: {temp}°C")
        logger.info(f"Humidity: {rh}%")
    else:
        logger.warning("Failed to get measurements")
    
    # Test cleanup
    logger.info("Cleaning up sensor")
    sensor.cleanup()
    
    return True

async def test_device_manager():
    """Test the device manager."""
    logger.info("Testing device manager...")
    
    device_manager = DeviceManager()
    
    # Test fan control
    logger.info("Setting fan speed to 75%")
    await device_manager.set_fan_speed(75)
    logger.info(f"Current fan speed: {device_manager.get_fan_speed()}%")
    
    # Test sensor
    logger.info("Getting measurements...")
    measurements = await device_manager.get_measurements()
    
    if measurements:
        co2, temp, rh = measurements
        logger.info(f"CO2: {co2} ppm")
        logger.info(f"Temperature: {temp}°C")
        logger.info(f"Humidity: {rh}%")
    else:
        logger.warning("Failed to get measurements")
    
    # Test settings
    logger.info("Getting settings...")
    settings = await device_manager.get_settings()
    logger.info(f"Current phase: {settings.get('environment', {}).get('current_phase', 'unknown')}")
    
    # Test cleanup
    logger.info("Cleaning up device manager")
    device_manager.cleanup()
    
    return True

async def main():
    """Run all tests."""
    logger.info("Starting tests...")
    
    try:
        # Test individual components
        await test_fan()
        await test_sensor()
        
        # Test device manager
        await test_device_manager()
        
        logger.info("All tests completed successfully")
    except Exception as e:
        logger.error(f"Test failed: {e}")
    
if __name__ == "__main__":
    asyncio.run(main()) 