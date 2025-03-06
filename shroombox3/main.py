### IMPORTS ###
import os
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
import scd30_i2c  # Import the module directly
import logging_setup
import copy
import json
import time
import asyncio
import aiohttp
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime
from simple_pid import PID
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from tapo import ApiClient
from noctua_pwm import NoctuaFan
from tapo_controller import TapoController
from scd30_controller import SCD30Controller
from settings_manager import SettingsManager

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
    
    log_file = os.getenv('SHROOMBOX_LOG_FILE', os.path.join(log_dir, 'main.log'))
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
        
        # Initialize settings manager
        self.settings_manager = SettingsManager(self.config_path)
        
        self.last_config_check = 0
        self.config_check_interval = 30  # Increased from 5 to 30 seconds
        
        # We'll load settings in the start method since we need async
        self.current_settings = {}
        
        # Initialize state tracking variables
        self.fan_percentage = 0  # Track current fan speed
        self.fan_manual_control = False  # Flag to indicate manual fan control
        self.heater_on = False  # Track heater state
        self.humidifier_on = False  # Track humidifier state
        self.fan = NoctuaFan()  # Initialize fan controller
        
        # Store device IPs
        self.heater_ip = None
        self.humidifier_ip = None
        
        # Add debounce timers for device state changes
        self.heater_last_change = 0
        self.humidifier_last_change = 0
        self.device_debounce_time = 10  # Minimum seconds between state changes
        
        # Initialize sensor - we'll set the measurement interval in start()
        self.sensor = SCD30Controller()
        
        # Initialize other variables
        self.influx_client = None
        self.write_api = None
        self.session = None
        self.tapo = None
        self.humidifier_config = None
        self.heater_config = None
        self.temperature_last_called = 0
        self.system_running = False
        self.monitoring_enabled = True
        
        # Initialize PIDs with default values - we'll update them in start()
        self.co2_pid = None
        self.cpu_pid = None
        self.humidity_pid = None
        
    async def start(self):
        """Initialize async resources."""
        # Create aiohttp session
        self.session = aiohttp.ClientSession()
        
        # Load settings
        self.current_settings = await self.settings_manager.load_settings()
        
        # Initialize logging settings
        self.logging_interval = self.current_settings.get('logging', {}).get('interval', 30)
        
        # Get measurement interval from config, with fallback to default
        self.measurement_interval = self.current_settings.get('sensor', {}).get('measurement_interval', 5)
        
        # Update sensor measurement interval
        self.sensor.set_measurement_interval(self.measurement_interval)
        
        # Initialize Tapo controller
        self.tapo = TapoController(
            email=os.getenv('TAPO_EMAIL'),
            password=os.getenv('TAPO_PASSWORD')
        )
        
        # Get device configs from settings
        self.humidifier_config = next((d for d in self.current_settings.get('available_devices', []) 
                                     if d.get('role') == 'humidifier'), None)
        self.heater_config = next((d for d in self.current_settings.get('available_devices', [])
                                 if d.get('role') == 'heater'), None)
        
        # Initialize InfluxDB client
        try:
            # Initialize InfluxDB client if environment variables are set
            influx_url = os.getenv('INFLUXDB_URL')
            influx_token = os.getenv('INFLUXDB_TOKEN')
            influx_org = os.getenv('INFLUXDB_ORG')
            
            if influx_url and influx_token and influx_org:
                self.influx_client = InfluxDBClient(
                    url=influx_url,
                    token=influx_token,
                    org=influx_org
                )
                self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
                logger.info(f"InfluxDB client initialized: {influx_url}")
            else:
                logger.warning("InfluxDB environment variables not set, data logging disabled")
        except Exception as e:
            logger.error(f"Error initializing InfluxDB client: {e}")
            
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
        
    async def load_config(self):
        """Load settings from config file using SettingsManager."""
        return await self.settings_manager.load_settings(force_reload=True)

    def get_logging_interval(self) -> int:
        """Get the current logging interval in seconds."""
        return self.current_settings.get('logging', {}).get('interval', 30)

    def update_controllers(self):
        """Update controller settings from config."""
        if not self.current_settings:
            return

        phase = self.current_settings['environment']['current_phase']
        phase_settings = self.current_settings['environment']['phases'][phase]
        
        # Convert setpoints to float
        try:
            self.co2_pid.setpoint = float(phase_settings['co2_setpoint'])
            self.humidity_pid.setpoint = float(phase_settings['rh_setpoint'])
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
            self.humidity_pid.tunings = (
                float(hum_pid_settings.get('Kp', 0.2)),
                float(hum_pid_settings.get('Ki', 0.01)),
                float(hum_pid_settings.get('Kd', 0.05))
            )

        # Update CO2 PID parameters
        co2_pid_settings = self.current_settings['co2'].get('pid', {})
        if co2_pid_settings:
            self.co2_pid.tunings = (
                float(co2_pid_settings.get('Kp', -1.0)),
                float(co2_pid_settings.get('Ki', -0.01)),
                float(co2_pid_settings.get('Kd', 0.0))
            )

        # Update fan settings
        fan_settings = self.current_settings.get('fan', {})
        if fan_settings:
            self.fan_manual_control = fan_settings.get('manual_control', False)
            fan_speed = fan_settings.get('speed', 0)
            
            # Always update fan speed from settings
            if self.fan_percentage != fan_speed:
                logger.info(f"Updating fan speed from settings: {self.fan_percentage:.1f}% -> {fan_speed:.1f}%")
                self.fan_percentage = fan_speed
                self.fan.set_speed(fan_speed)
                
            if self.fan_manual_control:
                logger.info(f"Fan is under manual control at {self.fan_percentage:.1f}%")
            else:
                logger.info(f"Fan is under automatic control at {self.fan_percentage:.1f}%")

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

    async def check_config_updates(self):
        """Check for configuration updates."""
        current_time = time.time()
        if current_time - self.last_config_check > self.config_check_interval:
            new_settings = await self.load_config()
            
            # Only update if settings other than device states have changed
            if self._settings_changed_excluding_device_states(new_settings, self.current_settings):
                logger.info("\nConfig changed, updating settings...")
                
                # Preserve current device states
                self._preserve_device_states(new_settings)
                
                self.current_settings = new_settings
                self.update_controllers()
                logger.info(f"New setpoints - RH: {self.humidity_pid.setpoint}%, CO2: {self.co2_pid.setpoint}ppm")
            
            self.last_config_check = current_time
    
    def _settings_changed_excluding_device_states(self, new_settings, old_settings):
        """Check if settings have changed, ignoring device state changes."""
        # Create deep copies to avoid modifying the originals
        new_copy = copy.deepcopy(new_settings)
        old_copy = copy.deepcopy(old_settings)
        
        # Remove device states from comparison
        if 'available_devices' in new_copy:
            for device in new_copy['available_devices']:
                if 'state' in device:
                    device['state'] = None
                    
        if 'available_devices' in old_copy:
            for device in old_copy['available_devices']:
                if 'state' in device:
                    device['state'] = None
        
        # Compare settings without device states
        return new_copy != old_copy
    
    def _preserve_device_states(self, new_settings):
        """Preserve current device states when updating settings."""
        if 'available_devices' not in new_settings or 'available_devices' not in self.current_settings:
            return
            
        # Create a map of device roles to states from current settings
        current_states = {}
        for device in self.current_settings['available_devices']:
            if 'role' in device and 'state' in device:
                current_states[device['role']] = device['state']
        
        # Apply current states to new settings
        for device in new_settings['available_devices']:
            if 'role' in device and device['role'] in current_states:
                device['state'] = current_states[device['role']]

    async def get_measurements(self) -> Optional[Tuple[float, float, float]]:
        """Get measurements from the sensor."""
        return await self.sensor.get_measurements()

    def co2_control(self, co2: float, setpoint_max: float) -> None:
        """Control CO2 levels using PID controller."""
        # Log input values
        logger.info(f"CO2 control - Current: {co2} ppm, Setpoint: {setpoint_max} ppm")
        
        # Skip fan control if under manual control
        if self.fan_manual_control:
            logger.info(f"Skipping CO2 control - Fan is under manual control (speed: {self.fan_percentage:.1f}%)")
            return
        
        # Calculate fan speed using PID
        previous_fan_percentage = self.fan_percentage
        self.fan_percentage = float(self.co2_pid(co2))
        
        # Log PID output
        logger.info(f"CO2 PID output - Fan speed: {self.fan_percentage:.1f}% (previous: {previous_fan_percentage:.1f}%)")
        
        # Get CPU temperature and use the higher of CO2 control or CPU cooling needs
        cpu_temp = self.fan.get_cpu_temp()
        if cpu_temp and cpu_temp > 70:  # CPU getting too hot
            logger.info(f"CPU temperature high ({cpu_temp}°C) - using auto control for fan")
            self.fan.auto_control()  # Let auto control take over
        else:
            logger.info(f"Setting fan speed to {self.fan_percentage:.1f}% based on CO2 control")
            self.fan.set_speed(self.fan_percentage)  # Normal CO2 control
            
        # Always update fan speed in settings.json
        asyncio.create_task(self.update_fan_settings_in_background())

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
                    # Synchronize actual device state with our tracking
                    await self.sync_device_states()
                else:
                    logger.error("Failed to connect to heater")
        except Exception as e:
            logger.error(f"Error initializing devices: {e}")

    async def sync_device_states(self):
        """Synchronize actual device states with our tracking and settings.json."""
        try:
            logger.info("Synchronizing device states with physical devices...")
            
            # Sync heater state
            if self.heater_ip:
                actual_heater_state = await self.tapo.get_device_state(self.heater_ip)
                if actual_heater_state is not None:
                    logger.info(f"Actual heater state: {'ON' if actual_heater_state else 'OFF'}")
                    # Update our tracking
                    self.heater_on = actual_heater_state
                    # Update settings.json using SettingsManager
                    await self.settings_manager.set_device_state('heater', actual_heater_state)
                else:
                    logger.warning("Could not get heater state - device may be offline")
            
            # Sync humidifier state
            if self.humidifier_ip:
                actual_humidifier_state = await self.tapo.get_device_state(self.humidifier_ip)
                if actual_humidifier_state is not None:
                    logger.info(f"Actual humidifier state: {'ON' if actual_humidifier_state else 'OFF'}")
                    # Update our tracking
                    self.humidifier_on = actual_humidifier_state
                    # Update settings.json using SettingsManager
                    await self.settings_manager.set_device_state('humidifier', actual_humidifier_state)
                else:
                    logger.warning("Could not get humidifier state - device may be offline")
                    
            logger.info("Device state synchronization complete")
        except Exception as e:
            logger.error(f"Error synchronizing device states: {e}")

    async def set_humidifier_state(self, state: bool) -> bool:
        """Set humidifier state.
        
        Args:
            state: True to turn on, False to turn off
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Apply debouncing to prevent rapid state changes
        current_time = time.time()
        if current_time - self.humidifier_last_change < self.device_debounce_time:
            # Only log if trying to change state
            if state != self.humidifier_on:
                logger.debug(f"Skipping humidifier state change to {state} (debounce active)")
            return False
            
        if self.humidifier_ip:
            try:
                # Only update if state is changing
                if state != self.humidifier_on:
                    # First update the physical device
                    success = await self.tapo.set_device_state(self.humidifier_ip, state)
                    
                    if success:
                        self.humidifier_on = state
                        self.humidifier_last_change = current_time
                        logger.info(f"Humidifier state set to: {'ON' if state else 'OFF'}")
                        
                        # Update state in settings.json using SettingsManager
                        await self.settings_manager.set_device_state('humidifier', state)
                        return True
                    else:
                        logger.error(f"Failed to set humidifier state to {'ON' if state else 'OFF'}")
                        return False
                else:
                    # State already matches what was requested
                    return True
            except Exception as e:
                logger.error(f"Error setting humidifier state: {e}")
                return False
        else:
            logger.warning("No humidifier IP available")
            return False

    async def set_heater_state(self, state: bool) -> bool:
        """Set heater state.
        
        Args:
            state: True to turn on, False to turn off
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Apply debouncing to prevent rapid state changes
        current_time = time.time()
        if current_time - self.heater_last_change < self.device_debounce_time:
            # Only log if trying to change state
            if state != self.heater_on:
                logger.debug(f"Skipping heater state change to {state} (debounce active)")
            return False
            
        if self.heater_ip:
            try:
                # Only update if state is changing
                if state != self.heater_on:
                    # Update the physical device
                    success = await self.tapo.set_device_state(self.heater_ip, state)
                    
                    if success:
                        # Update internal state tracking
                        self.heater_on = state
                        self.heater_last_change = current_time
                        logger.info(f"Heater state set to: {'ON' if state else 'OFF'}")
                        
                        # Update state in settings.json using SettingsManager
                        await self.settings_manager.set_device_state('heater', state)
                        return True
                    else:
                        logger.error(f"Failed to set heater state to {'ON' if state else 'OFF'}")
                        return False
                else:
                    # State already matches what was requested
                    return True
            except Exception as e:
                logger.error(f"Error setting heater state: {e}")
                return False
        else:
            logger.warning("No heater IP available")
            return False
    
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
            
            # Get hysteresis value from settings
            hysteresis = self.current_settings.get('humidifier', {}).get('rh_hysteresis', 2.0)
            
            # Skip humidity control if RH is above setpoint (with hysteresis)
            if current_rh >= (setpoint - hysteresis):
                # Only log if we're turning off the humidifier
                if self.humidifier_on or self.humidifier_bursting:
                    logger.info(f"RH ({current_rh}%) is above setpoint minus hysteresis ({setpoint - hysteresis}%), turning humidifier OFF")
                await self.set_humidifier_state(False)  # Ensure humidifier is off
                self.humidifier_bursting = False  # Reset bursting state
                return
            
            # Only activate if RH is significantly below setpoint
            if current_rh < (setpoint - hysteresis):
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
                    logger.info(f"Starting humidifier burst for {burst_duration:.1f}s (RH: {current_rh}%, target: {setpoint}%)")
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
            
            # Ensure settings.json is updated to match the actual state
            # Create a background task to update settings.json
            asyncio.create_task(self._ensure_heater_state_in_settings(bool(state)))
            
        except Exception as e:
            logger.error(f"❌ Error logging heater state: {e}")
            
    async def _ensure_heater_state_in_settings(self, state: bool) -> None:
        """Ensure the heater state in settings.json matches the actual state."""
        try:
            # Check current state in settings
            current_state = await self.settings_manager.get_device_state('heater')
            
            # If state doesn't match, update it
            if current_state != state:
                logger.warning(f"Heater state mismatch: InfluxDB has {'ON' if state else 'OFF'}, but settings.json has {'ON' if current_state else 'OFF'}")
                
                # Update settings.json
                success = await self.settings_manager.set_device_state('heater', state)
                if success:
                    logger.info(f"Successfully synchronized heater state in settings.json to {'ON' if state else 'OFF'}")
                else:
                    logger.error(f"Failed to synchronize heater state in settings.json")
        except Exception as e:
            logger.error(f"Error ensuring heater state in settings: {e}")

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

        # ... rest of control logic ...

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
                success = await self.set_heater_state(False)
                if success:
                    logger.info("✓ Heater turned off")
                else:
                    logger.warning("⚠ Could not turn off heater")
            except Exception as e:
                logger.error(f"❌ Error turning off heater: {e}")
                
            try:
                success = await self.set_humidifier_state(False)
                if success:
                    logger.info("✓ Humidifier turned off")
                else:
                    logger.warning("⚠ Could not turn off humidifier")
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
            temp_high = setpoint + hysteresis
            
            # Determine if heater should be on or off
            should_heat = temperature < temp_low
            
            # Only change state if needed
            if should_heat != self.heater_on:
                # First update the physical device and internal state
                success = await self.set_heater_state(should_heat)
                
                if success:
                    logger.info(f"Heater turned {'ON' if should_heat else 'OFF'} - Temp: {temperature}°C (Target: {setpoint}°C ±{hysteresis}°C)")
                    
                    # Log the heater state to InfluxDB
                    self.log_heater_state(1 if should_heat else 0, temperature)
                    
                    # Directly update settings.json to ensure it's in sync
                    settings_updated = await self.settings_manager.set_device_state('heater', should_heat)
                    if not settings_updated:
                        logger.error(f"Failed to update heater state in settings.json to {'ON' if should_heat else 'OFF'}")
                        
                        # Try one more time after a short delay
                        await asyncio.sleep(1)
                        retry_success = await self.settings_manager.set_device_state('heater', should_heat)
                        if retry_success:
                            logger.info(f"Successfully updated heater state in settings.json to {'ON' if should_heat else 'OFF'} on retry")
                        else:
                            logger.error(f"Failed to update heater state in settings.json even after retry")
                else:
                    logger.error(f"Failed to set heater state to {'ON' if should_heat else 'OFF'}")
                    
                    # Check if the device is online
                    is_online = await self.tapo.check_device_online(self.heater_ip)
                    if not is_online:
                        logger.error(f"Heater device appears to be offline. Please check the physical device and network connection.")
                    
                    # Try to resync device states
                    await self.sync_device_states()
            
            # Force an immediate check if the setpoint has changed significantly
            # This ensures the heater responds quickly to large setpoint changes
            if abs(temperature - setpoint) > hysteresis * 2:
                logger.info(f"Large temperature difference detected: current={temperature}°C, setpoint={setpoint}°C")
                # Force heater state update based on current conditions
                # Use the same hysteresis logic as in the regular check, don't just compare to setpoint
                should_heat = temperature < temp_low
                
                # Only update if state is different from current state
                if should_heat != self.heater_on:
                    # First update the physical device and internal state
                    success = await self.set_heater_state(should_heat)
                    
                    if success:
                        logger.info(f"Heater state forced to {'ON' if should_heat else 'OFF'} due to large setpoint change")
                        
                        # Log the heater state to InfluxDB after forced update
                        self.log_heater_state(1 if should_heat else 0, temperature)
                        
                        # Directly update settings.json to ensure it's in sync
                        settings_updated = await self.settings_manager.set_device_state('heater', should_heat)
                        if not settings_updated:
                            logger.error(f"Failed to update heater state in settings.json to {'ON' if should_heat else 'OFF'} after forced change")
                            
                            # Try one more time after a short delay
                            await asyncio.sleep(1)
                            retry_success = await self.settings_manager.set_device_state('heater', should_heat)
                            if retry_success:
                                logger.info(f"Successfully updated heater state in settings.json to {'ON' if should_heat else 'OFF'} on retry after forced change")
                            else:
                                logger.error(f"Failed to update heater state in settings.json even after retry after forced change")
                    else:
                        logger.error(f"Failed to force heater state to {'ON' if should_heat else 'OFF'}")
                        
                        # Check if the device is online
                        is_online = await self.tapo.check_device_online(self.heater_ip)
                        if not is_online:
                            logger.error(f"Heater device appears to be offline. Please check the physical device and network connection.")
                
        except Exception as e:
            logger.error(f"Error in temperature control: {e}")

    async def diagnose_sensor(self):
        """Print sensor diagnostic information."""
        try:
            if not self.sensor:
                logger.warning("No sensor available for diagnosis")
                return
                
            logger.info("\n=== SCD30 Sensor Diagnosis ===")
            # Remove direct access to underlying sensor methods
            logger.info(f"Measurement Interval: {self.sensor.measurement_interval}s")
            logger.info(f"Last Measurement Time: {datetime.fromtimestamp(self.sensor._last_measurement_time).strftime('%H:%M:%S') if self.sensor._last_measurement_time else 'None'}")
            logger.info(f"Consecutive Failures: {self.sensor._consecutive_failures}")
            logger.info(f"Sensor Initialized: {self.sensor._initialized}")
            logger.info("============================\n")
            
        except Exception as e:
            logger.error(f"Error during sensor diagnosis: {e}")

    async def initialize_sensor(self) -> bool:
        """Initialize the sensor with proper waiting for data readiness."""
        try:
            logger.info("Initializing SCD30 sensor...")
            
            # Get measurement interval from settings
            measurement_interval = self.current_settings['sensor']['measurement_interval']
            
            # Update the sensor's measurement interval if needed
            if self.sensor.measurement_interval != measurement_interval:
                logger.info(f"Updating sensor measurement interval to {measurement_interval}s")
                self.sensor.set_measurement_interval(measurement_interval)
            
            # Check if sensor is available
            if not self.sensor.is_available():
                logger.warning("SCD30 sensor not immediately available. Waiting for it to become ready...")
                
                # Wait for the sensor to become available (up to 30 seconds)
                for attempt in range(15):
                    await asyncio.sleep(2)  # Wait 2 seconds between checks
                    if self.sensor.is_available():
                        logger.info("SCD30 sensor is now available")
                        break
                    logger.debug(f"Waiting for sensor to become available (attempt {attempt+1}/15)...")
                else:
                    logger.error("Failed to initialize SCD30 sensor after multiple attempts")
                    return False
            
            # Try to get a test measurement
            logger.info("Waiting for first measurement...")
            for attempt in range(5):
                measurement = await self.sensor.get_measurements()
                if measurement:
                    co2, temp, rh = measurement
                    logger.info(f"First measurement successful: CO2={co2:.1f}ppm, Temp={temp:.1f}°C, RH={rh:.1f}%")
                    
                    # Print sensor diagnostic information
                    await self.diagnose_sensor()
                    return True
                
                logger.debug(f"Waiting for first measurement (attempt {attempt+1}/5)...")
                await asyncio.sleep(measurement_interval)
            
            logger.warning("Could not get initial measurement, but continuing anyway")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing sensor: {e}")
            return False

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

    async def update_fan_settings_in_background(self):
        """Update fan settings in the background."""
        try:
            # Update the fan speed in settings.json using the settings manager
            await self.settings_manager.set_fan_settings(
                manual_control=self.fan_manual_control,
                speed=self.fan_percentage
            )
            logger.info(f"Updated fan settings in settings.json: manual={self.fan_manual_control}, speed={self.fan_percentage:.1f}%")
        except Exception as e:
            logger.error(f"Error updating fan settings in settings.json: {e}")

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
        
        # Start the controller (initialize async resources)
        await controller.start()
        
        # Initialize devices
        await controller.initialize_devices()
        
        # Initialize sensor
        logger.info("\n=== Initializing SCD30 Sensor ===")
        sensor_ok = await controller.initialize_sensor()
        if not sensor_ok:
            logger.error("Failed to initialize sensor, continuing without sensor...")
        
        logger.info("\n=== Starting Main Control Loop ===")
        
        consecutive_failures = 0
        max_consecutive_failures = 5
        last_sync_time = 0
        sync_interval = 300  # Sync device states every 5 minutes
        
        while True:  # Main control loop
            try:
                # Periodically sync device states with physical devices
                current_time = time.time()
                if current_time - last_sync_time > sync_interval:
                    await controller.sync_device_states()
                    last_sync_time = current_time
                
                # Get current measurements
                measurements = await controller.get_measurements()
                if measurements:
                    co2, temp, rh = measurements
                    logger.debug(f"Measurements - Temp: {temp}°C, RH: {rh}%, CO2: {co2}ppm")
                    
                    # Reset failure counter on successful measurement
                    consecutive_failures = 0
                    
                    # Control temperature
                    await controller.temperature_control(temp)
                    
                    # Control humidity
                    await controller.humidity_control(rh)
                    
                    # Control CO2/ventilation
                    logger.info(f"Calling CO2 control with CO2={co2} ppm")
                    controller.co2_control(co2, controller.current_settings['environment']['phases'][controller.current_settings['environment']['current_phase']]['co2_setpoint'])
                    logger.info(f"CO2 control completed - Fan speed now: {controller.fan_percentage:.1f}%")
                    
                    # Check for configuration updates
                    await controller.check_config_updates()
                    
                    # Log data to InfluxDB
                    await controller.log_data(co2, temp, rh)
                else:
                    # Increment failure counter
                    consecutive_failures += 1
                    logger.warning(f"Failed to get measurements (failure #{consecutive_failures})")
                    
                    # Try to reinitialize sensor after multiple consecutive failures
                    if consecutive_failures >= max_consecutive_failures:
                        logger.warning(f"Too many consecutive failures ({consecutive_failures}). Attempting to reinitialize sensor...")
                        await controller.initialize_sensor()
                        consecutive_failures = 0  # Reset counter after reinitialization attempt
                
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
