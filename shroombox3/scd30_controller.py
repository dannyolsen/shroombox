import logging
import time
import asyncio
from typing import Optional, Tuple
from datetime import datetime
import scd30_i2c
import logging_setup

# Set up logging
logger = logging_setup.get_logger('shroombox.sensor')

class SCD30Controller:
    def __init__(self, measurement_interval: int = 5, max_retries: int = 3):
        """Initialize SCD30 controller.
        
        Args:
            measurement_interval: Time between measurements in seconds (minimum 2)
            max_retries: Maximum number of retries for operations
        """
        self.sensor = None
        self.measurement_interval = max(2, measurement_interval)  # Ensure minimum 2 seconds
        self._last_measurement_time = 0
        self._last_data_ready_check = 0
        self._data_ready_check_interval = 0.5  # Check data readiness every 0.5 seconds
        self.max_retries = max_retries
        self._last_successful_measurement = None  # Store last successful measurement
        self._consecutive_failures = 0  # Track consecutive failures
        self._using_fallback = False  # Flag to indicate if using fallback
        self.initialize_sensor()

    def initialize_sensor(self) -> bool:
        """Initialize the SCD30 sensor with error handling."""
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Initializing SCD30 sensor (attempt {attempt}/{self.max_retries})...")
                self.sensor = scd30_i2c.SCD30()
                # Using default address (0x61)
                
                # Set measurement interval
                self.sensor.set_measurement_interval(self.measurement_interval)
                logger.info(f"Set measurement interval to {self.measurement_interval} seconds")
                
                # Start periodic measurement
                self.sensor.start_periodic_measurement()
                logger.info("Started periodic measurement")
                
                # Wait for the first measurement to be ready
                logger.info(f"Waiting for first measurement (up to {self.measurement_interval * 2} seconds)...")
                start_time = time.time()
                while time.time() - start_time < self.measurement_interval * 2:
                    if self._check_data_ready():
                        logger.info("First measurement is ready")
                        return True
                    time.sleep(0.5)
                
                if attempt == self.max_retries:
                    logger.warning("Timed out waiting for first measurement, but continuing anyway")
                    return True
                    
                logger.warning("Timed out waiting for first measurement")
                
            except Exception as e:
                logger.error(f"Failed to initialize SCD30 sensor (attempt {attempt}): {e}")
                if attempt < self.max_retries:
                    logger.info(f"Retrying in 1 second...")
                    time.sleep(1)
                else:
                    self.sensor = None
        
        return False

    def _check_data_ready(self) -> bool:
        """Check if data is ready, respecting the sensor's timing requirements."""
        if self.sensor is None:
            return False
            
        # Limit how often we check data readiness to avoid overwhelming the sensor
        current_time = time.time()
        if current_time - self._last_data_ready_check < self._data_ready_check_interval:
            return False
            
        self._last_data_ready_check = current_time
        
        try:
            return bool(self.sensor.get_data_ready())
        except Exception as e:
            logger.error(f"Error checking if data is ready: {e}")
            return False

    def is_available(self) -> bool:
        """Check if the sensor is available and working."""
        if self.sensor is None:
            return False
            
        for attempt in range(1, self.max_retries + 1):
            try:
                # Just check if we can communicate with the sensor
                # Don't use get_data_ready here to avoid overwhelming the sensor
                self.sensor.get_firmware_version()
                return True
            except Exception as e:
                if attempt == 1:  # Only log on first attempt to reduce noise
                    logger.error(f"Error checking sensor availability: {e}")
                if attempt < self.max_retries:
                    time.sleep(0.1)  # Short delay between retries
        
        return False

    async def get_measurements(self) -> Optional[Tuple[float, float, float]]:
        """Get current CO2, temperature and humidity measurements.
        
        Returns:
            Tuple of (co2, temperature, humidity) or None if reading fails
        """
        # First try to get new measurements
        measurement = await self._try_get_measurements()
        
        # If successful, update last successful measurement and return
        if measurement is not None:
            self._last_successful_measurement = measurement
            self._consecutive_failures = 0
            self._using_fallback = False
            return measurement
            
        # If we have a previous successful measurement, return that with a warning
        if self._last_successful_measurement is not None:
            self._consecutive_failures += 1
            
            # Only log warning every 5 failures to reduce noise
            if self._consecutive_failures % 5 == 1:
                logger.warning(f"Using last successful measurement as fallback (failure #{self._consecutive_failures})")
            
            self._using_fallback = True
            return self._last_successful_measurement
            
        # No current or previous measurement available
        self._consecutive_failures += 1
        return None
        
    async def _try_get_measurements(self) -> Optional[Tuple[float, float, float]]:
        """Internal method to try getting measurements with retries."""
        if not self.is_available():
            # Try to reinitialize if sensor is not available
            if self.sensor is None:
                logger.info("Sensor not initialized. Attempting to initialize...")
                self.initialize_sensor()
                if not self.is_available():
                    logger.warning("Warning: No sensor available after reinitialization")
                    return None
            else:
                logger.warning("Warning: No sensor available")
                return None
        
        try:
            # First check when was the last measurement taken
            current_time = time.time()
            if self._last_measurement_time:
                time_since_last = current_time - self._last_measurement_time
                if time_since_last < self.measurement_interval:
                    # Not enough time has passed since the last measurement
                    # Wait until the measurement interval has passed
                    wait_time = self.measurement_interval - time_since_last
                    logger.debug(f"Waiting {wait_time:.1f}s for next measurement interval")
                    await asyncio.sleep(wait_time)
            
            # Wait for data to be ready with polling (respecting the sensor's timing)
            wait_start = time.time()
            max_wait = self.measurement_interval * 2  # Maximum time to wait for data
            
            while time.time() - wait_start < max_wait:
                if self._check_data_ready():
                    # Data is ready, read the measurement
                    for read_attempt in range(1, self.max_retries + 1):
                        try:
                            measurement = self.sensor.read_measurement()
                            if measurement is not None:
                                co2, temp, rh = measurement
                                co2 = round(co2, 2)
                                temp = round(temp, 2)
                                rh = round(rh, 2)
                                
                                # Store the measurement time
                                self._last_measurement_time = time.time()
                                
                                # More detailed logging
                                logger.info(f"Successful measurement at {datetime.now().strftime('%H:%M:%S')} - "
                                          f"CO2: {co2}ppm, Temp: {temp}°C, RH: {rh}%")
                                
                                return co2, temp, rh
                            else:
                                if read_attempt < self.max_retries:
                                    logger.warning(f"Measurement returned None (attempt {read_attempt}). Retrying...")
                                    time.sleep(0.5)  # Longer delay between read attempts
                        except Exception as e:
                            if read_attempt < self.max_retries:
                                logger.error(f"Error reading measurement (attempt {read_attempt}): {e}")
                                time.sleep(0.5)  # Longer delay between read attempts
                    
                    # If we get here, all read attempts failed
                    break
                
                # Data not ready yet, wait before checking again
                # Use a longer sleep to avoid overwhelming the sensor
                await asyncio.sleep(0.5)
            
            logger.warning("Sensor data not ready within timeout period")
            return None
            
        except Exception as e:
            logger.error(f"Error reading measurements: {e}")
            return None

    def set_measurement_interval(self, interval: int) -> bool:
        """Set the measurement interval in seconds."""
        try:
            interval = max(2, interval)  # Ensure minimum 2 seconds
            if self.sensor:
                self.sensor.set_measurement_interval(interval)
                self.measurement_interval = interval
                return True
            return False
        except Exception as e:
            logger.error(f"Error setting measurement interval: {e}")
            return False

    def cleanup(self):
        """Clean up sensor resources."""
        self.sensor = None 

if __name__ == "__main__":
    import time
    import signal
    import sys
    
    def signal_handler(sig, frame):
        print("\nExiting test. Cleaning up...")
        if controller:
            controller.cleanup()
        sys.exit(0)
    
    # Register the signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    print("Starting SCD30 sensor test. Press Ctrl+C to exit.")
    
    # Create and initialize the sensor controller with more retries
    controller = SCD30Controller(measurement_interval=2, max_retries=3)
    
    # Check if sensor is available
    if not controller.is_available():
        print("Warning: SCD30 sensor not immediately available. Will keep trying...")
    else:
        print(f"SCD30 sensor initialized with measurement interval of {controller.measurement_interval} seconds.")
    
    print("Taking continuous measurements. Press Ctrl+C to exit.")
    print("Time\t\tStatus\t\tCO2 (ppm)\tTemperature (°C)\tHumidity (%)")
    print("-" * 90)
    
    # Create event loop for async operations
    loop = asyncio.get_event_loop()
    
    try:
        while True:
            # Get measurements
            measurement = loop.run_until_complete(controller.get_measurements())
            
            if measurement:
                co2, temp, humidity = measurement
                current_time = datetime.now().strftime("%H:%M:%S")
                
                # Add status indicator
                status = "FALLBACK" if controller._using_fallback else "LIVE"
                
                print(f"{current_time}\t{status}\t\t{co2:.2f}\t\t{temp:.2f}\t\t\t{humidity:.2f}")
            else:
                print(f"{datetime.now().strftime('%H:%M:%S')}\tFAILED\t\tNo measurement available")
            
            # Small delay to prevent excessive CPU usage
            time.sleep(0.5)  # Longer delay to reduce sensor queries
    
    except Exception as e:
        print(f"Error during test: {e}")
    finally:
        controller.cleanup()
        print("Test completed and resources cleaned up.") 