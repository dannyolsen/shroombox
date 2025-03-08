"""
Device Manager for Shroombox
Manages all hardware devices to ensure only one component can access them at a time.
"""

import os
import time
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from utils.singleton import singleton
from managers.settings_manager import SettingsManager
from devices.fan import NoctuaFan
from devices.smart_plug import TapoController

# Set up logging
logger = logging.getLogger('shroombox.device')

@singleton
class DeviceManager:
    """
    Manager for all hardware devices.
    
    This class provides a unified interface for accessing and controlling
    all hardware devices in the system.
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialize the device manager.
        
        Args:
            config_path: Path to the settings.json file. If None, uses default path.
        """
        logger.info("Initializing Device Manager")
        
        # Set up config path
        if config_path is None:
            # Use path relative to the script location
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.config_path = os.path.join(script_dir, 'config', 'settings.json')
        else:
            self.config_path = config_path
            
        logger.info(f"Using config path: {self.config_path}")
        
        # Initialize settings manager first
        self.settings_manager = SettingsManager(self.config_path)
        
        # Initialize Tapo controller
        self.tapo = TapoController()
        
        # Initialize fan
        self.fan = NoctuaFan()  # Fan controller
        
        # Import and initialize sensor
        from devices.simple_sensor import SimpleSCD30Controller
        self.sensor = SimpleSCD30Controller()  # CO2 sensor
        
        # State tracking
        self.fan_percentage = 0
        self._last_fan_update = 0
        self._fan_update_interval = 1  # Update settings every 1 second
        
        # Device state tracking
        self.heater_state = False
        self.humidifier_state = False
        
        # Measurement cache
        self._measurement_cache = {
            'co2': None,
            'temperature': None,
            'humidity': None,
            'timestamp': None,
            'cache_ttl': 60  # Cache time-to-live in seconds
        }
        
        # Lock for thread-safe operations
        self._fan_lock = asyncio.Lock()
        self._sensor_lock = asyncio.Lock()
        
        # Initialization flag
        self._initialized = False
        
        logger.info("Device Manager initialized successfully")
        
    async def initialize(self):
        """Initialize the device manager asynchronously."""
        if not self._initialized:
            try:
                # Load initial settings
                settings = await self.settings_manager.load_settings(force_reload=True)
                
                # Initialize sensor settings
                await self.sensor.load_settings()
                
                # Load initial device states
                for device in settings.get('available_devices', []):
                    if device.get('role') in ['heater', 'humidifier']:
                        if device.get('role') == 'heater':
                            self.heater_state = device.get('state', False)
                        else:
                            self.humidifier_state = device.get('state', False)
                
                self._initialized = True
                logger.info("Device Manager async initialization complete")
            except Exception as e:
                logger.error(f"Error during async initialization: {e}")
                raise
    
    async def get_settings(self) -> Dict[str, Any]:
        """
        Get current settings from settings manager.
        
        Returns:
            Dict[str, Any]: Current settings
        """
        return await self.settings_manager.load_settings()
    
    async def save_settings(self, settings: Dict[str, Any]) -> bool:
        """
        Save settings using settings manager.
        
        Args:
            settings: Settings to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        return await self.settings_manager.save_settings(settings)
    
    async def set_fan_speed(self, speed: float) -> None:
        """
        Set fan speed and update settings.
        
        Args:
            speed: Fan speed percentage (0-100)
        """
        async with self._fan_lock:
            try:
                # Set fan speed
                self.fan.set_speed(speed)
                self.fan_percentage = speed
                
                # Update settings every second (configured by _fan_update_interval)
                current_time = time.time()
                if current_time - self._last_fan_update >= self._fan_update_interval:
                    self._last_fan_update = current_time
                    
                    # Update settings using update_settings to properly merge changes
                    updates = {
                        'fan': {
                            'speed': speed
                        }
                    }
                    
                    success = await self.settings_manager.update_settings(updates)
                    if success:
                        logger.debug(f"Updated fan speed in settings to {speed}%")
                    else:
                        logger.error("Failed to save settings with updated fan speed")
            except Exception as e:
                logger.error(f"Error setting fan speed: {e}")
    
    def get_fan_speed(self) -> float:
        """
        Get the current fan speed as a percentage.
        
        Returns:
            float: Current fan speed (0-100)
        """
        if hasattr(self, 'fan') and self.fan:
            return self.fan.get_speed()
        return 0.0
    
    async def get_device_state(self, role: str) -> Optional[bool]:
        """
        Get the state of a device by role.
        
        Args:
            role: The role of the device (e.g., 'heater', 'humidifier')
            
        Returns:
            Optional[bool]: The device state, or None if not found
        """
        try:
            # Ensure initialization is complete
            if not self._initialized:
                await self.initialize()
                
            # Get device state from settings
            return await self.settings_manager.get_device_state(role)
        except Exception as e:
            logger.error(f"Error getting {role} state: {e}")
            return None
    
    def get_cpu_temperature(self) -> Optional[float]:
        """
        Get CPU temperature.
        
        Returns:
            Optional[float]: CPU temperature in Celsius, or None if unavailable
        """
        return self.fan.get_cpu_temp()
    
    async def get_measurements(self) -> Optional[Tuple[float, float, float]]:
        """
        Get measurements from the sensor.
        
        Returns:
            Optional[Tuple[float, float, float]]: (CO2, temperature, humidity) or None if failed
        """
        async with self._sensor_lock:
            # Try to get fresh measurements from the sensor
            measurements = await self.sensor.get_measurements()
            
            # If we got valid measurements, update the cache
            if measurements is not None:
                co2, temp, rh = measurements
                self._measurement_cache['co2'] = co2
                self._measurement_cache['temperature'] = temp
                self._measurement_cache['humidity'] = rh
                self._measurement_cache['timestamp'] = time.time()
                logger.debug(f"Updated measurement cache with fresh data: CO2={co2}, Temp={temp}, RH={rh}")
                return measurements
            
            # If no fresh measurements, check if we have valid cached data
            if self._measurement_cache['timestamp'] is not None:
                # Check if cache is still valid
                cache_age = time.time() - self._measurement_cache['timestamp']
                if cache_age < self._measurement_cache['cache_ttl']:
                    logger.debug(f"Using cached measurements (age: {cache_age:.1f}s)")
                    return (
                        self._measurement_cache['co2'],
                        self._measurement_cache['temperature'],
                        self._measurement_cache['humidity']
                    )
                else:
                    logger.debug(f"Cached measurements expired (age: {cache_age:.1f}s)")
            
            # No valid measurements available
            return None
            
    async def get_cached_measurements(self) -> Dict[str, Any]:
        """
        Get the cached measurements with additional metadata.
        
        Returns:
            Dict[str, Any]: Dictionary with cached measurements and metadata
        """
        result = {
            'co2': self._measurement_cache['co2'],
            'temperature': self._measurement_cache['temperature'],
            'humidity': self._measurement_cache['humidity'],
            'timestamp': self._measurement_cache['timestamp'],
            'is_cached': True
        }
        
        if self._measurement_cache['timestamp'] is not None:
            result['age'] = time.time() - self._measurement_cache['timestamp']
            result['is_fresh'] = result['age'] < self._measurement_cache['cache_ttl']
        else:
            result['age'] = None
            result['is_fresh'] = False
            
        return result
    
    def get_heater_state(self) -> bool:
        """
        Get the current heater state.
        
        Returns:
            bool: True if ON, False if OFF
        """
        if hasattr(self, 'heater_state'):
            return self.heater_state
        return False
    
    def get_humidifier_state(self) -> bool:
        """
        Get the current humidifier state.
        
        Returns:
            bool: True if ON, False if OFF
        """
        if hasattr(self, 'humidifier_state'):
            return self.humidifier_state
        return False
    
    async def set_device_state(self, role: str, state: bool) -> bool:
        """
        Set the state of a device by role.
        
        Args:
            role: The role of the device (e.g., 'heater', 'humidifier')
            state: The state to set (True for on, False for off)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure initialization is complete
            if not self._initialized:
                await self.initialize()
                
            # Get device IP from settings
            settings = await self.settings_manager.load_settings()
            device = next((d for d in settings.get('available_devices', []) 
                         if d.get('role') == role), None)
            
            if not device or 'ip' not in device:
                logger.error(f"No {role} device found in settings or missing IP")
                return False
                
            # Update the physical device using TapoController
            success = await self.tapo.set_device_state(device['ip'], state)
            
            if success:
                # Update internal state tracking
                if role == 'heater':
                    self.heater_state = state
                elif role == 'humidifier':
                    self.humidifier_state = state
                    
                # Update the state in settings.json
                await self.settings_manager.set_device_state(role, state)
                logger.info(f"Successfully set {role} state to {'ON' if state else 'OFF'}")
                return True
            else:
                logger.error(f"Failed to set {role} state to {'ON' if state else 'OFF'}")
                return False
        except Exception as e:
            logger.error(f"Error setting {role} state: {e}")
            return False
    
    def cleanup(self):
        """Clean up resources before shutdown."""
        logger.info("Cleaning up device resources")
        
        # Stop the fan
        try:
            self.fan.cleanup()
            logger.info("Fan cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up fan: {e}")
        
        # Clean up sensor
        try:
            self.sensor.cleanup()
            logger.info("Sensor cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up sensor: {e}")

    async def log_heater_state(self, state: bool, current_temp: Optional[float], desired_state: Optional[bool] = None, reason: Optional[str] = None, timestamp: Optional[datetime] = None) -> None:
        """Log heater state to InfluxDB using the device-centered structure."""
        try:
            from managers.influxdb_manager import influxdb_manager
            settings = await self.settings_manager.load_settings()
            current_phase = settings['environment']['current_phase']
            phase_settings = settings['environment']['phases'][current_phase]
            
            # Get setpoint from current phase
            setpoint = None
            if 'temp_setpoint' in phase_settings:
                setpoint = float(phase_settings['temp_setpoint'])
            
            # Log to InfluxDB using the device-centered structure
            await influxdb_manager.log_heater_state(
                state=state,
                current_temp=current_temp,
                setpoint=setpoint,
                phase=current_phase,
                desired_state=desired_state,
                reason=reason,
                timestamp=timestamp
            )
        except Exception as e:
            logger.error(f"Error logging heater state to InfluxDB: {e}")

    async def log_humidifier_state(self, state: bool, current_rh: Optional[float], desired_state: Optional[bool] = None, 
                              reason: Optional[str] = None, burst_duration: float = 0.0, timestamp: Optional[datetime] = None) -> None:
        """Log humidifier state to InfluxDB using the device-centered structure."""
        try:
            from managers.influxdb_manager import influxdb_manager
            settings = await self.settings_manager.load_settings()
            current_phase = settings['environment']['current_phase']
            phase_settings = settings['environment']['phases'][current_phase]
            
            # Get setpoint from current phase
            setpoint = None
            if 'rh_setpoint' in phase_settings:
                setpoint = float(phase_settings['rh_setpoint'])
            
            # Log to InfluxDB using the device-centered structure
            await influxdb_manager.log_humidifier_state(
                state=state,
                current_rh=current_rh,
                setpoint=setpoint,
                phase=current_phase,
                desired_state=desired_state,
                reason=reason,
                burst_duration=burst_duration,
                timestamp=timestamp
            )
        except Exception as e:
            logger.error(f"Error logging humidifier state to InfluxDB: {e}")
            
    async def log_pid_metrics(self, controller_type: str, pid_output: float, error: float,
                          p_term: float = None, i_term: float = None, d_term: float = None,
                          process_variable: float = None, setpoint: float = None,
                          timestamp: Optional[datetime] = None) -> None:
        """
        Log PID controller metrics to InfluxDB using the device-centered structure.
        
        Args:
            controller_type: Type of controller (e.g., 'humidity', 'temperature')
            pid_output: Output value calculated by the PID controller
            error: Current error value (setpoint - process_variable)
            p_term: Proportional term of the PID output (optional)
            i_term: Integral term of the PID output (optional)
            d_term: Derivative term of the PID output (optional)
            process_variable: Current value of the process variable (optional)
            setpoint: Target setpoint (optional)
            timestamp: Timestamp for the measurement (optional)
        """
        try:
            from managers.influxdb_manager import influxdb_manager
            settings = await self.settings_manager.load_settings()
            current_phase = settings['environment']['current_phase']
            
            # Map controller type to appropriate measurement and use the device-centered structure
            await influxdb_manager.log_pid_metrics(
                controller_type=controller_type,
                pid_output=pid_output,
                error=error,
                p_term=p_term,
                i_term=i_term,
                d_term=d_term,
                process_variable=process_variable,
                setpoint=setpoint,
                phase=current_phase,
                timestamp=timestamp
            )
        except Exception as e:
            logger.error(f"Error logging PID metrics to InfluxDB: {e}")
            
    async def log_burst_cycle(self, cycle_active: bool, burst_progress: float = 0.0, 
                         time_remaining: float = 0.0, burst_duration: float = 0.0,
                         humidity: float = None, pid_output: float = None,
                         cycle_id: str = None, timestamp: Optional[datetime] = None) -> None:
        """
        Log humidifier burst cycle information to InfluxDB using the device-centered structure.
        
        Args:
            cycle_active: Whether a burst cycle is currently active
            burst_progress: Percentage completion of the current burst (0-100)
            time_remaining: Time remaining in the current burst cycle in seconds
            burst_duration: Total duration of the burst cycle in seconds
            humidity: Current humidity level during the burst cycle (optional)
            pid_output: PID output that determined the burst duration (optional)
            cycle_id: Unique identifier for the burst cycle (optional)
            timestamp: Timestamp for the measurement (optional)
        """
        try:
            from managers.influxdb_manager import influxdb_manager
            settings = await self.settings_manager.load_settings()
            current_phase = settings['environment']['current_phase']
            
            # Log to InfluxDB using the device-centered structure
            await influxdb_manager.log_burst_cycle(
                cycle_active=cycle_active,
                burst_progress=burst_progress,
                time_remaining=time_remaining,
                burst_duration=burst_duration,
                humidity=humidity,
                pid_output=pid_output,
                phase=current_phase,
                cycle_id=cycle_id,
                timestamp=timestamp
            )
        except Exception as e:
            logger.error(f"Error logging burst cycle data to InfluxDB: {e}")

# Create a global instance for easy access
device_manager = DeviceManager() 