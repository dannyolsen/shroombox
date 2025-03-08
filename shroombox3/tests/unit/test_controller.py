#!/usr/bin/env python3
"""
Test script for the SCD30 controller.
This script tests the SCD30Controller class.
"""

import os
import sys
import time
import asyncio
import logging

# Add parent directory to Python path so we can import from root
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))  # Go up two levels
sys.path.insert(0, parent_dir)

# Import from project
from devices.sensor import SCD30Controller
from utils import logging_setup

# Set up logging
logging_setup.setup_logging()
logger = logging_setup.get_logger('test_controller')

async def test_controller():
    """Test the modified SCD30Controller class"""
    print("Initializing SCD30Controller...")
    controller = SCD30Controller()
    
    print("Waiting for sensor to warm up...")
    # Wait for the sensor to warm up (shorter timeout)
    for i in range(5):
        if controller.is_warmed_up():
            print("Sensor is warmed up!")
            break
        print(f"Waiting... ({i+1}/5)")
        await asyncio.sleep(1)
    
    print("\nChecking if sensor is available...")
    is_available = controller.is_available()
    print(f"Sensor available: {is_available}")
    
    print("\nTrying to get measurements...")
    for i in range(5):
        print(f"Attempt {i+1}/5:")
        measurements = await controller.get_measurements()
        print(f"Measurements: {measurements}")
        
        if measurements is not None:
            co2, temp, humidity = measurements
            print(f"CO2: {co2:.1f} ppm")
            print(f"Temperature: {temp:.1f} °C")
            print(f"Humidity: {humidity:.1f} %")
            break
        
        await asyncio.sleep(2)
    
    print("\nCleaning up...")
    controller.cleanup()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(test_controller()) 