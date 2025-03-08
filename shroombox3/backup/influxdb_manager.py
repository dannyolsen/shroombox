"""
InfluxDB Manager for Shroombox
Manages all InfluxDB operations to ensure only one component can access it at a time.
"""

import os
import time
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from utils import logging_setup

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
    
    async def write_measurement(self, co2: float, temp: float, rh: float, fan_speed: float, 
                               heater_state: bool, humidifier_state: bool) -> bool:
        """Write measurements to InfluxDB.
        
        Args:
            co2: CO2 level in ppm
            temp: Temperature in Celsius
            rh: Relative humidity in percent
            fan_speed: Fan speed as percentage (0-100)
            heater_state: Heater state (True=ON, False=OFF)
            humidifier_state: Humidifier state (True=ON, False=OFF)
            
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
                heater_int = 1 if heater_state else 0
                humidifier_int = 1 if humidifier_state else 0
                
                # Create data point with a new measurement name to avoid type conflicts
                point = Point("shroombox_environment") \
                    .field("co2", co2_float) \
                    .field("temperature", temp_float) \
                    .field("humidity", rh_float) \
                    .field("fan_speed", fan_float) \
                    .field("heater", heater_int) \
                    .field("humidifier", humidifier_int) \
                    .time(datetime.utcnow())

                # Write to InfluxDB
                self.write_api.write(
                    bucket=os.getenv('INFLUXDB_BUCKET'),
                    record=point
                )
                
                logger.debug(f"Data written to InfluxDB - CO2: {co2_float}ppm, Temp: {temp_float}°C, RH: {rh_float}%, Fan: {fan_float}%")
                return True
                
            except Exception as e:
                logger.error(f"Error writing to InfluxDB: {e}")
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
                
    async def log_humidifier_state(self, state: bool, current_rh: float, setpoint: float, phase: str, burst_duration: float = 0.0) -> bool:
        """Log humidifier state to InfluxDB.
        
        Args:
            state: True if ON, False if OFF
            current_rh: Current relative humidity
            setpoint: Humidity setpoint
            phase: Current growth phase
            burst_duration: Duration of humidifier burst in seconds
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.write_api:
            logger.error("InfluxDB write_api not initialized")
            return False
            
        async with self._write_lock:
            try:
                # Convert boolean state to integer
                state_int = 1 if state else 0
                
                # Create point with humidifier state
                point = Point("humidifier_state") \
                    .tag("location", "shroombox") \
                    .tag("phase", phase) \
                    .field("state", state_int) \
                    .field("humidity", float(current_rh)) \
                    .field("setpoint", float(setpoint)) \
                    .field("burst_duration", float(burst_duration)) \
                    .time(datetime.utcnow())
                
                # Write to InfluxDB
                self.write_api.write(
                    bucket=os.getenv('INFLUXDB_BUCKET'),
                    record=point
                )
                
                logger.debug(f"Humidifier state logged to InfluxDB - State: {'ON' if state else 'OFF'}, RH: {current_rh}%, Setpoint: {setpoint}%")
                return True
                
            except Exception as e:
                logger.error(f"Error logging humidifier state to InfluxDB: {e}")
                return False
                
    async def log_heater_state(self, state: bool, current_temp: float, setpoint: float, phase: str) -> bool:
        """Log heater state to InfluxDB.
        
        Args:
            state: True if ON, False if OFF
            current_temp: Current temperature
            setpoint: Temperature setpoint
            phase: Current growth phase
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.write_api:
            logger.error("InfluxDB write_api not initialized")
            return False
            
        async with self._write_lock:
            try:
                # Convert boolean state to integer
                state_int = 1 if state else 0
                
                # Create point with heater state
                point = Point("heater_state") \
                    .tag("location", "shroombox") \
                    .tag("phase", phase) \
                    .field("state", state_int) \
                    .field("temperature", float(current_temp)) \
                    .field("setpoint", float(setpoint)) \
                    .time(datetime.utcnow())
                
                # Write to InfluxDB
                self.write_api.write(
                    bucket=os.getenv('INFLUXDB_BUCKET'),
                    record=point
                )
                
                logger.debug(f"Heater state logged to InfluxDB - State: {'ON' if state else 'OFF'}, Temp: {current_temp}°C, Setpoint: {setpoint}°C")
                return True
                
            except Exception as e:
                logger.error(f"Error logging heater state to InfluxDB: {e}")
                return False

# Create a global instance for easy access
influxdb_manager = InfluxDBManager() 