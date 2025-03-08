"""
InfluxDB Manager for Shroombox
Manages all InfluxDB operations to ensure only one component can access it at a time.
"""

import os
import time
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from utils import logging_setup
from utils.influx_schema_validator import influx_schema_validator

# Set up logging
logger = logging_setup.get_logger('shroombox.influxdb')

class InfluxDBManager:
    """Singleton manager for InfluxDB operations."""
    _instance = None
    _initialized = False
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(InfluxDBManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the InfluxDB manager."""
        # Only initialize once
        if InfluxDBManager._initialized:
            return
            
        logger.info("Initializing InfluxDB Manager")
        
        # Initialize InfluxDB client
        try:
            token = os.getenv('INFLUXDB_TOKEN')
            url = os.getenv('INFLUXDB_URL', 'http://localhost:8086')
            org = os.getenv('INFLUXDB_ORG')
            
            # Debug log (mask most of the token for security)
            if token:
                masked_token = token[:5] + "..." + token[-5:] if len(token) > 10 else "***"
                logger.info(f"Using InfluxDB token: {masked_token}")
            else:
                logger.error("INFLUXDB_TOKEN environment variable not set")
                
            logger.info(f"Using InfluxDB URL: {url}")
            logger.info(f"Using InfluxDB org: {org}")
            
            self.influx_client = InfluxDBClient(
                url=url,
                token=token,
                org=org
            )
            self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
            self.query_api = self.influx_client.query_api()
            logger.info("InfluxDB client initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing InfluxDB client: {e}")
            self.influx_client = None
            self.write_api = None
            self.query_api = None
        
        # Lock for thread-safe operations
        self._write_lock = asyncio.Lock()
        
        InfluxDBManager._initialized = True
    
    def write_points(self, data_points: List[Dict[str, Any]]) -> bool:
        """Write data points to InfluxDB.
        
        Args:
            data_points: List of data points to write
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.write_api:
            logger.error("InfluxDB write_api not initialized")
            return False
            
        try:
            # Write to InfluxDB
            self.write_api.write(
                bucket=os.getenv('INFLUXDB_BUCKET'),
                record=data_points
            )
            
            logger.debug(f"Data points written to InfluxDB: {len(data_points)} points")
            return True
            
        except Exception as e:
            logger.error(f"Error writing data points to InfluxDB: {e}")
            return False
    
    async def write_measurement(self, co2: float, temp: float, rh: float, fan_speed: float, 
                               heater_state: bool, humidifier_state: bool, timestamp: Optional[datetime] = None) -> bool:
        """Write environmental measurements to InfluxDB.
        
        Args:
            co2: CO2 level in ppm
            temp: Temperature in Celsius
            rh: Relative humidity in percent
            fan_speed: Fan speed as percentage (0-100)
            heater_state: Heater state (True=ON, False=OFF)
            humidifier_state: Humidifier state (True=ON, False=OFF)
            timestamp: Optional timestamp for the measurement. If None, uses current time.
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.write_api:
            logger.error("InfluxDB write_api not initialized")
            return False
            
        async with self._write_lock:
            try:
                # Ensure all values are of the correct type
                co2_float = float(co2) if co2 is not None else 0.0
                temp_float = float(temp) if temp is not None else 0.0
                rh_float = float(rh) if rh is not None else 0.0
                fan_float = float(fan_speed) if fan_speed is not None else 0.0
                
                # Prepare timestamp
                current_time = datetime.utcnow() if timestamp is None else timestamp
                
                # 1. Log environment data
                environment_fields = {
                    "temperature": temp_float,
                    "humidity": rh_float,
                    "co2": co2_float
                }
                
                environment_tags = {
                    "location": "shroombox"
                }
                
                # Validate and write environment data
                influx_schema_validator.validate_point("environment", environment_fields, environment_tags)
                environment_point = Point("environment")
                
                # Add tags
                for tag_name, tag_value in environment_tags.items():
                    environment_point = environment_point.tag(tag_name, tag_value)
                
                # Add fields
                for field_name, field_value in environment_fields.items():
                    environment_point = environment_point.field(field_name, field_value)
                
                environment_point = environment_point.time(current_time)
                
                # Write environment data
                self.write_api.write(
                    bucket=os.getenv('INFLUXDB_BUCKET'),
                    record=environment_point
                )
                
                # 2. Log fan data
                fan_fields = {
                    "speed": fan_float
                }
                
                fan_tags = {
                    "location": "shroombox",
                    "event_type": "measurement"
                }
                
                # Validate and write fan data
                influx_schema_validator.validate_point("fan", fan_fields, fan_tags)
                fan_point = Point("fan")
                
                # Add tags
                for tag_name, tag_value in fan_tags.items():
                    fan_point = fan_point.tag(tag_name, tag_value)
                
                # Add fields
                for field_name, field_value in fan_fields.items():
                    fan_point = fan_point.field(field_name, field_value)
                
                fan_point = fan_point.time(current_time)
                
                # Write fan data
                self.write_api.write(
                    bucket=os.getenv('INFLUXDB_BUCKET'),
                    record=fan_point
                )
                
                # 3. Log basic device states if changed
                # These are simpler entries just for recording the state
                # More detailed state changes are logged separately
                
                # Heater state
                heater_fields = {
                    "state": 1 if heater_state else 0
                }
                
                heater_tags = {
                    "location": "shroombox",
                    "event_type": "state_poll"  # Regular polling, not a state change event
                }
                
                # Validate and write heater state
                influx_schema_validator.validate_point("heater", heater_fields, heater_tags)
                heater_point = Point("heater")
                
                # Add tags
                for tag_name, tag_value in heater_tags.items():
                    heater_point = heater_point.tag(tag_name, tag_value)
                
                # Add fields
                for field_name, field_value in heater_fields.items():
                    heater_point = heater_point.field(field_name, field_value)
                
                heater_point = heater_point.time(current_time)
                
                # Write heater state
                self.write_api.write(
                    bucket=os.getenv('INFLUXDB_BUCKET'),
                    record=heater_point
                )
                
                # Humidifier state
                humidifier_fields = {
                    "state": 1 if humidifier_state else 0
                }
                
                humidifier_tags = {
                    "location": "shroombox",
                    "event_type": "state_poll"  # Regular polling, not a state change event
                }
                
                # Validate and write humidifier state
                influx_schema_validator.validate_point("humidifier", humidifier_fields, humidifier_tags)
                humidifier_point = Point("humidifier")
                
                # Add tags
                for tag_name, tag_value in humidifier_tags.items():
                    humidifier_point = humidifier_point.tag(tag_name, tag_value)
                
                # Add fields
                for field_name, field_value in humidifier_fields.items():
                    humidifier_point = humidifier_point.field(field_name, field_value)
                
                humidifier_point = humidifier_point.time(current_time)
                
                # Write humidifier state
                self.write_api.write(
                    bucket=os.getenv('INFLUXDB_BUCKET'),
                    record=humidifier_point
                )
                
                logger.debug(f"Environmental data written to InfluxDB - CO2: {co2_float}ppm, Temp: {temp_float}°C, RH: {rh_float}%, Fan: {fan_float}%")
                return True
                
            except Exception as e:
                logger.error(f"Error writing environmental data to InfluxDB: {e}")
                return False
    
    async def get_latest_measurements(self) -> Optional[Dict[str, Any]]:
        """Get latest measurements from InfluxDB.
        
        Returns:
            Optional[Dict[str, Any]]: Dictionary with latest measurements or None if failed
        """
        if not self.query_api:
            logger.error("InfluxDB query_api not initialized")
            return None
            
        try:
            query = f'''
                from(bucket: "{os.getenv('INFLUXDB_BUCKET')}")
                |> range(start: -5m)
                |> filter(fn: (r) => r["_measurement"] == "shroombox_environment")
                |> filter(fn: (r) => r["_field"] == "temperature" or r["_field"] == "humidity" or r["_field"] == "co2" or r["_field"] == "fan_speed")
                |> last()
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
            '''
            
            result = self.query_api.query(query)
            
            if len(result) > 0 and len(result[0].records) > 0:
                record = result[0].records[0]
                return {
                    'temperature': round(float(record.values.get('temperature', 0)), 1),
                    'humidity': round(float(record.values.get('humidity', 0)), 1),
                    'co2': round(float(record.values.get('co2', 0)), 1),
                    'fan_speed': round(float(record.values.get('fan_speed', 0)), 1)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error querying InfluxDB: {e}")
            return None
    
    def cleanup(self):
        """Clean up resources before shutdown."""
        if self.influx_client:
            try:
                self.influx_client.close()
                logger.info("InfluxDB client closed")
            except Exception as e:
                logger.error(f"Error closing InfluxDB client: {e}")
                
    async def log_humidifier_state(self, state: bool, current_rh: Optional[float], setpoint: Optional[float], phase: str, 
                              burst_duration: float = 0.0, desired_state: Optional[bool] = None, reason: Optional[str] = None,
                              timestamp: Optional[datetime] = None) -> bool:
        """Log humidifier state to InfluxDB following the device-centered structure."""
        if not self.write_api:
            logger.error("InfluxDB write_api not initialized")
            return False
            
        async with self._write_lock:
            try:
                # Convert boolean states to integers
                state_int = 1 if state else 0
                desired_state_int = 1 if desired_state else 0 if desired_state is not None else None
                
                # Define measurement name - now always 'humidifier' for the device-centered approach
                measurement_name = "humidifier"
                
                # Create fields dictionary
                fields = {
                    "state": state_int
                }
                
                # Add optional fields if they are not None
                if current_rh is not None:
                    fields["humidity"] = float(current_rh)
                if setpoint is not None:
                    fields["setpoint"] = float(setpoint)
                if burst_duration > 0:
                    fields["burst_duration"] = float(burst_duration)
                if desired_state is not None:
                    fields["desired_state"] = desired_state_int
                
                # Create tags dictionary
                tags = {
                    "location": "shroombox",
                    "phase": phase,
                    "event_type": "state_change"  # This is specifically a state change event
                }
                
                # Add reason tag if provided
                if reason is not None:
                    tags["state_change_reason"] = reason
                
                # Validate against schema
                influx_schema_validator.validate_point(measurement_name, fields, tags)
                
                # Create point
                point = Point(measurement_name)
                
                # Add tags
                for tag_name, tag_value in tags.items():
                    point = point.tag(tag_name, tag_value)
                
                # Add fields
                for field_name, field_value in fields.items():
                    point = point.field(field_name, field_value)
                
                # Set timestamp if provided, otherwise use current time
                if timestamp:
                    point = point.time(timestamp)
                else:
                    point = point.time(datetime.utcnow())
                
                # Write to InfluxDB
                self.write_api.write(
                    bucket=os.getenv('INFLUXDB_BUCKET'),
                    record=point
                )
                
                log_msg = f"Humidifier state logged to InfluxDB - State: {'ON' if state else 'OFF'}"
                if desired_state is not None:
                    log_msg += f", Desired: {'ON' if desired_state else 'OFF'}"
                if current_rh is not None:
                    log_msg += f", RH: {current_rh}%"
                if setpoint is not None:
                    log_msg += f", Setpoint: {setpoint}%"
                if reason is not None:
                    log_msg += f", Reason: {reason}"
                    
                logger.debug(log_msg)
                return True
                
            except Exception as e:
                logger.error(f"Error logging humidifier state to InfluxDB: {e}")
                return False
                
    async def log_heater_state(self, state: bool, current_temp: Optional[float], setpoint: Optional[float], phase: str,
                            desired_state: Optional[bool] = None, reason: Optional[str] = None,
                            timestamp: Optional[datetime] = None) -> bool:
        """Log heater state to InfluxDB following the device-centered structure."""
        if not self.write_api:
            logger.error("InfluxDB write_api not initialized")
            return False
            
        async with self._write_lock:
            try:
                # Convert boolean states to integers
                state_int = 1 if state else 0
                desired_state_int = 1 if desired_state else 0 if desired_state is not None else None
                
                # Define measurement name - now always 'heater' for the device-centered approach
                measurement_name = "heater"
                
                # Create fields dictionary
                fields = {
                    "state": state_int
                }
                
                # Add optional fields if they are not None
                if current_temp is not None:
                    fields["temperature"] = float(current_temp)
                if setpoint is not None:
                    fields["setpoint"] = float(setpoint)
                if desired_state is not None:
                    fields["desired_state"] = desired_state_int
                
                # Create tags dictionary
                tags = {
                    "location": "shroombox",
                    "phase": phase,
                    "event_type": "state_change"  # This is specifically a state change event
                }
                
                # Add reason tag if provided
                if reason is not None:
                    tags["state_change_reason"] = reason
                
                # Validate against schema
                influx_schema_validator.validate_point(measurement_name, fields, tags)
                
                # Create point
                point = Point(measurement_name)
                
                # Add tags
                for tag_name, tag_value in tags.items():
                    point = point.tag(tag_name, tag_value)
                
                # Add fields
                for field_name, field_value in fields.items():
                    point = point.field(field_name, field_value)
                
                # Set timestamp if provided, otherwise use current time
                if timestamp:
                    point = point.time(timestamp)
                else:
                    point = point.time(datetime.utcnow())
                
                # Write to InfluxDB
                self.write_api.write(
                    bucket=os.getenv('INFLUXDB_BUCKET'),
                    record=point
                )
                
                log_msg = f"Heater state logged to InfluxDB - State: {'ON' if state else 'OFF'}"
                if desired_state is not None:
                    log_msg += f", Desired: {'ON' if desired_state else 'OFF'}"
                if current_temp is not None:
                    log_msg += f", Temp: {current_temp}°C"
                if setpoint is not None:
                    log_msg += f", Setpoint: {setpoint}°C"
                if reason is not None:
                    log_msg += f", Reason: {reason}"
                    
                logger.debug(log_msg)
                return True
                
            except Exception as e:
                logger.error(f"Error logging heater state to InfluxDB: {e}")
                return False

    async def log_pid_metrics(self, controller_type: str, pid_output: float, error: float,
                         p_term: float = None, i_term: float = None, d_term: float = None,
                         process_variable: float = None, setpoint: float = None,
                         phase: str = None, timestamp: Optional[datetime] = None) -> bool:
        """
        Log PID controller metrics to InfluxDB following the device-centered structure.
        
        Args:
            controller_type: Type of controller (e.g., 'humidity', 'temperature', 'co2')
            pid_output: Output value calculated by the PID controller
            error: Current error value (setpoint - process_variable)
            p_term: Proportional term of the PID output (optional)
            i_term: Integral term of the PID output (optional)
            d_term: Derivative term of the PID output (optional)
            process_variable: Current value of the process variable (optional)
            setpoint: Target setpoint (optional)
            phase: Current growing phase (optional)
            timestamp: Timestamp for the measurement (optional)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.write_api:
            logger.error("InfluxDB write_api not initialized")
            return False
            
        async with self._write_lock:
            try:
                # Map controller type to measurement name
                # In the device-centered structure, we log PID metrics to the device measurement
                measurement_name = self._get_measurement_for_controller(controller_type)
                
                # Create fields dictionary
                fields = {
                    "pid_output": float(pid_output),
                    "error": float(error)
                }
                
                # Add optional fields if they are not None
                if p_term is not None:
                    fields["p_term"] = float(p_term)
                if i_term is not None:
                    fields["i_term"] = float(i_term)
                if d_term is not None:
                    fields["d_term"] = float(d_term)
                if process_variable is not None:
                    # Use the appropriate field name based on controller type
                    if controller_type == "humidity":
                        fields["humidity"] = float(process_variable)
                    elif controller_type == "temperature":
                        fields["temperature"] = float(process_variable)
                    elif controller_type == "co2":
                        fields["level"] = float(process_variable)
                    else:
                        fields["process_variable"] = float(process_variable)
                if setpoint is not None:
                    fields["setpoint"] = float(setpoint)
                
                # Create tags dictionary
                tags = {
                    "location": "shroombox",
                    "event_type": "pid_update"  # Tag to identify PID update events
                }
                
                # Add phase tag if provided
                if phase is not None:
                    tags["phase"] = phase
                
                # Validate against schema
                influx_schema_validator.validate_point(measurement_name, fields, tags)
                
                # Create point
                point = Point(measurement_name)
                
                # Add tags
                for tag_name, tag_value in tags.items():
                    point = point.tag(tag_name, tag_value)
                
                # Add fields
                for field_name, field_value in fields.items():
                    point = point.field(field_name, field_value)
                
                # Set timestamp if provided, otherwise use current time
                if timestamp:
                    point = point.time(timestamp)
                else:
                    point = point.time(datetime.utcnow())
                
                # Write to InfluxDB
                self.write_api.write(
                    bucket=os.getenv('INFLUXDB_BUCKET'),
                    record=point
                )
                
                logger.debug(f"PID metrics logged to InfluxDB - Controller: {controller_type}, Output: {pid_output}, Error: {error}")
                return True
                
            except Exception as e:
                logger.error(f"Error logging PID metrics to InfluxDB: {e}")
                return False
    
    def _get_measurement_for_controller(self, controller_type: str) -> str:
        """Map controller type to the appropriate measurement name in the device-centered structure."""
        controller_to_measurement = {
            "humidity": "humidifier",
            "temperature": "heater",
            "co2": "co2",
            "fan": "fan"
        }
        return controller_to_measurement.get(controller_type, controller_type)
                
    async def log_burst_cycle(self, cycle_active: bool, burst_progress: float = 0.0, 
                         time_remaining: float = 0.0, burst_duration: float = 0.0,
                         humidity: float = None, pid_output: float = None,
                         phase: str = None, cycle_id: str = None,
                         timestamp: Optional[datetime] = None) -> bool:
        """
        Log humidifier burst cycle information to InfluxDB following the device-centered structure.
        
        Args:
            cycle_active: Whether a burst cycle is currently active
            burst_progress: Percentage completion of the current burst (0-100)
            time_remaining: Time remaining in the current burst cycle in seconds
            burst_duration: Total duration of the burst cycle in seconds
            humidity: Current humidity level during the burst cycle (optional)
            pid_output: PID output that determined the burst duration (optional)
            phase: Current growing phase (optional)
            cycle_id: Unique identifier for the burst cycle (optional)
            timestamp: Timestamp for the measurement (optional)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.write_api:
            logger.error("InfluxDB write_api not initialized")
            return False
            
        async with self._write_lock:
            try:
                # Convert boolean to integer
                cycle_active_int = 1 if cycle_active else 0
                
                # Define measurement name - now 'humidifier' in the device-centered structure
                measurement_name = "humidifier"
                
                # Create fields dictionary
                fields = {
                    "cycle_active": cycle_active_int,
                    "burst_progress": float(burst_progress),
                    "time_remaining": float(time_remaining),
                    "burst_duration": float(burst_duration)
                }
                
                # Add optional fields if they are not None
                if humidity is not None:
                    fields["humidity"] = float(humidity)
                if pid_output is not None:
                    fields["pid_output"] = float(pid_output)
                
                # Create tags dictionary
                tags = {
                    "location": "shroombox",
                    "event_type": "burst_cycle"  # Tag to identify burst cycle events
                }
                
                # Add optional tags if provided
                if phase is not None:
                    tags["phase"] = phase
                if cycle_id is not None:
                    tags["cycle_id"] = cycle_id
                
                # Validate against schema
                influx_schema_validator.validate_point(measurement_name, fields, tags)
                
                # Create point
                point = Point(measurement_name)
                
                # Add tags
                for tag_name, tag_value in tags.items():
                    point = point.tag(tag_name, tag_value)
                
                # Add fields
                for field_name, field_value in fields.items():
                    point = point.field(field_name, field_value)
                
                # Set timestamp if provided, otherwise use current time
                if timestamp:
                    point = point.time(timestamp)
                else:
                    point = point.time(datetime.utcnow())
                
                # Write to InfluxDB
                self.write_api.write(
                    bucket=os.getenv('INFLUXDB_BUCKET'),
                    record=point
                )
                
                logger.debug(f"Burst cycle data logged to InfluxDB - Active: {cycle_active}, Progress: {burst_progress}%, Remaining: {time_remaining}s")
                return True
                
            except Exception as e:
                logger.error(f"Error logging burst cycle data to InfluxDB: {e}")
                return False

# Create a global instance for easy access
influxdb_manager = InfluxDBManager() 