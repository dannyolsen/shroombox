#!../../shroombox2/env_shrooms/bin/python3
### IMPORTS ###
import asyncio
import os
import time
from datetime import datetime
from typing import Optional, Tuple
import json
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

import noctua_pwm as fan
from scd30_i2c import SCD30
from simple_pid import PID
from tapo import ApiClient

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
        self.scd30 = self._init_scd30()
        self.humidity_last_called = time.time()
        self.fan_percentage = 0
        
        # Initialize PIDs
        self.co2_pid = PID(-1, -0.01, 0, setpoint=GROW_SETPOINTS.co2_max)
        self.co2_pid.output_limits = (0, 100)
        
        self.cpu_pid = PID(-10, -3, 0.05, setpoint=30)
        self.cpu_pid.output_limits = (0, 100)

        # PID for humidity control - directly controlling burst duration
        self.humidity_pid = PID(
            Kp=2.0,  # Proportional gain
            Ki=0.1,  # Integral gain
            Kd=0.05, # Derivative gain
            setpoint=GROW_SETPOINTS.rh_setpoint,
            output_limits=(HUMIDIFIER_BURST_MIN, HUMIDIFIER_BURST_MAX)
        )
        # Force initial output to minimum burst time
        self.humidity_pid._last_output = HUMIDIFIER_BURST_MIN
        
        # Humidifier state
        self.humidifier_bursting = False
        self.burst_end_time = 0
        self.humidifier_on = False
        
        # Initialize InfluxDB client
        self.influx_client = InfluxDBClient(
            url="http://localhost:8086",
            token="I4nOLNxdI28X7jcE3rArd4lnAFk09KZ2QLtg8CBP8lhSeFOMm5sn4YdUQ3FCm36lW-22VJLcOeZiEYzOxDZNwA==",
            org="SuperShrooms"
        )
        self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)

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
            # Environment measurements
            env_point = Point("environment") \
                .tag("location", "shroombox") \
                .tag("phase", "growing") \
                .field("co2_ppm", int(co2)) \
                .field("temperature_c", temp) \
                .field("humidity_rh", rh) \
                .field("fan_speed", int(self.fan_percentage))

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
        fan.setFanSpeed(self.fan_percentage)

    async def connect_to_humidifier(self, retries=3):
        """Connect to humidifier with retries."""
        for attempt in range(retries):
            try:
                client = ApiClient("dannyolsen1980@gmail.com", "xerted-6wexwu-nyqraD")
                humidifier = await client.p115("192.168.8.158")
                # Test connection with a simple command
                await humidifier.get_device_info()
                return humidifier
            except Exception as e:
                print(f"Connection attempt {attempt + 1}/{retries} failed: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(1)  # Wait before retry
                else:
                    raise
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
        current_time = time.time()
        time_delta = current_time - self.humidity_last_called

        if time_delta < HUMIDITY_BREAK_TIME:
            return

        try:
            # Get humidifier connection
            humidifier = await self.connect_to_humidifier()
            if not humidifier:
                return

            # Calculate error (setpoint - current_rh)
            error = GROW_SETPOINTS.rh_setpoint - rh
            
            if error > RH_HYSTERESIS:  # Only burst if humidity is too low
                # Calculate burst duration using PID
                burst_duration = self.humidity_pid(rh)
                print(f"\nStarting humidifier burst for {burst_duration:.1f}s (Target RH: {GROW_SETPOINTS.rh_setpoint}%, Current: {rh:.1f}%)")
                
                # Log burst start
                try:
                    burst_start = Point("humidifier_events") \
                        .tag("location", "shroombox") \
                        .tag("phase", "growing") \
                        .tag("event", "burst_start") \
                        .field("planned_duration", float(burst_duration)) \
                        .field("start_rh", rh) \
                        .field("error", error) \
                        .field("setpoint", GROW_SETPOINTS.rh_setpoint)
                    
                    self.write_api.write(
                        bucket="supershrooms",
                        record=burst_start
                    )
                except Exception as e:
                    print(f"Error logging burst start: {e}")

                # Execute burst
                self.humidifier_bursting = True
                start_rh = rh
                await humidifier.on()
                await asyncio.sleep(burst_duration)
                await humidifier.off()
                self.humidifier_bursting = False

                # Wait for humidity to stabilize and measure effect
                end_rh, rh_change = await self.measure_burst_effect(start_rh)
                
                # Log burst results
                try:
                    burst_effect = Point("humidifier_events") \
                        .tag("location", "shroombox") \
                        .tag("phase", "growing") \
                        .tag("event", "burst_effect") \
                        .field("duration", float(burst_duration)) \
                        .field("start_rh", start_rh) \
                        .field("end_rh", end_rh) \
                        .field("rh_change", rh_change) \
                        .field("pid_p", self.humidity_pid.components[0]) \
                        .field("pid_i", self.humidity_pid.components[1]) \
                        .field("pid_d", self.humidity_pid.components[2])
                    
                    self.write_api.write(
                        bucket="supershrooms",
                        record=burst_effect
                    )
                except Exception as e:
                    print(f"Error logging burst effect: {e}")

                self.humidity_last_called = current_time

                # After measuring effect
                print(f"Burst complete: RH changed from {start_rh:.1f}% to {end_rh:.1f}% (Δ{rh_change:+.1f}%)")

        except Exception as e:
            print(f"Error in humidity control: {e}")
            self.humidifier_bursting = False
            try:
                await humidifier.off()  # Safety: ensure humidifier is off
            except:
                pass

async def main():
    """Main control loop."""
    controller = EnvironmentController()
    print("\n=== SuperShrooms Control System Started ===")
    print(f"RH Setpoint: {GROW_SETPOINTS.rh_setpoint}%")
    print(f"CO2 Setpoint: {GROW_SETPOINTS.co2_max}ppm")
    print(f"Temperature Range: {GROW_SETPOINTS.temp_min}°C - {GROW_SETPOINTS.temp_max}°C")
    print("=" * 40 + "\n")
    
    try:
        while True:
            measurements = await controller.read_measurements()
            if measurements:
                co2, temp, rh = measurements
                print(f"\rCO2: {co2:4.0f}ppm | Temp: {temp:4.1f}°C | RH: {rh:4.1f}% | Fan: {controller.fan_percentage:3.0f}% | {'MISTING' if controller.humidifier_bursting else 'IDLE':8}", end='', flush=True)
                controller.co2_control(co2, GROW_SETPOINTS.co2_max)
                asyncio.create_task(controller.humidity_control(rh))
            await asyncio.sleep(0.2)
    except asyncio.CancelledError:
        print("\nShutting down gracefully...")
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    finally:
        # Cleanup
        try:
            print("\nPerforming cleanup...")
            # Turn off the humidifier
            client = ApiClient("dannyolsen1980@gmail.com", "xerted-6wexwu-nyqraD")
            humidifier = await client.p115("192.168.8.158")
            await humidifier.off()
            
            # Stop the fan
            fan.setFanSpeed(0)
            
            # Close InfluxDB client
            controller.influx_client.close()
            
            print("Cleanup completed successfully")
        except Exception as e:
            print(f"Error during cleanup: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
