import logging
import time
import asyncio
import math
from typing import Optional, Tuple
from datetime import datetime
import scd30_i2c
import logging_setup

# Set up logging
logger = logging_setup.get_logger('shroombox.sensor')

class SCD30Controller:
    def __init__(self, measurement_interval: int = 5):
        """Initialize SCD30 controller.
        
        Args:
            measurement_interval: Time between measurements in seconds (minimum 2)
        """
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
        self.initialize_sensor()

    def initialize_sensor(self) -> bool:
        """Initialize the SCD30 sensor with error handling."""
        try:
            self._initialization_attempts += 1
            logger.info(f"Initializing SCD30 sensor (attempt {self._initialization_attempts}/{self._max_initialization_attempts})...")
            
            # If we've tried too many times, wait longer between attempts
            if self._initialization_attempts > 2:
                logger.info(f"Multiple initialization attempts, waiting 5 seconds before trying again...")
                time.sleep(5)
            
            # Create a new sensor instance
            self.sensor = scd30_i2c.SCD30()
            
            # Stop any existing measurements
            try:
                self.sensor.stop_periodic_measurement()
                time.sleep(0.5)  # Wait for the command to take effect
            except Exception as e:
                logger.debug(f"Error stopping existing measurements (this is normal for first init): {e}")
            
            # Set measurement interval
            self.sensor.set_measurement_interval(self.measurement_interval)
            time.sleep(0.1)  # Wait for the command to take effect
            
            # Verify the measurement interval was set correctly
            actual_interval = self.sensor.get_measurement_interval()
            if actual_interval != self.measurement_interval:
                logger.warning(f"Measurement interval mismatch: requested {self.measurement_interval}s, got {actual_interval}s")
                # Try to set it again
                self.sensor.set_measurement_interval(self.measurement_interval)
                time.sleep(0.1)
            
            # Start periodic measurement
            self.sensor.start_periodic_measurement()
            
            # Wait for the sensor to start up
            time.sleep(1.0)  # Increased from 0.5 to 1.0 seconds
            
            # Check if automatic self-calibration is enabled
            try:
                asc_enabled = self.sensor.get_auto_self_calibration_active()
                logger.info(f"Automatic self-calibration is {'enabled' if asc_enabled else 'disabled'}")
            except Exception as e:
                logger.warning(f"Could not check ASC status: {e}")
            
            # Record initialization time
            self._initialization_time = time.time()
            self._initialized = True
            logger.info("SCD30 sensor initialized successfully")
            
            # Reset initialization attempts counter on success
            self._initialization_attempts = 0
            
            return True
        except Exception as e:
            logger.error(f"Failed to initialize SCD30 sensor: {e}")
            self.sensor = None
            self._initialized = False
            
            # If we've tried too many times, give up
            if self._initialization_attempts >= self._max_initialization_attempts:
                logger.error(f"Failed to initialize sensor after {self._max_initialization_attempts} attempts, giving up")
                self._initialization_attempts = 0  # Reset for next time
            
            return False

    def is_available(self) -> bool:
        """Check if the sensor is available and working."""
        if not self.sensor:
            return False
            
        try:
            # Check if the sensor is ready for reading
            return self.sensor.get_data_ready()
        except Exception as e:
            logger.error(f"Error checking sensor availability: {e}")
            return False
            
    def is_warmed_up(self) -> bool:
        """Check if the sensor has completed its warmup period."""
        if not self._initialized or self._initialization_time == 0:
            return False
            
        current_time = time.time()
        time_since_init = current_time - self._initialization_time
        
        return time_since_init >= self._warmup_period

    def _validate_measurement(self, co2: float, temp: float, rh: float) -> bool:
        """Validate measurement values are within reasonable ranges."""
        # Check for NaN or None values
        if any(x is None for x in [co2, temp, rh]):
            logger.warning("Measurement contains None values")
            return False
            
        # Check for NaN values
        if math.isnan(co2) or math.isnan(temp) or math.isnan(rh):
            logger.warning(f"Measurement contains NaN values: CO2={co2}, Temp={temp}, RH={rh}")
            return False
            
        # Check for reasonable ranges
        if not (300 <= co2 <= 10000):  # CO2 range: 300-10000 ppm
            logger.warning(f"CO2 reading out of range: {co2} ppm")
            return False
            
        if not (-10 <= temp <= 60):  # Temperature range: -10 to 60°C
            logger.warning(f"Temperature reading out of range: {temp}°C")
            return False
            
        if not (0 <= rh <= 100):  # Humidity range: 0-100%
            logger.warning(f"Humidity reading out of range: {rh}%")
            return False
            
        return True

    async def get_measurements(self) -> Optional[Tuple[float, float, float]]:
        """Get current CO2, temperature and humidity measurements.
        
        Returns:
            Tuple of (co2, temperature, humidity) or None if reading fails
        """
        if not self.sensor:
            logger.warning("No sensor initialized")
            return None
        
        # Check if sensor is still in warmup period
        if not self.is_warmed_up():
            time_since_init = time.time() - self._initialization_time
            remaining_warmup = max(0, self._warmup_period - time_since_init)
            logger.info(f"Sensor still in warmup period, {remaining_warmup:.1f}s remaining")
            
            # If we have a previous valid measurement, return it during warmup
            if self._last_valid_measurement:
                logger.info("Using last valid measurement during warmup period")
                return self._last_valid_measurement
                
            # Otherwise wait for the warmup to complete
            if remaining_warmup > 0:
                logger.info(f"Waiting {remaining_warmup:.1f}s for sensor warmup to complete")
                await asyncio.sleep(remaining_warmup)
        
        try:
            # First check when was the last measurement taken
            current_time = time.time()
            if self._last_measurement_time:
                time_since_last = current_time - self._last_measurement_time
                if time_since_last < self.measurement_interval:
                    # Wait until the measurement interval has passed
                    wait_time = self.measurement_interval - time_since_last
                    logger.debug(f"Waiting {wait_time:.1f}s for next measurement interval")
                    await asyncio.sleep(wait_time)
            
            # Wait for data to be ready with polling
            wait_start = time.time()
            max_wait = 10  # Increased maximum wait time from 5 to 10 seconds
            max_attempts = 5  # Maximum number of measurement attempts
            attempt = 0
            
            while time.time() - wait_start < max_wait and attempt < max_attempts:
                attempt += 1
                
                # Check if data is ready
                data_ready = False
                try:
                    data_ready = self.is_available()
                except Exception as e:
                    logger.warning(f"Error checking if data is ready (attempt {attempt}): {e}")
                    await asyncio.sleep(1)  # Wait a bit longer after an error
                    continue
                
                if not data_ready:
                    logger.debug(f"Data not ready yet (attempt {attempt}/{max_attempts})")
                    await asyncio.sleep(0.5)  # Increased from 0.1 to 0.5 seconds
                    continue
                
                # Data is ready, try to read it
                try:
                    logger.debug(f"Reading measurement (attempt {attempt}/{max_attempts})")
                    measurement = self.sensor.read_measurement()
                    
                    if measurement is None:
                        logger.warning(f"Sensor returned None measurement (attempt {attempt}/{max_attempts})")
                        self._consecutive_failures += 1
                        await asyncio.sleep(1)  # Wait a bit longer after a None measurement
                        continue
                    
                    co2, temp, rh = measurement
                    
                    # Check for NaN values before rounding
                    if (math.isnan(co2) or math.isnan(temp) or math.isnan(rh)):
                        logger.warning(f"Raw measurement contains NaN values (attempt {attempt}/{max_attempts}): CO2={co2}, Temp={temp}, RH={rh}")
                        self._consecutive_failures += 1
                        # Skip this measurement and wait for the next one
                        await asyncio.sleep(1)
                        continue
                    
                    # Round values for display
                    co2 = round(co2, 2)
                    temp = round(temp, 2)
                    rh = round(rh, 2)
                    
                    # Validate the measurement
                    if self._validate_measurement(co2, temp, rh):
                        # Store the measurement time
                        self._last_measurement_time = time.time()
                        self._last_valid_measurement = (co2, temp, rh)
                        self._consecutive_failures = 0
                        
                        # More detailed logging
                        logger.info(f"Successful measurement at {datetime.now().strftime('%H:%M:%S')} - "
                                  f"CO2: {co2}ppm, Temp: {temp}°C, RH: {rh}%")
                        
                        return co2, temp, rh
                    else:
                        logger.warning(f"Invalid measurement values (attempt {attempt}/{max_attempts}): CO2={co2}, Temp={temp}, RH={rh}")
                        self._consecutive_failures += 1
                        # Skip this measurement and wait for the next one
                        await asyncio.sleep(1)
                        continue
                        
                except Exception as e:
                    logger.warning(f"Error reading measurement (attempt {attempt}/{max_attempts}): {e}")
                    self._consecutive_failures += 1
                    await asyncio.sleep(1)  # Wait a bit longer after an error
                    continue
            
            # If we get here, we couldn't get a valid measurement
            if attempt >= max_attempts:
                logger.warning(f"Failed to get valid measurement after {max_attempts} attempts")
            else:
                logger.warning(f"Sensor data not ready within timeout period ({max_wait}s)")
            
            self._consecutive_failures += 1
            
            # If we have too many consecutive failures, try to reinitialize the sensor
            if self._consecutive_failures >= self._max_consecutive_failures:
                logger.warning(f"Too many consecutive failures ({self._consecutive_failures}), reinitializing sensor")
                self.cleanup()
                await asyncio.sleep(1)
                self.initialize_sensor()
                self._consecutive_failures = 0
                
                # Wait for the sensor to be ready after reinitialization
                await asyncio.sleep(2)
            
            # Return last valid measurement as fallback if available
            if self._last_valid_measurement:
                logger.info("Returning last valid measurement as fallback")
                return self._last_valid_measurement
                
            return None
            
        except Exception as e:
            logger.error(f"Error reading measurements: {e}")
            self._consecutive_failures += 1
            
            # Return last valid measurement as fallback if available
            if self._last_valid_measurement:
                logger.info("Returning last valid measurement as fallback after error")
                return self._last_valid_measurement
                
            return None

    def set_measurement_interval(self, interval: int) -> bool:
        """Set the measurement interval in seconds."""
        try:
            interval = max(2, interval)  # Ensure minimum 2 seconds
            
            # Only update if different from current interval
            if interval != self.measurement_interval:
                if self.sensor:
                    logger.info(f"Changing measurement interval from {self.measurement_interval}s to {interval}s")
                    self.sensor.set_measurement_interval(interval)
                    self.measurement_interval = interval
                    
                    # Verify the interval was set correctly
                    actual_interval = self.sensor.get_measurement_interval()
                    if actual_interval != interval:
                        logger.warning(f"Measurement interval mismatch: requested {interval}s, got {actual_interval}s")
                        # Try again
                        self.sensor.set_measurement_interval(interval)
                    
                    return True
                else:
                    logger.warning("Cannot set measurement interval: sensor not initialized")
            return False
        except Exception as e:
            logger.error(f"Error setting measurement interval: {e}")
            return False

    def cleanup(self):
        """Clean up sensor resources."""
        logger.info("Cleaning up SCD30 sensor resources")
        if self.sensor:
            try:
                # Stop periodic measurement
                self.sensor.stop_periodic_measurement()
            except Exception as e:
                logger.debug(f"Error stopping measurements during cleanup: {e}")
        self.sensor = None
        self._initialized = False

# Test function to run when this file is executed directly
async def test_scd30_sensor():
    """Test function to verify SCD30 sensor functionality."""
    print("Testing SCD30 sensor...")
    controller = SCD30Controller()
    
    # Give the sensor time to initialize and collect data
    print("Waiting for sensor to be ready...")
    await asyncio.sleep(2)
    
    # Try to get measurements
    for i in range(5):  # Try 5 times
        print(f"Attempt {i+1} to read measurements...")
        measurements = await controller.get_measurements()
        
        if measurements:
            co2, temp, rh = measurements
            print(f"CO2: {co2} ppm")
            print(f"Temperature: {temp} °C")
            print(f"Relative Humidity: {rh}%")
            break
        else:
            print("Failed to get measurements, trying again...")
            await asyncio.sleep(2)
    else:
        print("Could not get measurements after multiple attempts")
    
    # Clean up
    controller.cleanup()
    print("Test completed")

# Run the test function when this file is executed directly
if __name__ == "__main__":
    asyncio.run(test_scd30_sensor()) 