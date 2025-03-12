#!/usr/bin/env python3
"""
Script to simulate SCD30 sensor readings for testing purposes.
This can be used when the actual sensor hardware is not available or not working.
"""

import os
import sys
import json
import time
import random
from datetime import datetime

# Add parent directory to Python path so we can import from root
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Define the path to the measurements file
MEASUREMENTS_FILE = os.path.join(parent_dir, 'data', 'measurements.json')

def generate_random_measurements():
    """Generate random but realistic sensor measurements."""
    # Generate random values within realistic ranges
    co2 = random.randint(400, 1200)  # CO2 in ppm
    temperature = round(random.uniform(18.0, 25.0), 1)  # Temperature in °C
    humidity = round(random.uniform(40.0, 80.0), 1)  # Humidity in %
    
    return co2, temperature, humidity

def update_measurements_file():
    """Update the measurements file with simulated sensor readings."""
    # Create data directory if it doesn't exist
    data_dir = os.path.dirname(MEASUREMENTS_FILE)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"Created data directory: {data_dir}")
    
    # Generate simulated measurements
    co2, temp, humidity = generate_random_measurements()
    
    # Prepare measurement data
    measurement_data = {
        'co2': co2,
        'temperature': temp,
        'humidity': humidity,
        'source': 'simulated',
        'timestamp': datetime.now().isoformat(),
        'unix_timestamp': time.time()
    }
    
    # Write to file
    with open(MEASUREMENTS_FILE, 'w') as f:
        json.dump(measurement_data, f, indent=2)
    
    print(f"Updated measurements: CO2={co2}ppm, Temp={temp}°C, RH={humidity}%")

def main():
    """Run the simulation."""
    print("Starting sensor simulation...")
    print(f"Writing to: {MEASUREMENTS_FILE}")
    
    try:
        while True:
            update_measurements_file()
            time.sleep(10)  # Update every 10 seconds
    except KeyboardInterrupt:
        print("\nSimulation stopped by user")

if __name__ == "__main__":
    main() 