"""
SCD30 CO2 Sensor Controller
Manages the SCD30 CO2, temperature, and humidity sensor.

DEPRECATED: This implementation is deprecated and will be removed in a future version.
Please use the SimpleSCD30Controller from devices.simple_sensor instead.
"""

import logging
import time
import asyncio
import math
import json
import os
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
import scd30_i2c

from devices.base import Device
from utils.singleton import singleton

# Set up logging
logger = logging.getLogger('shroombox.sensor')

# Define the path to the measurements file
MEASUREMENTS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'measurements.json')

@singleton
class SCD30Controller(Device):
    """
    Controller for the SCD30 CO2, temperature, and humidity sensor.
    
    This class implements the Device interface and provides methods
    to read measurements from the SCD30 sensor.
    
    DEPRECATED: This implementation is deprecated and will be removed in a future version.
    Please use the SimpleSCD30Controller from devices.simple_sensor instead.
    """
    
    def __init__(self, measurement_interval: int = 5):
        """
        Initialize SCD30 controller.
        
        Args:
            measurement_interval: Time between measurements in seconds (minimum 2)
        """
        logger.warning("DEPRECATED: SCD30Controller is deprecated. Please use SimpleSCD30Controller instead.")
        self.sensor = None
        self.measurement_interval = max(2, measurement_interval)  # Ensure minimum 2 seconds
        self._last_measurement_time = 0
        self._last_valid_measurement = None  # Store last valid measurement as fallback
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3
        self._initialized = False
        self._initialization_time = 0
        self._warmup_period = 10  # Sensor warmup period in seconds
        self._initialization_attempts = 0
        self._max_initialization_attempts = 5
        self.initialize()
    
    def initialize(self) -> bool:
        """
        Initialize the SCD30 sensor with error handling.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        try:
            self._initialization_attempts += 1
            logger.info(f"Initializing SCD30 sensor (attempt {self._initialization_attempts}/{self._max_initialization_attempts})...")
            
            # Create a new sensor instance - exactly like in the simple test script
            self.sensor = scd30_i2c.SCD30()
            
            # Start continuous measurement - exactly like in the simple test script
            result = self.sensor.start_periodic_measurement()
            
            if result:
                logger.info("Started periodic measurement successfully")
                self._initialization_time = time.time()
                self._initialized = True
                return True
            else:
                logger.error("Failed to start periodic measurement")
                return False
            
        except Exception as e:
            logger.error(f"Error initializing SCD30 sensor: {e}")
            self._initialized = False
            return False
    
    def is_available(self) -> bool:
        """
        Check if the sensor is available.
        
        Returns:
            bool: True if the sensor is available, False otherwise
        """
        if not self.is_initialized:
            return False
            
        try:
            return self.sensor.get_data_ready()
        except Exception as e:
            logger.error(f"Error checking if sensor is available: {e}")
            return False
    
    def is_warmed_up(self) -> bool:
        """
        Check if the sensor has completed its warmup period.
        
        Returns:
            bool: True if the sensor is warmed up, False otherwise
        """
        if not self.is_initialized:
            return False
            
        current_time = time.time()
        return (current_time - self._initialization_time) >= self._warmup_period
    
    def _validate_measurement(self, co2: float, temp: float, rh: float) -> bool:
        """
        Validate measurement values to ensure they are within reasonable ranges.
        
        Args:
            co2: CO2 measurement in ppm
            temp: Temperature in Celsius
            rh: Relative humidity as percentage
            
        Returns:
            bool: True if the measurement is valid, False otherwise
        """
        # Check for NaN values
        if math.isnan(co2) or math.isnan(temp) or math.isnan(rh):
            logger.warning("Measurement contains NaN values")
            return False
            
        # Check CO2 range (0-40000 ppm, but typically 400-5000)
        if co2 < 0 or co2 > 40000:
            logger.warning(f"CO2 value out of range: {co2} ppm")
            return False
            
        # Check temperature range (-40 to 70°C)
        if temp < -40 or temp > 70:
            logger.warning(f"Temperature value out of range: {temp}°C")
            return False
            
        # Check humidity range (0-100%)
        if rh < 0 or rh > 100:
            logger.warning(f"Humidity value out of range: {rh}%")
            return False
            
        return True
    
    def _write_measurements_to_file(self, co2: float, temp: float, rh: float, source: str = 'sensor') -> bool:
        """
        Write measurements to a JSON file.
        
        Args:
            co2: CO2 measurement in ppm
            temp: Temperature in Celsius
            rh: Relative humidity as percentage
            source: Source of the measurement ('sensor', 'cache', etc.)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create data directory if it doesn't exist
            data_dir = os.path.dirname(MEASUREMENTS_FILE)
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
                logger.info(f"Created data directory: {data_dir}")
            
            # Prepare measurement data
            measurement_data = {
                'co2': round(co2, 1),
                'temperature': round(temp, 1),
                'humidity': round(rh, 1),
                'source': source,
                'timestamp': datetime.now().isoformat(),
                'unix_timestamp': time.time()
            }
            
            # Write to file
            with open(MEASUREMENTS_FILE, 'w') as f:
                json.dump(measurement_data, f, indent=2)
                
            logger.debug(f"Wrote measurements to file: {MEASUREMENTS_FILE}")
            return True
        except Exception as e:
            logger.error(f"Error writing measurements to file: {e}")
            return False
    
    def read_measurements_from_file(self) -> Optional[Dict[str, Any]]:
        """
        Read measurements from the JSON file.
        
        Returns:
            Optional[Dict[str, Any]]: Measurement data or None if failed
        """
        try:
            if not os.path.exists(MEASUREMENTS_FILE):
                logger.warning(f"Measurements file not found: {MEASUREMENTS_FILE}")
                return None
                
            with open(MEASUREMENTS_FILE, 'r') as f:
                data = json.load(f)
                
            # Check if data is stale (older than 5 minutes)
            if 'unix_timestamp' in data:
                age = time.time() - data['unix_timestamp']
                if age > 300:  # 5 minutes
                    logger.warning(f"Measurements data is stale ({age:.1f}s old)")
                    data['is_stale'] = True
                else:
                    data['is_stale'] = False
                    
                # Add age to data
                data['age'] = age
                
            return data
        except Exception as e:
            logger.error(f"Error reading measurements from file: {e}")
            return None
    
    async def get_measurements(self) -> Optional[Tuple[float, float, float]]:
        """
        Get measurements from the sensor.
        
        Returns:
            Optional[Tuple[float, float, float]]: (CO2, temperature, humidity) or None if failed
        """
        # Check if sensor is initialized
        if not self.is_initialized:
            logger.warning("Sensor not initialized, attempting to initialize...")
            if not self.initialize():
                logger.error("Failed to initialize sensor")
                return None
        
        # Check if enough time has passed since last measurement
        current_time = time.time()
        time_since_last = current_time - self._last_measurement_time
        
        if time_since_last < self.measurement_interval:
            # If we have a recent valid measurement, return it
            if self._last_valid_measurement is not None:
                return self._last_valid_measurement
            
            # Otherwise wait until measurement interval has passed
            wait_time = self.measurement_interval - time_since_last
            logger.debug(f"Waiting {wait_time:.1f}s for next measurement")
            await asyncio.sleep(wait_time)
        
        # Check if sensor is warmed up
        if not self.is_warmed_up():
            logger.warning("Sensor still in warmup period")
            await asyncio.sleep(1)  # Short delay to prevent rapid retries
            return None
        
        # Check if data is ready - simplified approach like in the test script
        try:
            if self.sensor.get_data_ready():
                # Read measurement
                measurement = self.sensor.read_measurement()
                if measurement is not None:
                    co2, temp, rh = measurement
                    
                    # Validate measurement
                    if self._validate_measurement(co2, temp, rh):
                        # Update last measurement time and reset failure counter
                        self._last_measurement_time = current_time
                        self._consecutive_failures = 0
                        self._last_valid_measurement = (co2, temp, rh)
                        
                        # Write measurements to file
                        self._write_measurements_to_file(co2, temp, rh, source='sensor')
                        
                        return co2, temp, rh
                    else:
                        logger.warning(f"Invalid measurement: CO2={co2}, Temp={temp}, RH={rh}")
                else:
                    logger.warning("Failed to read measurement")
            else:
                logger.debug("Data not ready yet")
                
            # If we have a recent valid measurement, return it as fallback
            if self._last_valid_measurement is not None:
                return self._last_valid_measurement
                
            # Otherwise return None
            return None
                
        except Exception as e:
            logger.error(f"Error reading measurement: {e}")
            self._consecutive_failures += 1
            
            if self._consecutive_failures >= self._max_consecutive_failures:
                logger.error(f"Too many consecutive failures ({self._consecutive_failures}), reinitializing sensor")
                self._initialized = False
                self.initialize()
                
            return self._last_valid_measurement
    
    def set_measurement_interval(self, interval: int) -> bool:
        """
        Set the measurement interval.
        
        Args:
            interval: Measurement interval in seconds (2-1800)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_initialized:
            logger.warning("Cannot set measurement interval: sensor not initialized")
            return False
        
        # Ensure interval is within valid range
        interval = max(2, min(1800, interval))
        
        try:
            # Stop measurements before changing interval
            self.sensor.stop_periodic_measurement()
            time.sleep(0.5)  # Wait for the command to take effect
            
            # Set new interval
            if not self.sensor.set_measurement_interval(interval):
                logger.error(f"Failed to set measurement interval to {interval}s")
                return False
            
            # Restart measurements
            if not self.sensor.start_periodic_measurement():
                logger.error("Failed to restart periodic measurement")
                return False
            
            self.measurement_interval = interval
            logger.info(f"Measurement interval set to {interval}s")
            return True
            
        except Exception as e:
            logger.error(f"Error setting measurement interval: {e}")
            return False
    
    def cleanup(self) -> None:
        """Clean up resources before shutdown."""
        if self.is_initialized and self.sensor is not None:
            try:
                logger.info("Cleaning up SCD30 sensor")
                self.sensor.stop_periodic_measurement()
                self._initialized = False
            except Exception as e:
                logger.error(f"Error cleaning up SCD30 sensor: {e}")
    
    @property
    def is_initialized(self) -> bool:
        """
        Check if the sensor is initialized.
        
        Returns:
            bool: True if the sensor is initialized, False otherwise
        """
        return self._initialized and self.sensor is not None
    
    @property
    def name(self) -> str:
        """
        Get the device name.
        
        Returns:
            str: The name of the device
        """
        return "SCD30 CO2 Sensor" 