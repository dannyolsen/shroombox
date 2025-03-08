#!/usr/bin/env python3
"""
Direct test of SCD30 sensor using the scd30_i2c library
"""

import time
import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('direct_scd30_test')


# Add parent directory to Python path so we can import from root
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))  # Go up two levels
sys.path.insert(0, parent_dir)

try:
    import scd30_i2c
except ImportError:
    logger.error("Failed to import scd30_i2c. Make sure it's installed.")
    sys.exit(1)

def test_scd30_direct():
    """Test the SCD30 sensor directly using the scd30_i2c library"""
    logger.info("Creating SCD30 instance...")
    sensor = scd30_i2c.SCD30()
    
    # Stop any existing measurements
    logger.info("Stopping any existing measurements...")
    try:
        sensor.stop_periodic_measurement()
        time.sleep(0.5)
    except Exception as e:
        logger.warning(f"Error stopping measurements: {e}")
    
    # Set measurement interval (2 seconds minimum)
    logger.info("Setting measurement interval...")
    if not sensor.set_measurement_interval(2):
        logger.warning("Failed to set measurement interval")
    
    # Start continuous measurements
    logger.info("Starting periodic measurement...")
    if not sensor.start_periodic_measurement():
        logger.error("Failed to start periodic measurement")
        return
    
    logger.info("Waiting for sensor to warm up (10 seconds)...")
    time.sleep(10)
    
    # Try to get measurements
    logger.info("Trying to get measurements...")
    for i in range(10):
        logger.info(f"Attempt {i+1}/10:")
        
        # Check if data is ready
        if sensor.get_data_ready():
            logger.info("Data is ready!")
            
            # Read measurement
            measurement = sensor.read_measurement()
            if measurement is not None:
                co2, temp, rh = measurement
                logger.info(f"CO2: {co2:.1f} ppm")
                logger.info(f"Temperature: {temp:.1f} °C")
                logger.info(f"Humidity: {rh:.1f} %")
                break
            else:
                logger.warning("Failed to read measurement")
        else:
            logger.info("Data not ready yet")
        
        time.sleep(2)
    
    # Stop measurements
    logger.info("Stopping measurements...")
    sensor.stop_periodic_measurement()
    logger.info("Done!")

if __name__ == "__main__":
    test_scd30_direct() 