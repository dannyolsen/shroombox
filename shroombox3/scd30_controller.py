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
    def __init__(self, measurement_interval: int = 5):
        """Initialize SCD30 controller.
        
        Args:
            measurement_interval: Time between measurements in seconds (minimum 2)
        """
        self.sensor = None
        self.measurement_interval = max(2, measurement_interval)  # Ensure minimum 2 seconds
        self._last_measurement_time = 0
        self.initialize_sensor()

    def initialize_sensor(self) -> bool:
        """Initialize the SCD30 sensor with error handling."""
        try:
            logger.info("Initializing SCD30 sensor...")
            self.sensor = scd30_i2c.SCD30()
            self.sensor.set_measurement_interval(self.measurement_interval)
            self.sensor.start_periodic_measurement()
            logger.info("SCD30 sensor initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize SCD30 sensor: {e}")
            self.sensor = None
            return False

    def is_available(self) -> bool:
        """Check if the sensor is available and working."""
        try:
            return self.sensor is not None and self.sensor.get_data_ready()
        except Exception as e:
            logger.error(f"Error checking sensor availability: {e}")
            return False

    async def get_measurements(self) -> Optional[Tuple[float, float, float]]:
        """Get current CO2, temperature and humidity measurements.
        
        Returns:
            Tuple of (co2, temperature, humidity) or None if reading fails
        """
        if not self.is_available():
            logger.warning("Warning: No sensor available")
            return None
        
        try:
            # First check when was the last measurement taken
            current_time = time.time()
            if self._last_measurement_time:
                time_since_last = current_time - self._last_measurement_time
                if time_since_last < self.measurement_interval:
                    await asyncio.sleep(self.measurement_interval - time_since_last)
            
            # Wait for data to be ready with polling
            wait_start = time.time()
            max_wait = 5  # Maximum time to wait for data
            
            while time.time() - wait_start < max_wait:
                if self.sensor.get_data_ready():
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
                await asyncio.sleep(0.1)  # Short sleep between checks
            
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