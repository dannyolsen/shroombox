#!/usr/bin/env python3
"""
Test script for the simplified SCD30 controller
"""

import asyncio
import sys
import os
import logging


# Add parent directory to Python path so we can import from root
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))  # Go up two levels
sys.path.insert(0, parent_dir)

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from devices.simple_sensor import SimpleSCD30Controller

async def test_simple_controller():
    """Test the simplified SCD30 controller"""
    print("Initializing SimpleSCD30Controller...")
    controller = SimpleSCD30Controller()
    
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
    asyncio.run(test_simple_controller()) 