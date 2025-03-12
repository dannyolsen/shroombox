"""
Fan Controller for Shroombox
Handles PID control of the fan based on CO2 levels.
"""

import time
import asyncio
import logging
from typing import Optional, Dict, Any, Callable

from simple_pid import PID
from devices.fan import NoctuaFan
from managers.settings_manager import SettingsManager

# Set up logging
logger = logging.getLogger('shroombox.fan')

class FanController:
    """
    Controller for fan speed based on CO2 levels.
    
    This class implements PID control for the fan based on CO2 readings,
    and handles synchronization with settings.json.
    """
    
    def __init__(self, 
                 fan: NoctuaFan, 
                 settings_manager: SettingsManager,
                 set_fan_speed_callback: Optional[Callable[[float], None]] = None):
        """
        Initialize the fan controller.
        
        Args:
            fan: Fan hardware interface
            settings_manager: Settings manager for reading/writing settings
            set_fan_speed_callback: Optional callback for setting fan speed
        """
        self.fan = fan
        self.settings_manager = settings_manager
        self.set_fan_speed_callback = set_fan_speed_callback
        
        # Initialize PID controller with default values
        # These will be updated from settings later
        self.co2_pid = PID(
            Kp=-1.0,  # Negative because higher CO2 -> higher fan speed
            Ki=-0.01,
            Kd=0.0,
            setpoint=1000,  # Default setpoint, will be updated from settings
            sample_time=None,  # We'll handle timing ourselves
            output_limits=(0, 100)  # Fan speed 0-100%
        )
        
        # State tracking
        self.fan_percentage = 0
        self.last_co2_control_time = time.time()
        self._last_fan_update = 0
        self._update_interval = 30  # Update settings every 30 seconds
        
        logger.info("Fan controller initialized")
    
    async def initialize_from_settings(self, settings: Dict[str, Any]) -> None:
        """
        Initialize controller from settings.
        
        Args:
            settings: Current settings dictionary
        """
        try:
            # Get fan speed from settings
            fan_speed = settings.get('fan', {}).get('speed', 0)
            self.fan_percentage = fan_speed
            self.fan.set_speed(fan_speed)
            logger.info(f"Loaded fan speed from settings: {fan_speed}%")
            
            # Get current phase and setpoints
            current_phase = settings.get('environment', {}).get('current_phase', 'colonisation')
            phase_settings = settings.get('environment', {}).get('phases', {}).get(current_phase, {})
            
            # Update CO2 setpoint
            if 'co2_setpoint' in phase_settings:
                self.co2_pid.setpoint = float(phase_settings['co2_setpoint'])
                logger.info(f"Loaded CO2 setpoint from settings: {self.co2_pid.setpoint}ppm")
            
            # Update PID parameters
            co2_pid_settings = settings.get('co2', {}).get('pid', {})
            if co2_pid_settings:
                self.co2_pid.tunings = (
                    float(co2_pid_settings.get('Kp', -1.0)),
                    float(co2_pid_settings.get('Ki', -0.01)),
                    float(co2_pid_settings.get('Kd', 0.0))
                )
                logger.info(f"Loaded CO2 PID parameters from settings: Kp={self.co2_pid.Kp}, Ki={self.co2_pid.Ki}, Kd={self.co2_pid.Kd}")
        
        except Exception as e:
            logger.error(f"Error initializing fan controller from settings: {e}")
    
    def update_co2_control(self, co2: float) -> float:
        """
        Update CO2 control using PID controller.
        
        Args:
            co2: Current CO2 level in ppm
            
        Returns:
            float: New fan speed percentage
        """
        current_time = time.time()
        
        # Check if manual control is enabled
        try:
            # Get the manual control setting directly without using asyncio.run()
            # This is safe because we're just reading a cached value
            settings = self.settings_manager.get_cached_settings()
            manual_control = settings.get('fan', {}).get('manual_control', False)
            
            if manual_control:
                # If manual control is enabled, just return the current fan speed
                logger.info("Manual fan control is enabled, skipping PID control")
                return self.fan_percentage
        except Exception as e:
            logger.error(f"Error checking manual control setting: {e}")
            # Continue with PID control if we can't check the setting
        
        # Calculate time delta since last update (in seconds)
        dt = current_time - self.last_co2_control_time
        
        # Only update if enough time has passed (at least 1 second)
        # This ensures the PID controller runs at regular intervals
        if dt >= 1.0:
            # Update PID with the current CO2 value
            # The PID controller will automatically use the time delta for calculations
            self.fan_percentage = float(self.co2_pid(co2))
            
            # Set fan speed through callback or directly
            if self.set_fan_speed_callback:
                # Create a task to run the callback, but don't wait for it
                # The callback will handle updating settings.json
                asyncio.create_task(self._update_fan_speed(self.fan_percentage))
            else:
                self.fan.set_speed(self.fan_percentage)
            
            # Update the last control time
            self.last_co2_control_time = current_time
            
            # Log PID values for debugging
            logger.debug(f"CO2 PID: CO2={co2}ppm, Setpoint={self.co2_pid.setpoint}ppm, Fan={self.fan_percentage}%, dt={dt:.2f}s")
        
        return self.fan_percentage
    
    async def _update_fan_speed(self, speed: float) -> None:
        """
        Update fan speed through callback.
        
        Args:
            speed: Fan speed percentage
        """
        try:
            await self.set_fan_speed_callback(speed)
        except Exception as e:
            logger.error(f"Error in fan speed callback: {e}")
            # Fallback to direct fan control if callback fails
            self.fan.set_speed(speed)
    
    async def update_fan_speed_in_settings(self, speed: float) -> None:
        """
        Update fan speed in settings.json.
        
        Args:
            speed: Fan speed percentage
        """
        try:
            # Only update occasionally to avoid excessive writes
            # But force update if the difference is significant (>10%)
            current_time = time.time()
            
            # Get current speed from settings
            current_settings = await self.settings_manager.load_settings()
            current_speed = current_settings.get('fan', {}).get('speed', 0)
            
            significant_change = abs(current_speed - speed) > 10
            time_elapsed = current_time - self._last_fan_update >= self._update_interval
            
            if not (significant_change or time_elapsed):
                return
            
            self._last_fan_update = current_time
            
            # Update the speed in settings using update_settings
            logger.info(f"Updating fan speed in settings from {current_speed}% to {speed}%")
            
            updates = {
                'fan': {
                    'speed': speed
                }
            }
            
            success = await self.settings_manager.update_settings(updates)
            if success:
                logger.info(f"Successfully updated fan speed in settings to {speed}%")
            else:
                logger.error(f"Failed to save settings with updated fan speed")
        except Exception as e:
            logger.error(f"Error updating fan speed in settings: {e}")
    
    async def sync_fan_speed(self) -> None:
        """
        Synchronize fan speed between controller and fan.
        """
        try:
            if self.fan:
                # Get the actual fan speed from the fan controller
                actual_speed = self.fan.get_speed()
                
                # If there's a significant difference, update controller.fan_percentage
                if abs(actual_speed - self.fan_percentage) > 5:
                    logger.info(f"Synchronizing fan speed: controller={self.fan_percentage}%, actual={actual_speed}%")
                    self.fan_percentage = actual_speed
                    
                    # Update settings.json
                    await self.update_fan_speed_in_settings(actual_speed)
        except Exception as e:
            logger.error(f"Error synchronizing fan speed: {e}")
    
    def update_setpoint(self, setpoint: float) -> None:
        """
        Update the CO2 setpoint for the PID controller.
        
        Args:
            setpoint: New CO2 setpoint in ppm
        """
        self.co2_pid.setpoint = setpoint
        logger.info(f"Updated CO2 setpoint to {setpoint}ppm")
    
    def update_pid_parameters(self, kp: float, ki: float, kd: float) -> None:
        """
        Update PID controller parameters.
        
        Args:
            kp: Proportional gain
            ki: Integral gain
            kd: Derivative gain
        """
        self.co2_pid.tunings = (kp, ki, kd)
        logger.info(f"Updated PID parameters: Kp={kp}, Ki={ki}, Kd={kd}")
    
    def get_current_speed(self) -> float:
        """
        Get the current fan speed.
        
        Returns:
            float: Current fan speed percentage
        """
        return self.fan_percentage
    
    def set_fan_speed(self, speed_percent):
        """Set the fan speed."""
        if self.fan:
            self.fan.set_speed(speed_percent)
            logger.info(f"Set fan speed to {speed_percent}%")
        else:
            logger.warning("No fan device available")
        
        # Update the speed in settings if callback is provided
        if self.set_fan_speed_callback:
            self.set_fan_speed_callback(speed_percent)
    
    def update_settings(self, settings: dict):
        """Update controller settings from the provided settings dictionary."""
        try:
            # Get current phase settings
            current_phase = settings['environment']['current_phase']
            phase_settings = settings['environment']['phases'][current_phase]
            
            # Update CO2 setpoint from phase settings
            co2_setpoint = float(phase_settings.get('co2_setpoint', 600.0))
            self.update_setpoint(co2_setpoint)
            
            # Update PID parameters if available
            if 'co2' in settings and 'pid' in settings['co2']:
                pid_settings = settings['co2']['pid']
                kp = float(pid_settings.get('Kp', -0.1))
                ki = float(pid_settings.get('Ki', -0.01))
                kd = float(pid_settings.get('Kd', 0.0))
                self.update_pid_parameters(kp, ki, kd)
            
            # Update fan speed if in manual mode
            if settings.get('fan', {}).get('manual_control', False):
                fan_speed = float(settings.get('fan', {}).get('speed', 50.0))
                self.set_fan_speed(fan_speed)
            
            logger.info(f"Updated fan controller settings - CO2 Setpoint: {self.co2_pid.setpoint}ppm, "
                           f"PID: Kp={self.co2_pid.Kp}, Ki={self.co2_pid.Ki}, Kd={self.co2_pid.Kd}")
            
        except (KeyError, ValueError) as e:
            logger.error(f"Error updating fan controller settings: {e}") 