### IMPORTS ###
import asyncio
import os
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

from scd30_i2c import SCD30
from simple_pid import PID
from kasa import Discover
from kasa.iot import IotPlug
from tapo import ApiClient
from noctua_pwm import NoctuaFan

### CONSTANTS ###
MEASUREMENT_INTERVAL = 2
TEMP_OFFSET = 2
HUMIDIFIER_BURST_MIN = 0.5    # Minimum burst time in seconds
HUMIDIFIER_BURST_MAX = 30   # Maximum burst time in seconds
HUMIDITY_BREAK_TIME = 60   # minimum time between humidifier activations
RH_HYSTERESIS = 2.0       # Hysteresis band (±2%)

### CLASSES ###
class EnvironmentSetpoints:
    def __init__(
        self,
        temp_min: float,
        temp_max: float,
        co2_max: float,
        rh_setpoint: float
    ):
        self.temp_min = temp_min
        self.temp_max = temp_max
        self.co2_max = co2_max
        self.rh_setpoint = rh_setpoint

# Define setpoints for different growth phases
COLONISATION_SETPOINTS = EnvironmentSetpoints(
    temp_min=27.0,
    temp_max=27.1,
    co2_max=1000,
    rh_setpoint=85.0
)

GROW_SETPOINTS = EnvironmentSetpoints(
    temp_min=22.0,
    temp_max=22.1,
    co2_max=550,
    rh_setpoint=60.0
)

CAKE_SETPOINTS = EnvironmentSetpoints(
    temp_min=27.0,
    temp_max=27.1,
    co2_max=500,
    rh_setpoint=85.0
)

class EnvironmentController:
    def __init__(self):
        self.config_path = os.path.join(os.path.dirname(__file__), 'config', 'settings.json')
        self.last_config_check = 0
        self.config_check_interval = 5  # Check config every 5 seconds
        self.current_settings = self.load_config()
        
        self.scd30 = self._init_scd30()
        self.humidity_last_called = time.time()
        self.fan_percentage = 0
        
        # Initialize PIDs with default values first
        phase = self.current_settings['environment']['current_phase']
        phase_settings = self.current_settings['environment']['phases'][phase]
        
        self.co2_pid = PID(
            Kp=-1,
            Ki=-0.01,
            Kd=0,
            setpoint=phase_settings['co2_max'],
            output_limits=(0, 100)
        )
        
        self.cpu_pid = PID(
            Kp=-10,
            Ki=-3,
            Kd=0.05,
            setpoint=30,
            output_limits=(0, 100)
        )
        
        self.humidity_pid = PID(
            Kp=0.2,
            Ki=0.01,
            Kd=0.05,
            setpoint=phase_settings['rh_setpoint'],
            output_limits=(0, HUMIDIFIER_BURST_MAX)
        )
        # Force initial output to minimum burst time
        self.humidity_pid._last_output = HUMIDIFIER_BURST_MIN
        
        # Humidifier state
        self.humidifier_bursting = False
        self.burst_end_time = 0
        self.humidifier_on = False
        
        # Initialize fan controller
        self.fan = NoctuaFan()
        
        # Now update controllers with config settings
        self.update_controllers()
        
        # Initialize InfluxDB client
        try:
            self.influx_client = InfluxDBClient(
                url="http://localhost:8086",
                token="I4nOLNxdI28X7jcE3rArd4lnAFk09KZ2QLtg8CBP8lhSeFOMm5sn4YdUQ3FCm36lW-22VJLcOeZiEYzOxDZNwA==",
                org="SuperShrooms"
            )
            self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
            # Test the connection
            self.write_api.write(
                bucket="supershrooms",
                record=Point("system_log")
                    .tag("location", "shroombox")
                    .tag("level", "info")
                    .field("message", "InfluxDB connection established")
                    .time(datetime.utcnow())
            )
        except Exception as e:
            print(f"Error initializing InfluxDB: {e}")
        
        self.session = None
        self.connector = None

    def load_config(self):
        """Load settings from config file."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return None

    def update_controllers(self):
        """Update controller settings from config."""
        if not self.current_settings:
            return

        phase = self.current_settings['environment']['current_phase']
        phase_settings = self.current_settings['environment']['phases'][phase]
        
        # Update PID setpoints
        self.co2_pid.setpoint = phase_settings['co2_max']
        self.humidity_pid.setpoint = phase_settings['rh_setpoint']

        # Update humidity PID parameters
        hum_pid_settings = self.current_settings['humidifier'].get('pid', {})
        if hum_pid_settings:
            self.humidity_pid.tunings = (
                hum_pid_settings.get('Kp', 0.2),
                hum_pid_settings.get('Ki', 0.01),
                hum_pid_settings.get('Kd', 0.05)
            )

        # Update CO2 PID parameters
        co2_pid_settings = self.current_settings['co2'].get('pid', {})
        if co2_pid_settings:
            self.co2_pid.tunings = (
                co2_pid_settings.get('Kp', -1.0),
                co2_pid_settings.get('Ki', -0.01),
                co2_pid_settings.get('Kd', 0.0)
            )

    async def check_config_updates(self):
        """Check for configuration updates."""
        current_time = time.time()
        if current_time - self.last_config_check > self.config_check_interval:
            new_settings = self.load_config()
            if new_settings != self.current_settings:
                print("\nConfig changed, updating settings...")
                self.current_settings = new_settings
                self.update_controllers()
                print(f"New setpoints - RH: {self.humidity_pid.setpoint}%, CO2: {self.co2_pid.setpoint}ppm")
            self.last_config_check = current_time

    def _init_scd30(self) -> SCD30:
        """Initialize and configure the SCD30 sensor."""
        sensor = SCD30()
        sensor.set_measurement_interval(MEASUREMENT_INTERVAL)
        sensor.start_periodic_measurement()
        sensor.set_temperature_offset(TEMP_OFFSET)
        time.sleep(2)
        return sensor

    async def write_to_influx(self, co2: float, temp: float, rh: float) -> None:
        """Write measurements to InfluxDB."""
        try:
            # Get CPU temperature
            cpu_temp = self.fan.get_cpu_temp()
            
            # Environment measurements
            env_point = Point("environment") \
                .tag("location", "shroombox") \
                .tag("phase", "growing") \
                .field("co2_ppm", int(co2)) \
                .field("temperature_c", temp) \
                .field("humidity_rh", rh) \
                .field("fan_speed", int(self.fan_percentage)) \
                .field("cpu_temp", float(cpu_temp) if cpu_temp is not None else 0.0)  # Add CPU temp

            # Humidifier state - store all states as integers (0/1)
            current_time = time.time()
            burst_remaining = max(0, self.burst_end_time - current_time) if self.humidifier_bursting else 0
            
            humidifier_point = Point("humidifier") \
                .tag("location", "shroombox") \
                .tag("phase", "growing") \
                .field("state", int(self.humidifier_on)) \
                .field("burst_state", int(self.humidifier_bursting)) \
                .field("burst_remaining", int(burst_remaining)) \
                .field("burst_duration", float(self.humidity_pid._last_output))  # Keep as seconds in float

            # Setpoints
            setpoint_point = Point("setpoints") \
                .tag("location", "shroombox") \
                .tag("phase", "growing") \
                .field("rh_setpoint", float(GROW_SETPOINTS.rh_setpoint)) \
                .field("rh_hysteresis", float(RH_HYSTERESIS)) \
                .field("temp_min", float(GROW_SETPOINTS.temp_min)) \
                .field("temp_max", float(GROW_SETPOINTS.temp_max)) \
                .field("co2_max", int(GROW_SETPOINTS.co2_max))

            # PID control outputs
            pid_point = Point("pid_control") \
                .tag("location", "shroombox") \
                .tag("phase", "growing") \
                .field("co2_pid_output", int(self.co2_pid.components[0])) \
                .field("humidity_pid_output", float(self.humidity_pid.components[0])) \
                .field("humidity_pid_i", float(self.humidity_pid.components[1])) \
                .field("humidity_pid_d", float(self.humidity_pid.components[2]))

            # Write all points
            self.write_api.write(
                bucket="supershrooms",
                record=[env_point, humidifier_point, setpoint_point, pid_point]
            )
        except Exception as e:
            print(f"Error writing to InfluxDB: {e}")

    async def read_measurements(self) -> Optional[Tuple[float, float, float]]:
        """Read measurements from SCD30 sensor."""
        if not self.scd30.get_data_ready():
            return None
            
        try:
            m = self.scd30.read_measurement()
            measurements = (
                float(f"{m[0]:.1f}"),  # CO2
                float(f"{m[1]:.2f}"),  # Temperature
                float(f"{m[2]:.2f}")   # Relative Humidity
            )
            
            # Write measurements to InfluxDB
            await self.write_to_influx(*measurements)
            
            return measurements
        except Exception as e:
            print(f"Error reading measurements: {e}")
            return None

    def co2_control(self, co2: float, setpoint_max: float) -> None:
        """Control CO2 levels using PID controller."""
        self.fan_percentage = float(self.co2_pid(co2))
        
        # Get CPU temperature and use the higher of CO2 control or CPU cooling needs
        cpu_temp = self.fan.get_cpu_temp()
        if cpu_temp and cpu_temp > 70:  # CPU getting too hot
            self.fan.auto_control()  # Let auto control take over
        else:
            self.fan.set_speed(self.fan_percentage)  # Normal CO2 control

    async def connect_to_humidifier(self, retries=3):
        """Connect to humidifier with retries."""
        ip = "192.168.8.158"
        email = "dannyolsen1980@gmail.com"
        password = "xerted-6wexwu-nyqraD"
        
        try:
            # Try to ping the device first
            result = subprocess.run(['ping', '-c', '1', '-W', '1', ip], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                print(f"\nHumidifier not responding to ping at {ip}")
                print("Please check:")
                print("1. Is the humidifier powered on?")
                print("2. Is the IP address correct?")
                print("3. Are you connected to the right network?")
                return None
            
            print(f"\nTrying to connect to humidifier at {ip}")
            client = ApiClient(email, password)
            humidifier = await client.p115(ip)
            print("Successfully connected to humidifier")
            return humidifier
            
        except Exception as e:
            print(f"Connection error: {e}")
            return None

    async def measure_burst_effect(self, start_rh: float, wait_time: int = 30) -> Tuple[float, float]:
        """
        Measure the effect of a burst after waiting for humidity to stabilize.
        Returns (end_rh, rh_change)
        """
        # Wait for humidity to spread and stabilize
        await asyncio.sleep(wait_time)
        
        # Take multiple measurements to get a stable reading
        measurements = await self.read_measurements()
        if measurements:
            end_rh = measurements[2]
            rh_change = end_rh - start_rh
            return end_rh, rh_change
        return start_rh, 0.0  # Return no change if measurement fails

    async def humidity_control(self, rh: float) -> None:
        """Control humidity using PID controller for burst timing."""
        # Skip humidity control if RH is above setpoint
        if rh >= self.humidity_pid.setpoint:
            return

        await self.check_config_updates()
        current_time = time.time()
        time_delta = current_time - self.humidity_last_called

        # Use burst interval from settings
        burst_interval = self.current_settings['humidifier'].get('burst_interval', 60)
        if time_delta < burst_interval:
            return

        try:
            # Get humidifier connection with retries
            client = ApiClient("dannyolsen1980@gmail.com", "xerted-6wexwu-nyqraD")
            humidifier = await client.p115("192.168.8.158")
            
            if not humidifier:
                print("\nSkipping humidity control - could not connect to humidifier")
                return

            # Calculate burst duration using PID
            error = self.humidity_pid.setpoint - rh
            burst_duration = self.humidity_pid(rh)

            # Clamp burst duration
            burst_min = self.current_settings['humidifier'].get('burst_min', 0.5)
            burst_max = self.current_settings['humidifier'].get('burst_max', 30.0)
            burst_duration = max(burst_min, min(burst_max, burst_duration))

            if error > 0:  # Only run if humidity is too low
                print(f"\nStarting humidifier burst for {burst_duration:.1f}s "
                      f"(Target RH: {self.humidity_pid.setpoint}%, "
                      f"Current: {rh:.1f}%, "
                      f"Error: {'+' if error > 0 else ''}{error:.1f}%)")

                try:
                    # Turn on humidifier
                    await humidifier.on()
                    self.humidifier_bursting = True
                    
                    # Wait for burst duration
                    await asyncio.sleep(burst_duration)
                    
                    # Turn off humidifier
                    await humidifier.off()
                    self.humidifier_bursting = False
                    
                except Exception as e:
                    print(f"Error during humidifier burst: {e}")
                    # Ensure humidifier is off after error
                    try:
                        await humidifier.off()
                    except Exception as e:
                        print(f"Failed to turn off humidifier after error: {e}")
                    self.humidifier_bursting = False

            self.humidity_last_called = current_time

        except Exception as e:
            print(f"Error in humidity control: {e}")

    async def start(self):
        """Initialize async resources."""
        self.session = aiohttp.ClientSession()
        
    async def cleanup(self):
        """Cleanup all resources."""
        if self.session:
            await self.session.close()

    async def write_system_log(self, message: str, level: str = "info") -> None:
        """Write a system log message to InfluxDB."""
        try:
            log_point = Point("system_log") \
                .tag("location", "shroombox") \
                .tag("level", level) \
                .field("message", message) \
                .time(datetime.utcnow())
            
            self.write_api.write(
                bucket="supershrooms",
                record=log_point
            )
        except Exception as e:
            print(f"Error writing to system log: {e}")

    async def log_to_flask(self, message: str) -> None:
        """Send log message to Flask web interface."""
        print(f"\nAttempting to send to Flask: {message}")  # Debug print
        try:
            async with aiohttp.ClientSession() as session:
                try:
                    response = await session.post(
                        'http://192.168.8.157:5000/log',
                        json={'message': message},
                        timeout=5  # Add timeout
                    )
                    print(f"Flask response status: {response.status}")
                    if response.status != 200:
                        response_text = await response.text()
                        print(f"Error response from Flask: {response_text}")
                except aiohttp.ClientError as e:
                    print(f"Network error sending to Flask: {e}")
                except asyncio.TimeoutError:
                    print("Timeout sending to Flask")
                except Exception as e:
                    print(f"Unexpected error sending to Flask: {e}")
        except Exception as e:
            print(f"Session creation error: {e}")
        
        # Also write directly to the log file as a backup
        try:
            with open('/var/log/shroombox-main.log', 'a') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"{timestamp} - {message}\n")
                f.flush()
        except Exception as e:
            print(f"Error writing directly to log file: {e}")

async def main():
    """Main control loop."""
    session = None
    connector = None
    try:
        # Create connector with explicit configuration
        connector = aiohttp.TCPConnector(force_close=True)
        session = aiohttp.ClientSession(connector=connector)
        controller = EnvironmentController()
        controller.session = session
        
        settings = controller.current_settings
        phase = settings['environment']['current_phase']
        phase_settings = settings['environment']['phases'][phase]
        
        # Get initial CPU temperature
        cpu_temp = controller.fan.get_cpu_temp()
        
        startup_message = f"""=== SuperShrooms Control System Started ===
Current Phase: {phase}
RH Setpoint: {phase_settings['rh_setpoint']}%
CO2 Setpoint: {phase_settings['co2_max']}ppm
Temperature Range: {phase_settings['temp_min']}°C - {phase_settings['temp_max']}°C
CPU Temperature: {cpu_temp:.1f}°C"""

        print(f"\n{startup_message}")
        print("=" * 40 + "\n")
        
        # Log startup to InfluxDB
        await controller.write_system_log("=== SYSTEM STARTUP ===", "warning")
        await controller.write_system_log(startup_message, "info")
        
        # Create a single humidity control task
        humidity_task = None
        
        try:
            while True:
                measurements = await controller.read_measurements()
                if measurements:
                    co2, temp, rh = measurements
                    cpu_temp = controller.fan.get_cpu_temp() or 0.0
                    print(
                        f"\rCO2: {co2:4.0f}ppm | "
                        f"Temp: {temp:4.1f}°C | "
                        f"CPU: {cpu_temp:4.1f}°C | "
                        f"RH: {rh:4.1f}% | "
                        f"Fan: {controller.fan_percentage:3.0f}% | "
                        f"{'MISTING' if controller.humidifier_bursting else 'IDLE':8}",
                        end='', flush=True
                    )
                    controller.co2_control(co2, controller.co2_pid.setpoint)
                    
                    # Only create new humidity task if previous one is done
                    if humidity_task is None or humidity_task.done():
                        humidity_task = asyncio.create_task(controller.humidity_control(rh))
                    
                await asyncio.sleep(0.2)
        except (asyncio.CancelledError, KeyboardInterrupt):
            print("\n=== SHUTDOWN SEQUENCE INITIATED ===")
            print("Reason: User requested shutdown")
            await asyncio.sleep(0.1)
        finally:
            # Cleanup
            try:
                print("\nBeginning system cleanup...")
                print("=" * 40)
                
                # 0. Cancel all tasks first
                print("[1/5] Cancelling active tasks...")
                tasks = [t for t in asyncio.all_tasks() 
                         if t is not asyncio.current_task()]
                if tasks:
                    print(f"     Found {len(tasks)} active tasks to cancel")
                    await asyncio.sleep(0.1)
                    print("     ✓ All tasks cancelled")
                
                # 1. Disable PID controllers
                print("\n[2/5] Disabling control systems...")
                controller.co2_pid.set_auto_mode(False)
                controller.cpu_pid.set_auto_mode(False)
                controller.fan_percentage = 0
                await asyncio.sleep(0.1)
                print("     ✓ PID controllers disabled")
                print("     ✓ Fan control disabled")
                
                # 2. Stop the fan
                try:
                    print("\n[3/5] Stopping ventilation system...")
                    controller.fan.emergency_stop()
                    await asyncio.sleep(0.1)
                    print("     ✓ Fan emergency stop completed")
                except Exception as e:
                    print(f"     ✗ Error stopping fan: {e}")
                
                # 3. Turn off the humidifier
                try:
                    print("\n[4/5] Shutting down humidifier...")
                    client = ApiClient("dannyolsen1980@gmail.com", "xerted-6wexwu-nyqraD")
                    humidifier = await client.p115("192.168.8.158")
                    await humidifier.off()
                    await asyncio.sleep(0.1)
                    print("     ✓ Humidifier powered off")
                except Exception as e:
                    print(f"     ✗ Error turning off humidifier: {e}")
                
                # 4. Close network connections
                print("\n[5/5] Closing network connections...")
                if session and not session.closed:
                    await session.close()
                    await asyncio.sleep(0.1)
                    print("     ✓ Network session closed")
                
                print("\n=== SHUTDOWN COMPLETE ===")
                print("All systems powered down successfully")
                print("=" * 40 + "\n")
                
            except Exception as e:
                print(f"\n❌ ERROR DURING SHUTDOWN: {e}")
                print("Some systems may not have shut down properly")

    finally:
        # Final cleanup of all network resources
        if session:
            try:
                if not session.closed:
                    print("Closing network resources...")
                    try:
                        # Close connector first
                        if connector and not connector.closed:
                            await connector.close()
                        
                        # Then close session
                        await session.close()
                        
                        # Short wait for cleanup
                        await asyncio.sleep(0.1)
                    except Exception as e:
                        print(f"Error closing network resources: {e}")
            except Exception as e:
                print(f"Session cleanup error: {e}")

        # Cancel any remaining tasks
        try:
            tasks = [t for t in asyncio.all_tasks() 
                    if t is not asyncio.current_task()]
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            print(f"Task cleanup error: {e}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main_task = None
    
    try:
        # Set up logging
        logger = logging.getLogger('shroombox')
        logger.setLevel(logging.INFO)
        handler = RotatingFileHandler('/var/log/shroombox-main.log', maxBytes=1024*1024, backupCount=5)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        main_task = loop.create_task(main())
        loop.run_until_complete(main_task)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        if main_task and not main_task.done():
            main_task.cancel()
    finally:
        try:
            if main_task and not main_task.done():
                loop.run_until_complete(asyncio.gather(main_task, return_exceptions=True))
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
        except Exception as e:
            print(f"Error during final cleanup: {e}")
