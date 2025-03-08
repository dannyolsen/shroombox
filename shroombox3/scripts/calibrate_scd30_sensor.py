#!/usr/bin/env python3
"""
SCD30 Sensor Calibration Utility
Tool for calibrating the SCD30 CO2, temperature, and humidity sensor.
"""

import time
import sys
import os
import logging
from typing import Tuple, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('scd30_calibration')

# Add the parent directory to the path so we can import from the project
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from scd30_i2c import SCD30
except ImportError:
    logger.error("Failed to import scd30_i2c. Make sure it's installed.")
    sys.exit(1)

def take_measurements(sensor: SCD30, count: int = 5) -> Optional[Tuple[float, float, float]]:
    """
    Take multiple measurements from the sensor and return the last valid one.
    
    Args:
        sensor: The SCD30 sensor instance
        count: Number of measurements to take
        
    Returns:
        Optional[Tuple[float, float, float]]: The last valid measurement (CO2, temp, humidity) or None if failed
    """
    last_measurement = None
    
    for i in range(count):
        logger.info(f"Taking measurement {i+1}/{count}...")
        
        # Wait for data to be ready
        for _ in range(10):  # Try for up to 10 seconds
            if sensor.get_data_ready():
                break
            time.sleep(1)
        
        # Read measurement if data is ready
        if sensor.get_data_ready():
            measurement = sensor.read_measurement()
            if measurement is not None:
                co2, temp, humidity = measurement
                logger.info(f"CO2: {co2:.2f}ppm, Temperature: {temp:.2f}°C, Humidity: {humidity:.2f}%")
                last_measurement = (co2, temp, humidity)
            else:
                logger.warning("Failed to read measurement")
        else:
            logger.warning("Data not ready")
            
        # Wait between measurements
        time.sleep(2)
        
    return last_measurement

def enable_automatic_calibration(sensor: SCD30) -> bool:
    """
    Enable automatic self-calibration on the SCD30 sensor.
    
    Args:
        sensor: The SCD30 sensor instance
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info("Enabling automatic self-calibration...")
        sensor.set_automatic_self_calibration(True)
        
        # Verify it was set
        if sensor.get_automatic_self_calibration():
            logger.info("Automatic self-calibration is now enabled.")
            logger.info("Note: The sensor will self-calibrate over the next 7 days,")
            logger.info("      assuming it sees fresh air (~400ppm) for at least 1 hour each day.")
            return True
        else:
            logger.error("Failed to enable automatic self-calibration")
            return False
    except Exception as e:
        logger.error(f"Error enabling automatic self-calibration: {e}")
        return False

def perform_forced_calibration(sensor: SCD30, reference_co2_ppm: int = 400) -> bool:
    """
    Perform forced calibration with a known CO2 reference value.
    
    Args:
        sensor: The SCD30 sensor instance
        reference_co2_ppm: Reference CO2 value in ppm (default is 400 for outdoor air)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Performing forced calibration with reference value of {reference_co2_ppm}ppm...")
        sensor.forced_recalibration_with_reference(reference_co2_ppm)
        logger.info("Forced calibration completed")
        return True
    except Exception as e:
        logger.error(f"Error performing forced calibration: {e}")
        return False

def calibrate_scd30():
    """Main calibration function for the SCD30 sensor."""
    # Initialize sensor
    logger.info("Initializing SCD30 sensor...")
    sensor = SCD30()
    
    # Start continuous measurement
    logger.info("Starting continuous measurement...")
    if not sensor.start_periodic_measurement():
        logger.error("Failed to start periodic measurement")
        return
    
    # Wait for sensor to warm up
    logger.info("Waiting for sensor to warm up (10 seconds)...")
    time.sleep(10)
    
    # Take initial measurements
    logger.info("Taking initial measurements...")
    initial_measurements = take_measurements(sensor, count=5)
    
    if initial_measurements is None:
        logger.error("Failed to get initial measurements")
        return
    
    # Ask user which calibration method to use
    print("\nCalibration Methods:")
    print("1. Automatic Self-Calibration (ASC)")
    print("2. Forced Calibration with Reference Value")
    
    choice = input("\nSelect calibration method (1/2): ")
    
    if choice == "1":
        # Enable automatic self-calibration
        if enable_automatic_calibration(sensor):
            # Take measurements after calibration
            logger.info("\nTaking measurements after enabling ASC...")
            take_measurements(sensor, count=5)
    elif choice == "2":
        # Get reference CO2 value
        try:
            reference_co2 = int(input("\nEnter reference CO2 value in ppm (default 400): ") or "400")
        except ValueError:
            logger.error("Invalid input. Using default value of 400ppm.")
            reference_co2 = 400
        
        # Perform forced calibration
        if perform_forced_calibration(sensor, reference_co2):
            # Take measurements after calibration
            logger.info("\nTaking measurements after forced calibration...")
            take_measurements(sensor, count=5)
    else:
        logger.error("Invalid choice")
    
    # Stop measurements
    logger.info("Stopping measurements...")
    sensor.stop_periodic_measurement()
    logger.info("Calibration process completed")

if __name__ == "__main__":
    try:
        calibrate_scd30()
    except KeyboardInterrupt:
        print("\nCalibration cancelled by user")
    except Exception as e:
        logger.error(f"Error during calibration: {e}") 