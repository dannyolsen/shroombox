#!/usr/bin/env python3
"""
Script to periodically update the measurements file with the latest sensor readings.
This can be run as a separate process to ensure measurements are always up-to-date.
It also logs measurements to InfluxDB at configurable intervals.
"""

import os
import sys
import time
import json
import signal
import asyncio
import logging
from datetime import datetime

# Add parent directory to Python path so we can import from root
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Import from project
from managers.device_manager import DeviceManager
from managers.settings_manager import SettingsManager
from managers.influxdb_manager import influxdb_manager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('measurements_updater')

# Path to the measurements file
MEASUREMENTS_FILE = os.path.join(parent_dir, 'data', 'measurements.json')
# Path to the settings file
SETTINGS_FILE = os.path.join(parent_dir, 'config', 'settings.json')

# Default measurement interval in seconds (if not specified in settings)
DEFAULT_MEASUREMENT_INTERVAL = 10
# Default InfluxDB logging interval in seconds (if not specified in settings)
DEFAULT_INFLUXDB_INTERVAL = 60

# Ensure data directory exists
os.makedirs(os.path.dirname(MEASUREMENTS_FILE), exist_ok=True)

# Global variables for cleanup
device_manager = None
settings_manager = None
shutdown_event = None
last_influxdb_log_time = 0

async def get_measurement_interval():
    """Get the measurement interval from settings.json."""
    global settings_manager
    
    try:
        if settings_manager is None:
            settings_manager = SettingsManager(SETTINGS_FILE)
        
        settings = await settings_manager.load_settings()
        
        # Get the measurement interval from settings
        if 'sensor' in settings and 'measurement_interval' in settings['sensor']:
            interval = settings['sensor']['measurement_interval']
            # Ensure the interval is at least 2 seconds (SCD30 minimum)
            interval = max(2, int(interval))
            logger.debug(f"Using measurement interval from settings: {interval}s")
            return interval
        else:
            logger.debug(f"No measurement interval found in settings, using default: {DEFAULT_MEASUREMENT_INTERVAL}s")
            return DEFAULT_MEASUREMENT_INTERVAL
    except Exception as e:
        logger.error(f"Error reading measurement interval from settings: {e}")
        return DEFAULT_MEASUREMENT_INTERVAL

async def get_influxdb_logging_interval():
    """Get the InfluxDB logging interval from settings.json."""
    global settings_manager
    
    try:
        if settings_manager is None:
            settings_manager = SettingsManager(SETTINGS_FILE)
        
        settings = await settings_manager.load_settings()
        
        # Get the InfluxDB logging interval from settings
        if 'sensor' in settings and 'influxdb_logging_interval' in settings['sensor']:
            interval = settings['sensor']['influxdb_logging_interval']
            # Ensure the interval is at least 10 seconds
            interval = max(10, int(interval))
            logger.debug(f"Using InfluxDB logging interval from settings: {interval}s")
            return interval
        else:
            logger.debug(f"No InfluxDB logging interval found in settings, using default: {DEFAULT_INFLUXDB_INTERVAL}s")
            return DEFAULT_INFLUXDB_INTERVAL
    except Exception as e:
        logger.error(f"Error reading InfluxDB logging interval from settings: {e}")
        return DEFAULT_INFLUXDB_INTERVAL

async def is_influxdb_logging_enabled():
    """Check if InfluxDB logging is enabled in settings.json."""
    global settings_manager
    
    try:
        if settings_manager is None:
            settings_manager = SettingsManager(SETTINGS_FILE)
        
        settings = await settings_manager.load_settings()
        
        # Check if InfluxDB logging is enabled
        if 'sensor' in settings and 'influxdb_logging_enabled' in settings['sensor']:
            enabled = settings['sensor']['influxdb_logging_enabled']
            logger.debug(f"InfluxDB logging enabled: {enabled}")
            return enabled
        else:
            logger.debug("InfluxDB logging enabled setting not found, using default: True")
            return True
    except Exception as e:
        logger.error(f"Error reading InfluxDB logging enabled setting: {e}")
        return True

async def log_to_influxdb(co2, temp, rh):
    """Log measurements to InfluxDB."""
    global last_influxdb_log_time
    
    try:
        # Check if InfluxDB logging is enabled
        enabled = await is_influxdb_logging_enabled()
        if not enabled:
            logger.debug("InfluxDB logging is disabled")
            return False
        
        # Get the InfluxDB logging interval
        interval = await get_influxdb_logging_interval()
        
        # Check if enough time has passed since last log
        current_time = time.time()
        time_since_last = current_time - last_influxdb_log_time
        
        if time_since_last < interval:
            logger.debug(f"Not enough time has passed since last InfluxDB log (elapsed: {time_since_last:.1f}s, required: {interval}s)")
            return False
        
        # Log to InfluxDB
        logger.info(f"Logging to InfluxDB: CO2={co2:.1f}ppm, Temp={temp:.1f}°C, RH={rh:.1f}%")
        
        # Get fan speed from device manager
        fan_speed = device_manager.get_fan_speed() if hasattr(device_manager, 'get_fan_speed') else 0
        
        # Get device states from settings
        heater_state = False
        humidifier_state = False
        
        try:
            settings = await settings_manager.load_settings()
            available_devices = settings.get('available_devices', [])
            
            for device in available_devices:
                if device.get('role') == 'heater':
                    heater_state = device.get('state', False)
                elif device.get('role') == 'humidifier':
                    humidifier_state = device.get('state', False)
        except Exception as e:
            logger.warning(f"Error getting device states from settings: {e}")
        
        # Log to InfluxDB
        success = await influxdb_manager.write_measurement(
            co2=co2,
            temp=temp,
            rh=rh,
            fan_speed=fan_speed,
            heater_state=heater_state,
            humidifier_state=humidifier_state
        )
        
        if success:
            logger.debug("Successfully logged to InfluxDB")
            last_influxdb_log_time = current_time
            return True
        else:
            logger.warning("Failed to log to InfluxDB")
            return False
    except Exception as e:
        logger.error(f"Error logging to InfluxDB: {e}")
        return False

async def update_measurements():
    """Update the measurements file with the latest sensor readings."""
    global device_manager, shutdown_event, settings_manager
    
    # Get the DeviceManager instance (it's a singleton)
    device_manager = DeviceManager()
    logger.info("Using DeviceManager to access sensor")
    
    # Initialize settings manager if not already done
    if settings_manager is None:
        settings_manager = SettingsManager(SETTINGS_FILE)
    
    # Get the measurement interval from settings
    measurement_interval = await get_measurement_interval()
    logger.info(f"Measurement interval set to {measurement_interval} seconds")
    
    # Set the measurement interval on the sensor
    if hasattr(device_manager.sensor, 'set_measurement_interval'):
        device_manager.sensor.set_measurement_interval(measurement_interval)
    
    # Track consecutive failures
    consecutive_failures = 0
    max_consecutive_failures = 5
    
    # Main loop
    while not shutdown_event.is_set():
        try:
            # Check if the measurement interval has changed
            new_interval = await get_measurement_interval()
            if new_interval != measurement_interval:
                logger.info(f"Measurement interval changed from {measurement_interval}s to {new_interval}s")
                measurement_interval = new_interval
                # Update the sensor's measurement interval
                if hasattr(device_manager.sensor, 'set_measurement_interval'):
                    device_manager.sensor.set_measurement_interval(measurement_interval)
            
            # Get measurements using DeviceManager
            logger.info("Attempting to read measurements...")
            
            # Get fresh measurements
            measurements = await device_manager.get_measurements()
            
            # Get fan speed from device manager
            fan_speed = device_manager.get_fan_speed()
            fan_speed_rounded = round(fan_speed, 1)
            
            if measurements:
                co2, temp, rh = measurements
                logger.info(f"Valid measurement: CO2={co2:.1f}ppm, Temp={temp:.1f}°C, RH={rh:.1f}%, Fan={fan_speed_rounded}%")
                
                # Round values for display
                co2_rounded = round(co2)
                temp_rounded = round(temp, 1)
                rh_rounded = round(rh, 1)
                
                # Prepare data
                data = {
                    'co2': co2_rounded,
                    'temperature': temp_rounded,
                    'humidity': rh_rounded,
                    'fan_speed': fan_speed_rounded,
                    'source': 'sensor',
                    'timestamp': datetime.now().isoformat(),
                    'unix_timestamp': time.time()
                }
                
                # Write to file (using atomic write pattern)
                temp_file = f"{MEASUREMENTS_FILE}.tmp"
                with open(temp_file, 'w') as f:
                    json.dump(data, f, indent=2)
                os.replace(temp_file, MEASUREMENTS_FILE)
                
                logger.info(f"Updated measurements: CO2={co2_rounded}ppm, Temp={temp_rounded}°C, RH={rh_rounded}%, Fan={fan_speed_rounded}%")
                
                # Log to InfluxDB
                await log_to_influxdb(co2, temp, rh)
                
                # Reset failure counter on success
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                logger.warning(f"Failed to get measurements (failure {consecutive_failures}/{max_consecutive_failures})")
                
                # If we've had too many consecutive failures, try to get cached measurements
                if consecutive_failures >= max_consecutive_failures:
                    logger.warning("Too many consecutive failures, checking cached measurements")
                    cached = await device_manager.get_cached_measurements()
                    
                    if cached['co2'] is not None and cached['temperature'] is not None and cached['humidity'] is not None:
                        logger.info(f"Using cached measurements: CO2={cached['co2']}ppm, Temp={cached['temperature']}°C, RH={cached['humidity']}%, Fan={fan_speed_rounded}%")
                        
                        # Prepare data from cache
                        data = {
                            'co2': cached['co2'],
                            'temperature': cached['temperature'],
                            'humidity': cached['humidity'],
                            'fan_speed': fan_speed_rounded,
                            'source': 'cache',
                            'timestamp': datetime.now().isoformat(),
                            'unix_timestamp': time.time(),
                            'cache_age': cached['age'] if cached['age'] is not None else 'unknown'
                        }
                        
                        # Write to file (using atomic write pattern)
                        temp_file = f"{MEASUREMENTS_FILE}.tmp"
                        with open(temp_file, 'w') as f:
                            json.dump(data, f, indent=2)
                        os.replace(temp_file, MEASUREMENTS_FILE)
                        
                        logger.info(f"Updated measurements from cache")
                    else:
                        logger.error("No valid cached measurements available")
                
            # Wait for next update (using the configured interval)
            logger.debug(f"Waiting {measurement_interval} seconds before next measurement...")
            try:
                # Use wait_for with timeout to allow for clean shutdown
                await asyncio.wait_for(shutdown_event.wait(), timeout=measurement_interval)
                if shutdown_event.is_set():
                    logger.info("Shutdown event detected, exiting measurement loop")
                    break
            except asyncio.TimeoutError:
                # This is expected - it means the timeout was reached without the event being set
                pass
            
        except Exception as e:
            logger.error(f"Error updating measurements: {e}", exc_info=True)
            await asyncio.sleep(5)  # Wait before retrying

def cleanup():
    """Clean up resources before shutdown."""
    global device_manager
    
    logger.info("Performing cleanup before shutdown")
    
    if device_manager is not None:
        try:
            # Call the DeviceManager's cleanup method
            device_manager.cleanup()
            logger.info("Device cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def signal_handler(sig, frame):
    """Handle termination signals to ensure proper cleanup."""
    logger.info(f"Received signal {sig}, initiating shutdown")
    
    # Set the shutdown event
    if shutdown_event is not None:
        shutdown_event.set()
    else:
        # If we're not in the async context yet, just exit
        cleanup()
        sys.exit(0)

async def main():
    """Main function."""
    global shutdown_event
    
    # Create shutdown event
    shutdown_event = asyncio.Event()
    
    # Register signal handlers
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, signal_handler)
    
    logger.info("Starting measurements updater")
    logger.info(f"Measurements will be written to: {MEASUREMENTS_FILE}")
    logger.info(f"Using settings from: {SETTINGS_FILE}")
    
    try:
        await update_measurements()
    except KeyboardInterrupt:
        logger.info("Measurements updater stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        logger.info("Measurements updater shutting down")
        cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 