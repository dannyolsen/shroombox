#!/usr/bin/env python3
"""
Test script to check if the SCD30 sensor is working.
"""

import asyncio
import logging
from devices.simple_sensor import SimpleSCD30Controller

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    """Main function to test the sensor."""
    print("Testing SCD30 sensor...")
    
    # Initialize sensor
    sensor = SimpleSCD30Controller()
    print(f"Sensor initialized: {sensor.is_initialized}")
    
    # Try to get measurements
    print("Getting measurements...")
    measurements = await sensor.get_measurements()
    print(f"Measurements: {measurements}")
    
    if measurements:
        co2, temp, rh = measurements
        print(f"CO2: {co2:.1f} ppm")
        print(f"Temperature: {temp:.1f} °C")
        print(f"Relative Humidity: {rh:.1f} %")
    else:
        print("Failed to get measurements")

if __name__ == "__main__":
    asyncio.run(main()) 