### IMPORTS ###
import os
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
import scd30_i2c  # Import the module directly
import logging_setup

# Initialize logging first thing
logging_setup.setup_logging()
logger = logging_setup.get_logger('shroombox')

# Set up logging ONCE at the module level
logger.setLevel(logging.INFO)

# Only add handlers if they don't exist
if not logger.handlers:
    # Get log directory from environment variable, fall back to local logs
    log_dir = os.getenv('SHROOMBOX_LOG_DIR', os.path.join(os.path.dirname(__file__), 'logs'))
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, 'main.log')
    try:
        # Create file handler
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=1024*1024,  # 1MB
            backupCount=5,
            mode='a'
        )
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
        logger.info(f"Logging to: {log_file}")
    except Exception as e:
        print(f"Error setting up file logging: {e}")
        # Continue with console-only logging
    
    # Always add console handler
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

# Make logger not buffer output
logger.propagate = False

# Load environment variables
load_dotenv()

# Log environment variables
logger.info("Environment variables loaded:")
logger.info(f"INFLUXDB_URL: {os.getenv('INFLUXDB_URL')}")
logger.info(f"INFLUXDB_ORG: {os.getenv('INFLUXDB_ORG')}")
logger.info(f"INFLUXDB_BUCKET: {os.getenv('INFLUXDB_BUCKET')}")
logger.info("=" * 50)

import asyncio
import time
from datetime import datetime
from typing import Optional, Tuple
import json
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import RPi.GPIO as GPIO
import socket
import subprocess
import aiohttp
import logging
from logging.handlers import RotatingFileHandler

from simple_pid import PID
from tapo import ApiClient
from noctua_pwm import NoctuaFan
from tapo_controller import TapoController
from scd30_controller import SCD30Controller

### CONSTANTS ###
MEASUREMENT_INTERVAL = 5
TEMP_OFFSET = 2
HUMIDIFIER_BURST_MIN = 0.5    # Minimum burst time in seconds
HUMIDIFIER_BURST_MAX = 30   # Maximum burst time in seconds
HUMIDITY_BREAK_TIME = 60   # minimum time between humidifier activations
RH_HYSTERESIS = 2.0       # Hysteresis band (±2%)

### CLASSES ###
class EnvironmentSetpoints:
    def __init__(
        self,
        temp_setpoint: float,
        co2_setpoint: float,
        rh_setpoint: float
    ):
        self.temp_setpoint = temp_setpoint
        self.co2_setpoint = co2_setpoint
        self.rh_setpoint = rh_setpoint

# Define setpoints for different growth phases
COLONISATION_SETPOINTS = EnvironmentSetpoints(
    temp_setpoint=27.0,
    co2_setpoint=1000,
    rh_setpoint=85.0
)

GROW_SETPOINTS = EnvironmentSetpoints(
    temp_setpoint=22.0,
    co2_setpoint=550,
    rh_setpoint=60.0
)

CAKE_SETPOINTS = EnvironmentSetpoints(
    temp_setpoint=27.0,
    co2_setpoint=500,
    rh_setpoint=85.0
)

class EnvironmentController:
    def __init__(self):
        # Add debug logging for current working directory
        current_dir = os.getcwd()
        logger.info(f"Current working directory: {current_dir}")
        
        # Use path relative to the script location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(script_dir, 'config', 'settings.json')
        logger.info(f"Looking for config at: {self.config_path}")
        
        self.last_config_check = 0
        self.config_check_interval = 5  # Check config every 5 seconds
        self.current_settings = self.load_config()
        
        # Initialize config last modified time
        try:
            self.config_last_modified = os.path.getmtime(self.config_path)
            logger.info(f"Config last modified: {datetime.fromtimestamp(self.config_last_modified)}")
        except Exception as e:
            logger.error(f"Error getting config modification time: {e}")
            self.config_last_modified = 0
        
        # Initialize logging settings FIRST
        self.logging_interval = self.current_settings.get('logging', {}).get('interval', 30)
        
        # Get measurement interval from config, with fallback to default
        self.measurement_interval = self.current_settings.get('sensor', {}).get('measurement_interval', 5)
        
        # Initialize state tracking variables
        self.fan_percentage = 0  # Track current fan speed
        self.heater_on = False  # Track heater state
        self.humidifier_on = False  # Track humidifier state
        self.fan = NoctuaFan()  # Initialize fan controller
        
        # Store device IPs
        self.heater_ip = None
        self.humidifier_ip = None
        
        # Initialize sensor
        self.sensor = SCD30Controller(
            measurement_interval=self.current_settings['sensor']['measurement_interval']
        )
        
        # Load initial device assignments
        self._load_device_assignments()
        
        # Initialize PIDs with default values first
        phase = self.current_settings['environment']['current_phase']
        phase_settings = self.current_settings['environment']['phases'][phase]
        
        # Debug print PID initialization
        logger.info("\nInitializing PIDs:")
        logger.info(f"Phase: {phase}")
        logger.info(f"RH Setpoint: {phase_settings['rh_setpoint']}")
        logger.info(f"CO2 Setpoint: {phase_settings['co2_setpoint']}")
        
        # Initialize CO2 PID
        self.co2_pid = PID(
            Kp=-1,
            Ki=-0.01,
            Kd=0,
            setpoint=float(phase_settings['co2_setpoint']),  # Make sure to convert to float
            output_limits=(0, 100)
        )
        
        # Initialize CPU PID
        self.cpu_pid = PID(
            Kp=-10,
            Ki=-3,
            Kd=0.05,
            setpoint=30,
            output_limits=(0, 100)
        )
        
        # Initialize Humidity PID
        self.humidity_pid = PID(
            Kp=0.2,
            Ki=0.01,
            Kd=0.05,
            setpoint=float(phase_settings['rh_setpoint']),  # Make sure to convert to float
            output_limits=(0, HUMIDIFIER_BURST_MAX)
        )
        # Force initial output to minimum burst time
        self.humidity_pid._last_output = HUMIDIFIER_BURST_MIN
        
        # Initialize humidifier state tracking
        self.humidifier_bursting = False
        self.burst_end_time = 0
        self.last_humidifier_state = False  # Track state changes
        
        # Now update controllers with config settings
        self.update_controllers()
        
        # Initialize InfluxDB client
        try:
            logger.info("\n=== Initializing InfluxDB Client ===")
            logger.info(f"URL: {os.getenv('INFLUXDB_URL')}")
            logger.info(f"Organization: {os.getenv('INFLUXDB_ORG')}")
            logger.info(f"Bucket: {os.getenv('INFLUXDB_BUCKET')}")
            
            if not os.getenv('INFLUXDB_TOKEN'):
                logger.error("❌ Error: INFLUXDB_TOKEN not found in environment variables")
                return
                
            self.influx_client = InfluxDBClient(
                url=os.getenv('INFLUXDB_URL', 'http://localhost:8086'),
                token=os.getenv('INFLUXDB_TOKEN'),
                org=os.getenv('INFLUXDB_ORG')
            )
            self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
            
            # Test the connection
            try:
                test_point = Point("test_connection").field("value", 1)
                self.write_api.write(
                    bucket=os.getenv('INFLUXDB_BUCKET'),
                    record=test_point
                )
                logger.info("✓ InfluxDB connection test successful")
            except Exception as e:
                logger.error(f"❌ InfluxDB connection test failed: {e}")
                
        except Exception as e:
            logger.error(f"❌ Error initializing InfluxDB client: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
        
        self.session = None
        self.connector = None
        
        # Initialize Tapo controller
        self.tapo = TapoController(
            email=os.getenv('TAPO_EMAIL'),
            password=os.getenv('TAPO_PASSWORD')
        )
        
        # Get device configs from settings
        self.humidifier_config = self.current_settings.get('devices', {}).get('humidifier')
        self.heater_config = self.current_settings.get('devices', {}).get('heater')
        
        # Initialize temperature_last_called
        self.temperature_last_called = 0
        
        self.system_running = False
        self.monitoring_enabled = True
        
    def load_config(self):
        """Load settings from config file."""
        try:
            logger.info(f"Loading config from: {self.config_path}")
            
            # Check if file exists
            if not os.path.exists(self.config_path):
                logger.error(f"Config file does not exist: {self.config_path}")
                return {}
                
            # Check file permissions
            try:
                file_stat = os.stat(self.config_path)
                logger.info(f"Config file permissions: {oct(file_stat.st_mode)}")
                logger.info(f"Config file owner: {file_stat.st_uid}, group: {file_stat.st_gid}")
            except Exception as e:
                logger.warning(f"Could not check file permissions: {e}")
            
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                logger.info(f"Successfully loaded config from {self.config_path}")
            
            # Ensure numeric values are properly converted
            if 'environment' in config and 'phases' in config['environment']:
                for phase_name, phase_data in config['environment']['phases'].items():
                    if 'temp_setpoint' in phase_data:
                        phase_data['temp_setpoint'] = float(phase_data['temp_setpoint'])
                    if 'rh_setpoint' in phase_data:
                        phase_data['rh_setpoint'] = float(phase_data['rh_setpoint'])
                    if 'co2_setpoint' in phase_data:
                        phase_data['co2_setpoint'] = int(phase_data['co2_setpoint'])
                
                # Log the current phase settings
                current_phase = config['environment']['current_phase']
                if current_phase in config['environment']['phases']:
                    phase_settings = config['environment']['phases'][current_phase]
                    logger.info(f"Loaded settings for phase '{current_phase}':")
                    logger.info(f"  Temperature setpoint: {phase_settings.get('temp_setpoint')}°C")
                    logger.info(f"  Humidity setpoint: {phase_settings.get('rh_setpoint')}%")
                    logger.info(f"  CO2 setpoint: {phase_settings.get('co2_setpoint')}ppm")
                else:
                    logger.warning(f"Current phase '{current_phase}' not found in config phases")
                    
            return config
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing config file (invalid JSON): {e}")
            # Try to read the raw file content for debugging
            try:
                with open(self.config_path, 'r') as f:
                    content = f.read()
                logger.error(f"Raw config file content: {content[:500]}...")
            except Exception as read_error:
                logger.error(f"Could not read raw config file: {read_error}")
            return {}
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
            return {}

    def get_logging_interval(self) -> int:
        """Get the current logging interval in seconds."""
        return self.current_settings.get('logging', {}).get('interval', 30)

    def update_controllers(self):
        """Update controller settings from config."""
        if not self.current_settings:
            logger.warning("No settings available to update controllers")
            return

        try:
            phase = self.current_settings['environment']['current_phase']
            phase_settings = self.current_settings['environment']['phases'][phase]
            
            # Log the current phase and settings we're applying
            logger.info(f"Updating controllers with phase: {phase}")
            logger.info(f"Temperature setpoint: {phase_settings['temp_setpoint']}°C")
            logger.info(f"Humidity setpoint: {phase_settings['rh_setpoint']}%")
            logger.info(f"CO2 setpoint: {phase_settings['co2_setpoint']}ppm")
            
            # Convert setpoints to float
            try:
                # Update CO2 and humidity PID setpoints
                self.co2_pid.setpoint = float(phase_settings['co2_setpoint'])
                self.humidity_pid.setpoint = float(phase_settings['rh_setpoint'])
                
                # Note: Temperature doesn't use PID, it uses hysteresis control
                # The temperature setpoint is applied directly in temperature_control method
            except (ValueError, TypeError) as e:
                logger.error(f"Error converting setpoints to float: {e}")
                logger.error(f"CO2 setpoint: {phase_settings['co2_setpoint']}")
                logger.error(f"RH setpoint: {phase_settings['rh_setpoint']}")
                return

            # Update logging interval
            new_logging_interval = self.current_settings.get('logging', {}).get('interval', 30)
            if new_logging_interval != self.logging_interval:
                logger.info(f"\nUpdating logging interval: {self.logging_interval}s -> {new_logging_interval}s")
                self.logging_interval = new_logging_interval
                logger.info("✓ Logging interval updated")

            # Update humidity PID parameters
            hum_pid_settings = self.current_settings['humidifier'].get('pid', {})
            if hum_pid_settings:
                old_tunings = self.humidity_pid.tunings
                new_tunings = (
                    float(hum_pid_settings.get('Kp', 0.2)),
                    float(hum_pid_settings.get('Ki', 0.01)),
                    float(hum_pid_settings.get('Kd', 0.05))
                )
                
                if old_tunings != new_tunings:
                    logger.info(f"Updating humidity PID tunings: {old_tunings} -> {new_tunings}")
                    self.humidity_pid.tunings = new_tunings

            # Update CO2 PID parameters
            co2_pid_settings = self.current_settings['co2'].get('pid', {})
            if co2_pid_settings:
                old_tunings = self.co2_pid.tunings
                new_tunings = (
                    float(co2_pid_settings.get('Kp', -1.0)),
                    float(co2_pid_settings.get('Ki', -0.01)),
                    float(co2_pid_settings.get('Kd', 0.0))
                )
                
                if old_tunings != new_tunings:
                    logger.info(f"Updating CO2 PID tunings: {old_tunings} -> {new_tunings}")
                    self.co2_pid.tunings = new_tunings

            # Update sensor interval if changed
            new_interval = self.current_settings.get('sensor', {}).get('measurement_interval', 5)
            if new_interval != self.measurement_interval:
                logger.info(f"\nUpdating sensor measurement interval: {self.measurement_interval}s -> {new_interval}s")
                self.measurement_interval = new_interval
                if self.sensor:
                    try:
                        self.sensor.set_measurement_interval(self.measurement_interval)
                        logger.info("✓ Sensor measurement interval updated")
                    except Exception as e:
                        logger.error(f"✗ Error updating sensor interval: {e}")
                        
            logger.info("Controllers updated successfully with new settings")
        except Exception as e:
            logger.error(f"Error in update_controllers: {e}")
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")

    async def check_config_updates(self):
        """Check for updates to config file and reload if necessary."""
        try:
            # Get the last modification time of the config file
            config_mtime = os.path.getmtime(self.config_path)
            current_time = time.time()
            
            logger.info(f"Checking config updates - File: {self.config_path}")
            logger.info(f"Last modified time: {datetime.fromtimestamp(config_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"Last checked time: {datetime.fromtimestamp(self.config_last_modified).strftime('%Y-%m-%d %H:%M:%S') if self.config_last_modified > 0 else 'Never'}")
            logger.info(f"Current time: {datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')}")
            
            # If the file has been modified since last check, reload it
            if config_mtime > self.config_last_modified:
                logger.info(f"Config file modified at {datetime.fromtimestamp(config_mtime)}, reloading...")
                
                # Read the file content for debugging
                try:
                    with open(self.config_path, 'r') as f:
                        file_content = f.read()
                        logger.info(f"Current config file content (first 500 chars): {file_content[:500]}...")
                except Exception as e:
                    logger.error(f"Error reading config file for debug: {e}")
                
                old_settings = self.current_settings.copy() if self.current_settings else {}
                self.current_settings = self.load_config()
                self.config_last_modified = config_mtime
                
                # Log the changes to help with debugging
                if old_settings:
                    # Check if growth phase changed
                    old_phase = old_settings.get('environment', {}).get('current_phase', 'unknown')
                    new_phase = self.current_settings.get('environment', {}).get('current_phase', 'unknown')
                    logger.info(f"CONFIG UPDATE: Phase changed: {old_phase} -> {new_phase}")
                    
                    # Always log temperature setpoint for the current phase, regardless of whether phase changed
                    old_temp = old_settings.get('environment', {}).get('phases', {}).get(new_phase, {}).get('temp_setpoint', 'unknown')
                    new_temp = self.current_settings.get('environment', {}).get('phases', {}).get(new_phase, {}).get('temp_setpoint', 'unknown')
                    logger.info(f"CONFIG UPDATE: Temperature setpoint: {old_temp} -> {new_temp}")
                    
                    # Also log CO2 and humidity setpoints
                    old_co2 = old_settings.get('environment', {}).get('phases', {}).get(new_phase, {}).get('co2_setpoint', 'unknown')
                    new_co2 = self.current_settings.get('environment', {}).get('phases', {}).get(new_phase, {}).get('co2_setpoint', 'unknown')
                    logger.info(f"CONFIG UPDATE: CO2 setpoint: {old_co2} -> {new_co2}")
                    
                    old_rh = old_settings.get('environment', {}).get('phases', {}).get(new_phase, {}).get('rh_setpoint', 'unknown')
                    new_rh = self.current_settings.get('environment', {}).get('phases', {}).get(new_phase, {}).get('rh_setpoint', 'unknown')
                    logger.info(f"CONFIG UPDATE: Humidity setpoint: {old_rh} -> {new_rh}")
                    
                    # Check heater device details
                    old_devices = old_settings.get('available_devices', [])
                    new_devices = self.current_settings.get('available_devices', [])
                    
                    old_heater = next((d for d in old_devices if d.get('role') == 'heater'), None)
                    new_heater = next((d for d in new_devices if d.get('role') == 'heater'), None)
                    
                    if old_heater and new_heater:
                        logger.info(f"CONFIG UPDATE: Heater state in config: {old_heater.get('state')} -> {new_heater.get('state')}")
                        logger.info(f"CONFIG UPDATE: Heater IP: {old_heater.get('ip')} -> {new_heater.get('ip')}")
                
                # Update the controllers with the new settings
                try:
                    logger.info("Updating controllers with new settings...")
                    self.update_controllers()
                    
                    # Force an immediate reevaluation of the heater state based on new settings
                    if hasattr(self, 'diagnose_heater_control'):
                        asyncio.create_task(self.diagnose_heater_control())
                        logger.info("Running heater diagnostic with new settings")
                except Exception as e:
                    logger.error(f"Error updating controllers with new settings: {e}")
            else:
                logger.info(f"No changes detected in config file (last modified: {datetime.fromtimestamp(config_mtime).strftime('%Y-%m-%d %H:%M:%S')})")
        except Exception as e:
            logger.error(f"Error checking for config updates: {e}")
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
            # Don't update the config_last_modified time on error
            # so we'll try again on the next check

    async def get_measurements(self) -> Optional[Tuple[float, float, float]]:
        """Get measurements from the sensor."""
        return await self.sensor.get_measurements()

    def co2_control(self, co2: float, setpoint_max: float) -> None:
        """Control CO2 levels using PID controller."""
        self.fan_percentage = float(self.co2_pid(co2))
        
        # Get CPU temperature and use the higher of CO2 control or CPU cooling needs
        cpu_temp = self.fan.get_cpu_temp()
        if cpu_temp and cpu_temp > 70:  # CPU getting too hot
            self.fan.auto_control()  # Let auto control take over
        else:
            self.fan.set_speed(self.fan_percentage)  # Normal CO2 control

    async def initialize_devices(self):
        """Initialize device connections."""
        try:
            # Initialize TapoController
            self.tapo = TapoController(
                email=os.getenv('TAPO_EMAIL'),
                password=os.getenv('TAPO_PASSWORD')
            )
            
            # Scan for devices and update settings
            await self.tapo.scan_and_update_settings('config/settings.json')
            
            # Initialize device connections
            if self.humidifier_config:
                self.humidifier_ip = await self.tapo.get_or_update_device(self.humidifier_config)
                if self.humidifier_ip:
                    logger.info(f"Connected to humidifier at {self.humidifier_ip}")
                else:
                    logger.error("Failed to connect to humidifier")
            
            if self.heater_config:
                self.heater_ip = await self.tapo.get_or_update_device(self.heater_config)
                if self.heater_ip:
                    logger.info(f"Connected to heater at {self.heater_ip}")
                else:
                    logger.error("Failed to connect to heater")
        except Exception as e:
            logger.error(f"Error initializing devices: {e}")

    async def set_humidifier_state(self, state: bool) -> None:
        """Set humidifier state."""
        if self.humidifier_ip:
            await self.tapo.set_device_state(self.humidifier_ip, state)
            self.humidifier_on = state
            
            # Update state in settings.json
            try:
                with open(self.config_path, 'r') as f:
                    settings = json.load(f)
                
                # Update device state in settings
                for device in settings.get('available_devices', []):
                    if device.get('role') == 'humidifier':
                        device['state'] = state
                
                # Save updated settings
                with open(self.config_path, 'w') as f:
                    json.dump(settings, f, indent=4)
            except Exception as e:
                logger.error(f"Error updating humidifier state in settings: {e}")

    async def set_heater_state(self, state: bool) -> None:
        """Set heater state."""
        if self.heater_ip:
            try:
                logger.info(f"Setting heater to {'ON' if state else 'OFF'}")
                
                # Get current state before changing
                current_state = await self.tapo.get_device_state(self.heater_ip)
                
                # Only send command if needed
                if current_state != state:
                    # Try to set the state
                    success = await self.tapo.set_device_state(self.heater_ip, state)
                    
                    if success:
                        logger.info(f"Successfully set heater to {'ON' if state else 'OFF'}")
                    else:
                        logger.error(f"Failed to set heater to {'ON' if state else 'OFF'}")
                        return
                else:
                    logger.debug(f"Heater already {'ON' if state else 'OFF'}, no change needed")
                
                # Update internal tracking
                self.heater_on = state
                
                # Verify the state change
                try:
                    actual_state = await self.tapo.get_device_state(self.heater_ip)
                    if actual_state != state:
                        logger.warning(f"Heater state verification failed! Expected {'ON' if state else 'OFF'} but got {'ON' if actual_state else 'OFF'}")
                    else:
                        logger.debug("Heater state verified successfully")
                except Exception as e:
                    logger.error(f"Error verifying heater state: {e}")
                
                # Update state in settings.json
                try:
                    with open(self.config_path, 'r') as f:
                        settings = json.load(f)
                    
                    # Update device state in settings
                    for device in settings.get('available_devices', []):
                        if device.get('role') == 'heater':
                            if device['state'] != state:
                                device['state'] = state
                                logger.debug(f"Updated heater state in settings.json to {'ON' if state else 'OFF'}")
                    
                    # Save updated settings
                    with open(self.config_path, 'w') as f:
                        json.dump(settings, f, indent=4)
                except Exception as e:
                    logger.error(f"Error updating heater state in settings: {e}")
            except Exception as e:
                logger.error(f"Error setting heater state: {e}")
                import traceback
                logger.error(f"Stack trace: {traceback.format_exc()}")

    async def connect_to_humidifier(self, retries=3):
        """Connect to humidifier with retries."""
        try:
            # Try to ping the device first
            result = subprocess.run(['ping', '-c', '1', '-W', '1', self.humidifier_ip], 
                                    capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"\nHumidifier not responding to ping at {self.humidifier_ip}")
                logger.error("Please check:")
                logger.error("1. Is the humidifier powered on?")
                logger.error("2. Is the IP address correct?")
                logger.error("3. Are you connected to the right network?")
                return None
            
            logger.info(f"\nTrying to connect to humidifier at {self.humidifier_ip}")
            client = ApiClient(self.tapo_email, self.tapo_password)
            humidifier = await client.p115(self.humidifier_ip)
            logger.info("Successfully connected to humidifier")
            return humidifier
            
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return None

    async def measure_burst_effect(self, start_rh: float, wait_time: int = 30) -> Tuple[float, float]:
        """
        Measure the effect of a burst after waiting for humidity to stabilize.
        Returns (end_rh, rh_change)
        """
        # Wait for humidity to spread and stabilize
        await asyncio.sleep(wait_time)
        
        # Take multiple measurements to get a stable reading
        measurements = await self.get_measurements()
        if measurements:
            end_rh = measurements[2]
            rh_change = end_rh - start_rh
            return end_rh, rh_change
        return start_rh, 0.0  # Return no change if measurement fails

    async def humidity_control(self, current_rh: float) -> None:
        """Control humidity using PID controller."""
        try:
            # Ensure we're working with float values
            current_rh = float(current_rh)
            setpoint = float(self.humidity_pid.setpoint)
            current_time = time.time()
            
            # Skip humidity control if RH is above setpoint
            if current_rh >= setpoint:
                await self.set_humidifier_state(False)  # Ensure humidifier is off
                return

            # Check if we're in a burst
            if self.humidifier_bursting:
                if current_time >= self.burst_end_time:
                    self.humidifier_bursting = False
                    await self.set_humidifier_state(False)
                    return

            # Calculate burst duration using PID
            burst_duration = self.humidity_pid(current_rh)
            
            # Start a new burst if duration is sufficient
            if burst_duration >= HUMIDIFIER_BURST_MIN:
                self.humidifier_bursting = True
                self.burst_end_time = current_time + burst_duration
                await self.set_humidifier_state(True)
                
        except Exception as e:
            logger.error(f"Error in humidity control: {e}")
            await self.set_humidifier_state(False)  # Safety: turn off on error

    def log_humidifier_state(self, state: int, current_rh: float, burst_duration: float = 0.0) -> None:
        """Log humidifier state to InfluxDB."""
        try:
            bucket = os.getenv('INFLUXDB_BUCKET')
            if not bucket or not self.write_api:
                return
            
            phase = self.current_settings['environment']['current_phase']
            
            # Create point with humidifier state
            point = Point("humidifier_state") \
                .tag("location", "shroombox") \
                .tag("phase", phase) \
                .field("state", state) \
                .field("humidity", float(current_rh)) \
                .field("setpoint", float(self.humidity_pid.setpoint)) \
                .field("burst_duration", float(burst_duration))
            
            self.write_api.write(bucket=bucket, record=point)
            logger.info(f"✓ Logged humidifier state: {'ON' if state == 1 else 'OFF'}")
            
        except Exception as e:
            logger.error(f"❌ Error logging humidifier state: {e}")

    def log_heater_state(self, state: int, current_temp: float) -> None:
        """Log heater state to InfluxDB."""
        try:
            bucket = os.getenv('INFLUXDB_BUCKET')
            if not bucket or not self.write_api:
                return
            
            phase = self.current_settings['environment']['current_phase']
            
            # Get the current temperature setpoint
            temp_setpoint = self.current_settings['environment']['phases'][phase]['temp_setpoint']
            
            # Create point with heater state
            point = Point("heater_state") \
                .tag("location", "shroombox") \
                .tag("phase", phase) \
                .field("state", state) \
                .field("temperature", float(current_temp)) \
                .field("setpoint", float(temp_setpoint))
            
            self.write_api.write(bucket=bucket, record=point)
            logger.info(f"✓ Logged heater state: {'ON' if state == 1 else 'OFF'}")
            
        except Exception as e:
            logger.error(f"❌ Error logging heater state: {e}")

    async def start_system(self):
        """Start environmental control system."""
        self.system_running = True
        logger.info("System control started")
        # Initialize PIDs, etc.

    async def stop_system(self):
        """Stop environmental control system but continue monitoring."""
        self.system_running = False
        # Turn off all devices
        await self.set_heater_state(False)
        await self.set_humidifier_state(False)
        self.fan.set_speed(0)
        logger.info("System control stopped (monitoring continues)")

    async def control_loop(self):
        """Main control loop."""
        if not self.system_running:
            return  # Skip control logic if system is stopped

        try:
            # Check for config updates first to ensure we have current settings
            await self.check_config_updates()
            
            # Log that control loop is executing
            logger.debug("Control loop executing...")
            
            # Get current measurements
            measurements = await self.get_measurements()
            if not measurements:
                logger.warning("No measurements available for control loop")
                return
                
            co2, temperature, rh = measurements
            
            # Log current measurements and setpoints
            current_phase = self.current_settings['environment']['current_phase']
            temp_setpoint = float(self.current_settings['environment']['phases'][current_phase]['temp_setpoint'])
            logger.info(f"Current readings - Temp: {temperature:.1f}°C (setpoint: {temp_setpoint:.1f}°C), RH: {rh:.1f}%, CO2: {co2:.0f}ppm")
            
            # FIRST update device states to get current actual state
            logger.debug("Updating device states first...")
            previous_heater_state = self.heater_on
            await self.update_device_states()
            
            # Check if state changed externally and log it
            if previous_heater_state != self.heater_on:
                logger.warning(f"Heater state changed externally: {previous_heater_state} -> {self.heater_on}")
            
            # Calculate what heater state SHOULD be based on temperature
            temp_hysteresis = float(self.current_settings['environment']['phases'][current_phase]['temp_hysteresis'])
            temp_low = temp_setpoint - temp_hysteresis
            should_heat = temperature < temp_low
            
            # Compare actual state with what it should be
            if should_heat != self.heater_on:
                logger.warning(f"STATE MISMATCH: Heater is {'ON' if self.heater_on else 'OFF'} but should be {'ON' if should_heat else 'OFF'} based on temperature")
            else:
                logger.debug(f"Heater state is correct: {'ON' if self.heater_on else 'OFF'} (Should be {'ON' if should_heat else 'OFF'})")
            
            # Run temperature control AFTER state update so it has the final say
            logger.debug("Running temperature control (with final authority)...")
            await self.temperature_control(temperature)
            
            # Run humidity control
            logger.debug("Running humidity control...")
            await self.humidity_control(rh)
            
            # Run CO2 control
            logger.debug("Running CO2 control...")
            await self.co2_control(co2, self.current_settings['environment']['phases'][current_phase]['co2_setpoint'])
                        
        except Exception as e:
            logger.error(f"Error in control loop: {e}")
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")

    async def start(self):
        """Initialize async resources."""
        self.session = aiohttp.ClientSession()
        
    async def cleanup(self):
        """Cleanup resources before shutdown."""
        try:
            logger.info("\n=== Cleaning up resources ===")
            
            # Stop the fan
            if hasattr(self, 'fan'):
                self.fan.set_speed(0)
                logger.info("✓ Fan stopped")
            
            # Turn off devices
            try:
                await self.set_heater_state(False)
                logger.info("✓ Heater turned off")
            except Exception as e:
                logger.error(f"❌ Error turning off heater: {e}")
                
            try:
                await self.set_humidifier_state(False)
                logger.info("✓ Humidifier turned off")
            except Exception as e:
                logger.error(f"❌ Error turning off humidifier: {e}")
            
            # Close InfluxDB client
            if hasattr(self, 'influx_client'):
                self.influx_client.close()
                logger.info("✓ InfluxDB client closed")
                
            logger.info("✓ Cleanup completed")
            
        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")

    async def write_system_log(self, message: str, level: str = "info") -> None:
        """Write a system log message to InfluxDB."""
        try:
            # Debug print
            bucket = os.getenv('INFLUXDB_BUCKET')
            logger.info(f"write_system_log using bucket: {bucket}")
            
            log_point = Point("system_log") \
                .tag("location", "shroombox") \
                .tag("level", level) \
                .field("message", message) \
                .time(datetime.utcnow())
            
            self.write_api.write(
                bucket=bucket,
                record=log_point
            )
        except Exception as e:
            logger.error(f"Error writing to system log: {e}")

    async def log_to_flask(self, message: str) -> None:
        """Send log message to Flask web interface."""
        logger.info(f"\nAttempting to send to Flask: {message}")  # Debug print
        try:
            async with aiohttp.ClientSession() as session:
                try:
                    response = await session.post(
                        'http://192.168.8.157:5000/log',
                        json={'message': message},
                        timeout=5  # Add timeout
                    )
                    logger.info(f"Flask response status: {response.status}")
                    if response.status != 200:
                        response_text = await response.text()
                        logger.error(f"Error response from Flask: {response_text}")
                except aiohttp.ClientError as e:
                    logger.error(f"Network error sending to Flask: {e}")
                except asyncio.TimeoutError:
                    logger.error("Timeout sending to Flask")
                except Exception as e:
                    logger.error(f"Unexpected error sending to Flask: {e}")
        except Exception as e:
            logger.error(f"Session creation error: {e}")
        
        # Also write directly to the log file as a backup
        try:
            with open('/var/log/shroombox-main.log', 'a') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"{timestamp} - {message}\n")
                f.flush()
        except Exception as e:
            logger.error(f"Error writing directly to log file: {e}")

    async def connect_to_heater(self, retries=3):
        """Connect to heater plug with retries using Tapo library."""
        try:
            # Try to ping the device first
            result = subprocess.run(['ping', '-c', '1', '-W', '1', self.heater_ip], 
                                    capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"\nHeater plug not responding to ping at {self.heater_ip}")
                logger.error("Please check:")
                logger.error("1. Is the heater plug powered on?")
                logger.error("2. Is the IP address correct?")
                logger.error("3. Are you connected to the right network?")
                return None
            
            logger.info(f"\nTrying to connect to heater plug at {self.heater_ip}")
            client = ApiClient(self.tapo_email, self.tapo_password)
            self.heater = await client.p115(self.heater_ip)
            logger.info("Successfully connected to heater plug")
            return self.heater
            
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return None

    async def temperature_control(self, temperature: float) -> None:
        """Control temperature using heater."""
        try:
            # Get current phase settings
            current_phase = self.current_settings['environment']['current_phase']
            setpoint = float(self.current_settings['environment']['phases'][current_phase]['temp_setpoint'])
            hysteresis = float(self.current_settings['environment']['phases'][current_phase]['temp_hysteresis'])
            
            # Calculate temperature bounds
            temp_low = setpoint - hysteresis
            
            # Add detailed debug logging
            logger.info(f"TEMP CONTROL DEBUG: Current temp={temperature:.1f}°C, Setpoint={setpoint:.1f}°C, Hysteresis={hysteresis:.1f}°C")
            logger.info(f"TEMP CONTROL DEBUG: Turn on threshold={temp_low:.1f}°C, Current heater state={'ON' if self.heater_on else 'OFF'}")
            
            # Determine if heater should be on or off
            should_heat = temperature < temp_low
            logger.info(f"TEMP CONTROL DEBUG: Should heat? {should_heat} (temp < threshold? {temperature:.1f} < {temp_low:.1f})")
            
            # Get ACTUAL current state directly from device for double-checking
            actual_state = False
            if self.heater_ip:
                try:
                    actual_state = await self.tapo.get_device_state(self.heater_ip)
                    if actual_state != self.heater_on:
                        logger.warning(f"TEMP CONTROL DEBUG: Tracked state ({self.heater_on}) differs from actual device state ({actual_state})")
                except Exception as e:
                    logger.error(f"Error checking actual device state: {e}")
            
            # ALWAYS apply the correct state - don't rely on state tracking
            # This ensures the temperature control logic has authority
            logger.info(f"TEMP CONTROL DEBUG: Enforcing heater state to {'ON' if should_heat else 'OFF'} based on temperature logic")
            await self.set_heater_state(should_heat)
            logger.info(f"Heater set to {'ON' if should_heat else 'OFF'} - Temp: {temperature}°C (Target: {setpoint}°C ±{hysteresis}°C)")
            
            # Log the heater state to InfluxDB
            self.log_heater_state(1 if should_heat else 0, temperature)
                
        except Exception as e:
            logger.error(f"Error in temperature control: {e}")
            # Add stack trace for better debugging
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")

    async def diagnose_sensor(self):
        """Print sensor diagnostic information."""
        try:
            if not self.sensor:
                logger.warning("No sensor available for diagnosis")
                return
                
            logger.info("\n=== SCD30 Sensor Diagnosis ===")
            logger.info(f"ASC Status: {self.sensor.get_auto_self_calibration()}")  # Changed back to original method
            logger.info(f"Measurement Interval: {self.sensor.get_measurement_interval()}s")
            logger.info(f"Temperature Offset: {self.sensor.get_temperature_offset()}°C")
            logger.info(f"Firmware Version: {self.sensor.get_firmware_version()}")
            logger.info("============================\n")
            
        except Exception as e:
            logger.error(f"Error during sensor diagnosis: {e}")

    async def initialize_sensor(self) -> bool:
        """Initialize the sensor."""
        return self.sensor.is_available()

    async def log_data(self, co2: float, temp: float, rh: float) -> None:
        """Log sensor data to InfluxDB."""
        if not self.monitoring_enabled:
            return  # Skip logging if monitoring is disabled
        try:
            logger.debug(f"Attempting to log data - CO2: {co2}ppm, Temp: {temp}°C, RH: {rh}%")
            
            # Only log if we have valid measurements
            if all(x is not None for x in [co2, temp, rh]):
                await self.write_to_influx(co2, temp, rh)
                logger.debug("Data logged successfully")
            else:
                logger.warning("Skipping data logging due to invalid measurements")
                logger.debug(f"Invalid values detected - CO2: {co2}, Temp: {temp}, RH: {rh}")
                
        except Exception as e:
            logger.error(f"Error logging data: {e}")

    def _load_device_assignments(self):
        """Load device assignments from settings."""
        try:
            devices = self.current_settings.get('available_devices', [])
            heater = next((d for d in devices if d.get('role') == 'heater'), None)
            humidifier = next((d for d in devices if d.get('role') == 'humidifier'), None)
            
            self.heater_ip = heater['ip'] if heater else None
            self.humidifier_ip = humidifier['ip'] if humidifier else None
            
            logger.info(f"Loaded device assignments - Heater: {self.heater_ip}, Humidifier: {self.humidifier_ip}")
        except Exception as e:
            logger.error(f"Error loading device assignments: {e}")

    async def update_device_states(self):
        """Update the states of connected devices."""
        try:
            if self.heater_ip:
                self.heater_on = await self.tapo.get_device_state(self.heater_ip)
            if self.humidifier_ip:
                self.humidifier_on = await self.tapo.get_device_state(self.humidifier_ip)
        except Exception as e:
            logger.error(f"Error updating device states: {e}")

    async def write_to_influx(self, co2: float, temp: float, rh: float) -> None:
        """Write measurements to InfluxDB.
        
        Args:
            co2: CO2 level in ppm
            temp: Temperature in Celsius
            rh: Relative humidity in percent
        """
        try:
            # Create data point
            point = Point("environment") \
                .field("co2", co2) \
                .field("temperature", temp) \
                .field("humidity", rh) \
                .field("fan_speed", self.fan_percentage) \
                .field("heater", self.heater_on) \
                .field("humidifier", self.humidifier_on) \
                .time(datetime.utcnow())

            # Write to InfluxDB
            self.write_api.write(
                bucket=os.getenv('INFLUXDB_BUCKET'),
                record=point
            )
            
            logger.debug(f"Data written to InfluxDB - CO2: {co2}ppm, Temp: {temp}°C, RH: {rh}%")
            
        except Exception as e:
            logger.error(f"Error writing to InfluxDB: {e}")
            # Re-raise to be caught by caller
            raise

    async def stop_monitoring(self):
        """Complete shutdown including sensor readings."""
        self.monitoring_enabled = False
        self.system_running = False
        # Turn off all devices
        await self.set_heater_state(False)
        await self.set_humidifier_state(False)
        self.fan.set_speed(0)
        # Clean up sensor
        self.sensor.cleanup()
        logger.info("System completely stopped")

    async def diagnose_heater_control(self):
        """Special diagnostic function to check heater control logic"""
        try:
            # Get current measurements
            measurements = await self.get_measurements()
            if not measurements:
                logger.error("HEATER DIAGNOSTIC: No measurements available!")
                return
            
            co2, temperature, rh = measurements
            
            # Get setpoint
            current_phase = self.current_settings['environment']['current_phase']
            setpoint = float(self.current_settings['environment']['phases'][current_phase]['temp_setpoint'])
            hysteresis = float(self.current_settings['environment']['phases'][current_phase]['temp_hysteresis'])
            
            # Calculate threshold
            temp_low = setpoint - hysteresis
            
            # Get current heater state
            current_heater_state = await self.tapo.get_device_state(self.heater_ip) if self.heater_ip else False
            
            # What should the heater state be?
            should_heat = temperature < temp_low
            
            logger.info("=================== HEATER DIAGNOSTIC ===================")
            logger.info(f"Current temperature: {temperature:.1f}°C")
            logger.info(f"Temperature setpoint: {setpoint:.1f}°C")
            logger.info(f"Hysteresis: {hysteresis:.1f}°C")
            logger.info(f"Heat-on threshold: {temp_low:.1f}°C")
            logger.info(f"Criteria met for heating? {should_heat} (temp < threshold? {temperature:.1f} < {temp_low:.1f})")
            logger.info(f"Current heater state according to Tapo: {'ON' if current_heater_state else 'OFF'}")
            logger.info(f"Local tracking of heater state: {'ON' if self.heater_on else 'OFF'}")
            logger.info("=======================================================")
            
            # Check for mismatch
            if should_heat != current_heater_state:
                logger.warning(f"HEATER DIAGNOSTIC: Detected state mismatch! Tapo shows {'ON' if current_heater_state else 'OFF'} but should be {'ON' if should_heat else 'OFF'}")
                
                # Fix the mismatch
                logger.info(f"HEATER DIAGNOSTIC: Fixing state mismatch by setting heater to {'ON' if should_heat else 'OFF'}")
                await self.set_heater_state(should_heat)
                
                # Verify the fix
                new_state = await self.tapo.get_device_state(self.heater_ip) if self.heater_ip else False
                logger.info(f"HEATER DIAGNOSTIC: Heater state after fix: {'ON' if new_state else 'OFF'}")
                
            else:
                logger.info("HEATER DIAGNOSTIC: Heater state is correct according to control logic.")
            
        except Exception as e:
            logger.error(f"Error during heater diagnostics: {e}")
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")

class ShroomboxController:
    def __init__(self):
        self.config_path = 'config/settings.json'
        
        # Initialize TapoController
        self.tapo = TapoController(
            email=os.getenv('TAPO_EMAIL'),
            password=os.getenv('TAPO_PASSWORD')
        )
        
        # Load settings
        try:
            with open(self.config_path, 'r') as f:
                self.settings = json.load(f)
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            self.settings = {}
            
    async def get_device_by_role(self, role):
        """Get device info for a specific role from available devices."""
        device = next((d for d in self.settings['available_devices'] if d.get('role') == role), None)
        if not device:
            logger.warning(f"No device found with role: {role}")
            return None
        return device
            
    async def control_heater(self, state: bool):
        """Control the heater device."""
        try:
            heater = await self.get_device_by_role('heater')
            if heater:
                success = await self.tapo.set_device_state(heater['ip'], state)
                if success:
                    logger.info(f"Heater turned {'ON' if state else 'OFF'}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Error controlling heater: {e}")
            return False
            
    async def control_humidifier(self, state: bool):
        """Control the humidifier device."""
        try:
            humidifier = await self.get_device_by_role('humidifier')
            if humidifier:
                success = await self.tapo.set_device_state(humidifier['ip'], state)
                if success:
                    logger.info(f"Humidifier turned {'ON' if state else 'OFF'}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Error controlling humidifier: {e}")
            return False
            
    async def check_device_status(self):
        """Check if devices are reachable and update their status."""
        try:
            heater = await self.get_device_by_role('heater')
            humidifier = await self.get_device_by_role('humidifier')
            
            heater_status = False
            humidifier_status = False
            
            if heater:
                heater_info = await self.tapo.get_device_info(heater['ip'])
                heater_status = bool(heater_info)
                
            if humidifier:
                humidifier_info = await self.tapo.get_device_info(humidifier['ip'])
                humidifier_status = bool(humidifier_info)
                
            return {
                'heater': heater_status,
                'humidifier': humidifier_status
            }
            
        except Exception as e:
            logger.error(f"Error checking device status: {e}")
            return {
                'heater': False,
                'humidifier': False
            }

async def test_humidifier_plug():
    """Test function to verify the functionality of the Tapo humidifier plug."""
    humidifier_ip = "192.168.8.158"  # Replace with the actual IP address of your humidifier plug
    tapo_email = os.getenv('TAPO_EMAIL', 'dannyolsen1980@gmail.com')
    tapo_password = os.getenv('TAPO_PASSWORD', 'xerted-6wexwu-nyqraD')
    
    try:
        logger.info(f"\nTesting Tapo humidifier plug at {humidifier_ip}")
        
        # Initialize the humidifier plug
        client = ApiClient(tapo_email, tapo_password)
        humidifier = await client.p115(humidifier_ip)
        
        # Get initial state
        device_info = await humidifier.get_device_info()
        is_on = device_info.device_on
        logger.info(f"Humidifier plug initialized. Current state: {'ON' if is_on else 'OFF'}")
        
        # Toggle the humidifier state
        if is_on:
            logger.info("Turning humidifier OFF")
            await humidifier.off()
        else:
            logger.info("Turning humidifier ON")
            await humidifier.on()
        
        # Wait for the state change to take effect
        await asyncio.sleep(2)
        
        # Check the new state
        humidifier = await client.p115(humidifier_ip)
        device_info = await humidifier.get_device_info()
        is_on = device_info.device_on
        logger.info(f"Humidifier state after toggle: {'ON' if is_on else 'OFF'}")
        
        # Toggle back to original state
        if is_on:
            logger.info("Turning humidifier OFF (back to original state)")
            await humidifier.off()
        else:
            logger.info("Turning humidifier ON (back to original state)")
            await humidifier.on()
        
        # Wait for the state change to take effect
        await asyncio.sleep(2)
        
        # Check the final state
        humidifier = await client.p115(humidifier_ip)
        device_info = await humidifier.get_device_info()
        is_on = device_info.device_on
        logger.info(f"Final humidifier state: {'ON' if is_on else 'OFF'}")
        
        logger.info("Humidifier plug test completed successfully.")
    
    except Exception as e:
        logger.error(f"Error during humidifier plug test: {e}")

async def scan_and_log_devices():
    """Initial device scan and logging."""
    logger.info("\n=== Starting Initial Device Scan ===")
    
    try:
        # Initialize TapoController
        tapo = TapoController(
            email=os.getenv('TAPO_EMAIL'),
            password=os.getenv('TAPO_PASSWORD')
        )
        
        # Log initial state
        logger.info("\nBefore scan - Current settings in settings.json:")
        try:
            with open('config/settings.json', 'r') as f:
                before_settings = json.load(f)
            before_devices = before_settings.get('available_devices', [])
            logger.info(f"Number of devices: {len(before_devices)}")
            for device in before_devices:
                logger.info(f"  - {device['name']} ({device['ip']}) - Role: {device.get('role', 'Not assigned')}")
        except Exception as e:
            logger.error(f"Error reading initial settings: {e}")
        
        # Scan for devices
        logger.info("\nScanning for devices...")
        success = await tapo.scan_and_update_settings('config/settings.json')
        
        if success:
            # Read and log the updated settings
            logger.info("\nAfter scan - Updated settings in settings.json:")
            with open('config/settings.json', 'r') as f:
                settings = json.load(f)
            
            devices = settings.get('available_devices', [])
            logger.info(f"\nFound and saved {len(devices)} devices:")
            
            for device in devices:
                logger.info("\nDevice Details:")
                logger.info(f"  Name: {device['name']}")
                logger.info(f"  IP: {device['ip']}")
                logger.info(f"  MAC: {device['mac']}")
                logger.info(f"  Model: {device['model']}")
                logger.info(f"  Role: {device.get('role', 'Not assigned')}")
                logger.info(f"  State: {'ON' if device['state'] else 'OFF'}")
            
            # Check if any changes were made
            if before_devices != devices:
                logger.info("\nChanges detected in settings.json!")
                logger.info("Settings file has been updated with new device information.")
            else:
                logger.info("\nNo changes detected - settings.json remains the same.")
        else:
            logger.error("Device scan failed!")
            
    except Exception as e:
        logger.error(f"Error during initial device scan: {e}")
    
    logger.info("\n=== Device Scan Complete ===\n")

async def main():
    """Main application entry point."""
    controller = None
    try:
        # Perform initial device scan
        await scan_and_log_devices()
        
        # Initialize environment controller
        controller = EnvironmentController()
        await controller.initialize_devices()
        
        # Initialize sensor
        sensor_ok = await controller.initialize_sensor()
        if not sensor_ok:
            logger.error("Failed to initialize sensor, continuing without sensor...")
        
        logger.info("\n=== Starting Main Control Loop ===")
        
        while True:  # Main control loop
            try:
                # Get current measurements
                measurements = await controller.get_measurements()
                if measurements:
                    co2, temp, rh = measurements
                    logger.debug(f"Measurements - Temp: {temp}°C, RH: {rh}%, CO2: {co2}ppm")
                    
                    # Control temperature
                    await controller.temperature_control(temp)
                    
                    # Control humidity
                    await controller.humidity_control(rh)
                    
                    # Control CO2/ventilation
                    controller.co2_control(co2, controller.current_settings['environment']['phases'][controller.current_settings['environment']['current_phase']]['co2_setpoint'])
                    
                    # Check for configuration updates
                    await controller.check_config_updates()
                    
                    # Log data to InfluxDB
                    await controller.log_data(co2, temp, rh)
                
                # Wait for next measurement interval
                await asyncio.sleep(controller.current_settings['sensor']['measurement_interval'])
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying
                
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
    finally:
        # Cleanup
        if controller:
            await controller.cleanup()  # Await the cleanup
        logger.info("Application shutdown complete")

if __name__ == "__main__":
    # Set up logging (your existing logging setup)
    ...
    
    try:
        # Run the main function
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        logger.info("Shutting down...")
