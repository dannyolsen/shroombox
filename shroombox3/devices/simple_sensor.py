"""
Simple SCD30 CO2 Sensor Controller
A simplified version that directly uses the approach from our working test script.
"""

import logging
import time
import asyncio
import math
import json
import os
import sys
import warnings
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
import scd30_i2c
from utils.singleton import singleton
from devices.base import Device

# Add parent directory to path when running directly
if __name__ == "__main__":
    # Get the directory of this file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Get the parent directory (project root)
    parent_dir = os.path.dirname(current_dir)
    # Add to Python path
    sys.path.insert(0, parent_dir)
    
    # Suppress deprecation warnings when running directly
    warnings.filterwarnings("ignore", category=DeprecationWarning)

# Set up logging
logger = logging.getLogger('shroombox.sensor')

# Define the path to the measurements file
MEASUREMENTS_FILE = os.path.join('data', 'measurements.json')

@singleton
class SimpleSCD30Controller(Device):
    """
    Simplified controller for the SCD30 CO2, temperature, and humidity sensor.
    
    This class implements the Device interface and provides methods
    to read measurements from the SCD30 sensor using a simplified approach.
    """
    
    def __init__(self):
        """Initialize the simplified SCD30 controller."""
        logger.info("Initializing SimpleSCD30Controller")
        self.sensor = None
        self._last_measurement = None
        self._last_measurement_time = 0
        self._last_influxdb_log_time = 0
        self._initialized = False
        
        # Initialize settings manager first
        from managers.settings_manager import SettingsManager
        self.settings_manager = SettingsManager()
        
        # Default settings
        self._measurement_interval = 2  # Default to 2 seconds
        self._influxdb_logging_interval = 60  # Default to 60 seconds
        self._influxdb_logging_enabled = True  # Default to enabled
        
        # Initialize hardware
        self.initialize()
    
    async def load_settings(self):
        """Load all settings asynchronously."""
        try:
            settings = await self.settings_manager.load_settings()
            
            # Get measurement interval
            if 'sensor' in settings and 'measurement_interval' in settings['sensor']:
                self._measurement_interval = max(2, float(settings['sensor']['measurement_interval']))
                logger.info(f"Using measurement interval from settings: {self._measurement_interval}s")
            
            # Get InfluxDB logging interval
            if 'influxdb' in settings and 'logging_interval' in settings['influxdb']:
                self._influxdb_logging_interval = max(10, float(settings['influxdb']['logging_interval']))
                logger.info(f"Using InfluxDB logging interval from settings: {self._influxdb_logging_interval}s")
            
            # Get InfluxDB logging enabled setting
            if 'influxdb' in settings and 'enabled' in settings['influxdb']:
                self._influxdb_logging_enabled = settings['influxdb']['enabled']
                logger.info(f"InfluxDB logging {'enabled' if self._influxdb_logging_enabled else 'disabled'}")
            
        except Exception as e:
            logger.warning(f"Error loading settings: {e}")
    
    def initialize(self) -> bool:
        """
        Initialize the SCD30 sensor using the simplified approach.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        try:
            # Create a new sensor instance
            logger.info("Creating SCD30 instance")
            self.sensor = scd30_i2c.SCD30()
            
            # Always try to stop any existing measurements first
            # This is critical for handling cases where the sensor was left in measurement mode
            try:
                logger.info("Stopping any existing measurements (cleanup from previous runs)")
                self.sensor.stop_periodic_measurement()
                logger.info("Successfully stopped periodic measurement")
                # Wait for the sensor to reset - this is important!
                time.sleep(2)  # Increased wait time to 2 seconds for more reliable reset
            except Exception as e:
                logger.debug(f"Error stopping periodic measurement: {e}")
            
            # Start continuous measurement
            logger.info("Starting continuous measurement")
            result = self.sensor.start_periodic_measurement()
            
            if result:
                logger.info("SCD30 sensor initialized successfully")
                self._initialized = True
                return True
            else:
                # This is often not a critical error - the sensor might already be in measurement mode
                # Use debug level instead of warning to suppress the message in normal operation
                logger.debug("Failed to start periodic measurement - sensor may already be in measurement mode")
                
                # Instead of treating this as an error, let's check if the sensor is actually working
                logger.info("Checking if sensor is working despite initialization warning")
                
                # Wait a bit longer for the sensor to stabilize
                time.sleep(2)
                
                # Check if we can read data to confirm sensor is working
                for attempt in range(5):  # Try up to 5 times (increased from 3)
                    try:
                        # Wait between attempts
                        if attempt > 0:
                            time.sleep(1)
                        
                        logger.debug(f"Checking sensor readiness (attempt {attempt+1}/5)")
                        if self.sensor.get_data_ready():
                            measurement = self.sensor.read_measurement()
                            if measurement is not None:
                                co2, temp, rh = measurement
                                logger.info(f"Sensor is working despite initialization warning: CO2={co2:.1f}ppm, Temp={temp:.1f}°C, RH={rh:.1f}%")
                                self._initialized = True
                                self._last_measurement = (co2, temp, rh)
                                self._last_measurement_time = time.time()
                                return True
                        else:
                            logger.debug(f"Data not ready yet (attempt {attempt+1}/5)")
                    except Exception as e:
                        logger.debug(f"Error checking sensor after failed initialization (attempt {attempt+1}/5): {e}")
                
                # Last resort: try to force a reset by stopping and starting again
                try:
                    logger.info("Attempting to force sensor reset")
                    self.sensor.stop_periodic_measurement()
                    time.sleep(3)  # Longer wait time for reset
                    result = self.sensor.start_periodic_measurement()
                    if result:
                        logger.info("Sensor reset successful")
                        self._initialized = True
                        return True
                except Exception as e:
                    logger.error(f"Error during forced sensor reset: {e}")
                
                # If we can't confirm the sensor is working after multiple attempts, mark as not initialized
                logger.error("Could not confirm sensor is working after multiple attempts")
                self._initialized = False
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
        if self.sensor is None:
            return False
            
        try:
            return self.sensor.get_data_ready()
        except Exception as e:
            logger.error(f"Error checking if sensor is available: {e}")
            return False
    
    def set_measurement_interval(self, interval: int) -> bool:
        """
        Set the measurement interval in seconds.
        
        Args:
            interval: Measurement interval in seconds (2-1800)
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Ensure interval is within valid range
        interval = max(2, min(1800, interval))
        
        logger.info(f"Setting measurement interval to {interval}s")
        
        # Update the internal measurement interval
        self._measurement_interval = interval
        
        # No need to set it on the sensor directly as we handle the interval in get_measurements
        return True
    
    def set_influxdb_logging_interval(self, interval: int) -> bool:
        """
        Set the InfluxDB logging interval in seconds.
        
        Args:
            interval: InfluxDB logging interval in seconds (10-3600)
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Ensure interval is within valid range
        interval = max(10, min(3600, interval))
        
        logger.info(f"Setting InfluxDB logging interval to {interval}s")
        
        # Update the internal InfluxDB logging interval
        self._influxdb_logging_interval = interval
        
        return True
    
    def set_influxdb_logging_enabled(self, enabled: bool) -> bool:
        """
        Enable or disable InfluxDB logging.
        
        Args:
            enabled: True to enable InfluxDB logging, False to disable
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Setting InfluxDB logging enabled to {enabled}")
        
        # Update the internal InfluxDB logging enabled flag
        self._influxdb_logging_enabled = enabled
        
        return True
    
    @property
    def is_initialized(self) -> bool:
        """
        Check if the sensor is initialized.
        
        Returns:
            bool: True if the sensor is initialized, False otherwise
        """
        return self._initialized and self.sensor is not None
    
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
    
    def _log_measurements_to_influxdb(self, co2: float, temp: float, rh: float, timestamp: Optional[datetime] = None) -> bool:
        """
        Log measurements to InfluxDB.
        
        Args:
            co2: CO2 measurement in ppm
            temp: Temperature in Celsius
            rh: Relative humidity as percentage
            timestamp: Optional timestamp for the measurement. If None, uses current time.
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self._influxdb_logging_enabled:
            logger.debug("InfluxDB logging is disabled")
            return False
            
        # Check if enough time has passed since last InfluxDB log
        current_time = time.time()
        time_since_last_log = current_time - self._last_influxdb_log_time
        
        if time_since_last_log < self._influxdb_logging_interval:
            logger.debug(f"Not enough time has passed since last InfluxDB log (elapsed: {time_since_last_log:.1f}s, required: {self._influxdb_logging_interval}s)")
            return False
            
        try:
            # Import here to avoid circular imports
            try:
                from managers.influxdb_manager import influxdb_manager
            except ImportError as e:
                logger.warning(f"InfluxDB manager not available: {e}")
                return False
            
            # Log measurements to InfluxDB
            logger.info(f"Logging measurements to InfluxDB: CO2={co2:.1f}ppm, Temp={temp:.1f}°C, RH={rh:.1f}%")
            
            # Create data points
            data_points = [
                {
                    "measurement": "environment",
                    "tags": {
                        "source": "scd30",
                        "location": "shroombox"
                    },
                    "fields": {
                        "co2": float(co2),
                        "temperature": float(temp),
                        "humidity": float(rh)
                    },
                    "time": timestamp.isoformat() + "Z" if timestamp else datetime.utcnow().isoformat() + "Z"
                }
            ]
            
            # Write to InfluxDB
            success = influxdb_manager.write_points(data_points)
            
            if success:
                logger.debug("Successfully logged measurements to InfluxDB")
                self._last_influxdb_log_time = current_time
                return True
            else:
                logger.warning("Failed to log measurements to InfluxDB")
                return False
                
        except Exception as e:
            logger.error(f"Error logging measurements to InfluxDB: {e}")
            return False
    
    async def get_measurements(self) -> Optional[Tuple[float, float, float]]:
        """
        Get measurements from the sensor.
        
        Returns:
            Optional[Tuple[float, float, float]]: (CO2, temperature, humidity) or None if failed
        """
        # Check if sensor is initialized
        if self.sensor is None:
            logger.warning("Sensor not initialized, attempting to initialize...")
            if not self.initialize():
                logger.error("Failed to initialize sensor")
                return None
        
        # Check if enough time has passed since last measurement
        current_time = time.time()
        time_since_last = current_time - self._last_measurement_time
        
        if time_since_last < self._measurement_interval:
            # If we have a recent valid measurement, return it
            if self._last_measurement is not None:
                logger.debug(f"Using recent measurement (age: {time_since_last:.1f}s)")
                return self._last_measurement
            
            # Otherwise wait until measurement interval has passed
            wait_time = self._measurement_interval - time_since_last
            logger.debug(f"Waiting {wait_time:.1f}s for next measurement")
            await asyncio.sleep(wait_time)
        
        # Check if data is ready
        try:
            # Try up to 3 times to get data
            for attempt in range(3):
                try:
                    if self.sensor.get_data_ready():
                        logger.debug("Data is ready")
                        
                        # Read measurement
                        measurement = self.sensor.read_measurement()
                        if measurement is not None:
                            co2, temp, rh = measurement
                            
                            # Get timestamp immediately after reading measurement
                            measurement_time = datetime.utcnow()
                            
                            # Validate measurement
                            if self._validate_measurement(co2, temp, rh):
                                logger.info(f"Valid measurement: CO2={co2:.1f}ppm, Temp={temp:.1f}°C, RH={rh:.1f}%")
                                
                                # Update last measurement time and value
                                self._last_measurement_time = current_time
                                self._last_measurement = (co2, temp, rh)
                                
                                # Write measurements to file
                                self._write_measurements_to_file(co2, temp, rh, source='sensor')
                                
                                # Log measurements to InfluxDB if enabled and interval has passed
                                self._log_measurements_to_influxdb(co2, temp, rh, timestamp=measurement_time)
                                
                                return co2, temp, rh
                            else:
                                logger.warning(f"Invalid measurement: CO2={co2}, Temp={temp}, RH={rh}")
                        else:
                            logger.warning("Failed to read measurement")
                    else:
                        logger.debug(f"Data not ready yet (attempt {attempt+1}/3)")
                        await asyncio.sleep(0.5)  # Wait a bit before trying again
                except Exception as e:
                    logger.warning(f"Error reading measurement (attempt {attempt+1}/3): {e}")
                    await asyncio.sleep(0.5)  # Wait a bit before trying again
            
            # If we have a recent valid measurement, return it as fallback
            if self._last_measurement is not None:
                logger.debug("Using last known measurement as fallback")
                return self._last_measurement
                
            # If sensor is not initialized or not working properly, try to reinitialize
            if not self._initialized or not self.is_available():
                logger.warning("Sensor appears to be in a bad state, attempting to reinitialize...")
                self.initialize()
                
            # Otherwise return None
            logger.warning("No valid measurements available")
            return None
                
        except Exception as e:
            logger.error(f"Error reading measurement: {e}")
            return self._last_measurement
    
    def cleanup(self) -> None:
        """Clean up resources before shutdown."""
        if self.sensor is not None:
            try:
                logger.info("Cleaning up SCD30 sensor")
                # Try multiple times to ensure the sensor is stopped
                for attempt in range(3):
                    try:
                        result = self.sensor.stop_periodic_measurement()
                        if result:
                            logger.info(f"Successfully stopped periodic measurement (attempt {attempt+1})")
                            break
                        else:
                            logger.warning(f"Failed to stop periodic measurement (attempt {attempt+1})")
                            time.sleep(0.5)
                    except Exception as e:
                        logger.warning(f"Error stopping periodic measurement (attempt {attempt+1}): {e}")
                        time.sleep(0.5)
                
                # Clear the sensor reference
                self.sensor = None
                self._initialized = False
                logger.info("SCD30 sensor cleanup completed")
            except Exception as e:
                logger.error(f"Error cleaning up SCD30 sensor: {e}")
    
    @property
    def name(self) -> str:
        """
        Get the device name.
        
        Returns:
            str: The name of the device
        """
        return "Simple SCD30 CO2 Sensor" 

# Function to test the sensor
async def test_sensor(interval: int = None, count: int = 0, json_output: bool = False):
    """
    Test the sensor by reading measurements and printing them to the console.
    
    Args:
        interval: Measurement interval in seconds (minimum 2). If None, uses value from settings.json
        count: Number of measurements to take (0 for continuous)
        json_output: Whether to output in JSON format
    """
    # If interval is not specified, try to get it from settings.json
    if interval is None:
        try:
            # Find the settings.json file
            script_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(script_dir)  # Go up one level
            settings_path = os.path.join(parent_dir, 'config', 'settings.json')
            
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                    if 'sensor' in settings and 'measurement_interval' in settings['sensor']:
                        interval = settings['sensor']['measurement_interval']
                        print(f"Using measurement interval from settings.json: {interval}s")
        except Exception as e:
            print(f"Error reading settings.json: {e}")
        
        # Default to 2 seconds if settings.json doesn't exist or doesn't contain the interval
        if interval is None:
            interval = 2
            print(f"Using default measurement interval: {interval}s")
    
    # Create sensor instance
    sensor = None
    try:
        sensor = SimpleSCD30Controller()
        
        # Set measurement interval
        sensor.set_measurement_interval(interval)
        
        print(f"Reading measurements from {sensor.name} (interval: {interval}s)")
        print("Press Ctrl+C to stop")
        
        count_taken = 0
        while count == 0 or count_taken < count:
            try:
                # Get measurements
                measurements = await sensor.get_measurements()
                
                if measurements:
                    co2, temp, rh = measurements
                    
                    # Output in requested format
                    if json_output:
                        import json
                        data = {
                            'co2': round(co2, 1),
                            'temperature': round(temp, 1),
                            'humidity': round(rh, 1),
                            'timestamp': datetime.now().isoformat()
                        }
                        print(json.dumps(data))
                    else:
                        print(f"CO2: {co2:.1f} ppm, Temperature: {temp:.1f}°C, Humidity: {rh:.1f}%")
                    
                    count_taken += 1
                else:
                    print("Failed to get measurements")
                
                # Wait for next measurement
                if count == 0 or count_taken < count:
                    await asyncio.sleep(interval)
            except asyncio.CancelledError:
                # This is raised when the task is cancelled (e.g., by KeyboardInterrupt)
                break
    except KeyboardInterrupt:
        print("\nStopped by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Clean up
        if sensor:
            try:
                sensor.cleanup()
                print("Sensor cleaned up")
            except Exception as e:
                print(f"Error during cleanup: {e}")