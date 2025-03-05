### IMPORTS ###
import os
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
import scd30_i2c  # Import the module directly

# Set up logging ONCE at the module level
logger = logging.getLogger('shroombox')
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
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Ensure numeric values are properly converted
            if 'environment' in config and 'phases' in config['environment']:
                for phase_name, phase_data in config['environment']['phases'].items():
                    if 'temp_setpoint' in phase_data:
                        phase_data['temp_setpoint'] = float(phase_data['temp_setpoint'])
                    if 'rh_setpoint' in phase_data:
                        phase_data['rh_setpoint'] = float(phase_data['rh_setpoint'])
                    if 'co2_setpoint' in phase_data:
                        phase_data['co2_setpoint'] = int(phase_data['co2_setpoint'])
                    
            return config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}

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
            new_settings = self.load_config()
            if new_settings != self.current_settings:
                logger.info("\nConfig changed, updating settings...")
                self.current_settings = new_settings
                self.update_controllers()
                logger.info(f"New setpoints - RH: {self.humidity_pid.setpoint}%, CO2: {self.co2_pid.setpoint}ppm")
            self.last_config_check = current_time

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
    
    async def set_heater_state(self, state: bool) -> None:
        """Set heater state."""
        if self.heater_ip:
            await self.tapo.set_device_state(self.heater_ip, state)
            self.heater_on = state

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
                await self.control_heater(False)
                logger.info("✓ Heater turned off")
            except Exception as e:
                logger.error(f"❌ Error turning off heater: {e}")
                
            try:
                await self.control_humidifier(False)
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
            temp_high = setpoint + hysteresis
            
            # Determine if heater should be on or off
            should_heat = temperature < temp_low
            
            # Only change state if needed
            if should_heat != self.heater_on:
                await self.set_heater_state(should_heat)
                logger.info(f"Heater turned {'ON' if should_heat else 'OFF'} - Temp: {temperature}°C (Target: {setpoint}°C ±{hysteresis}°C)")
            
            # Force an immediate check if the setpoint has changed significantly
            # This ensures the heater responds quickly to large setpoint changes
            if abs(temperature - setpoint) > hysteresis * 2:
                logger.info(f"Large temperature difference detected: current={temperature}°C, setpoint={setpoint}°C")
                # Force heater state update based on current conditions
                should_heat = temperature < setpoint
                await self.set_heater_state(should_heat)
                logger.info(f"Heater state forced to {'ON' if should_heat else 'OFF'} due to large setpoint change")
                self.heater_on = should_heat
                
        except Exception as e:
            logger.error(f"Error in temperature control: {e}")

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
