import os
import time
import logging
import asyncio
from typing import Optional, Dict, Any

# Set up logging
logger = logging.getLogger("shroombox.temperature")

class TemperatureController:
    """
    Controller for managing temperature using a heater device.
    
    This class handles the logic for maintaining the desired temperature
    by controlling a heater device.
    """
    
    def __init__(self, device_manager=None):
        """
        Initialize the temperature controller.
        
        Args:
            device_manager: The device manager instance to use for controlling the heater.
                           If None, the controller will operate in simulation mode.
        """
        self.logger = logger
        self.device_manager = device_manager
        
        # Default settings
        self.temp_setpoint = 20.0
        self.temp_hysteresis = 0.5
        self.min_state_change_interval = 1.0  # Reduced from 60.0 to 1.0 seconds
        
        # State tracking
        self.last_control_time = 0
        self.last_state_change = 0
        self.heater_state = False
        
        # Error tracking
        self.consecutive_errors = 0
        self.max_consecutive_errors = 3
        
        self.logger.info("Temperature controller initialized")
        self.logger.info(f"Default settings - Setpoint: {self.temp_setpoint}°C, "
                      f"Hysteresis: {self.temp_hysteresis}°C, "
                      f"Min state change interval: {self.min_state_change_interval}s")
    
    async def update_settings(self, settings: Dict[str, Any]) -> None:
        """
        Update controller settings from the provided settings dictionary.
        
        Args:
            settings: Dictionary containing settings
        """
        try:
            # Get current phase settings
            current_phase = settings['environment']['current_phase']
            phase_settings = settings['environment']['phases'][current_phase]
            
            # Update setpoint from phase settings
            new_setpoint = float(phase_settings.get('temp_setpoint', 20.0))
            new_hysteresis = float(phase_settings.get('temp_hysteresis', 0.5))
            
            # Log if settings changed
            if new_setpoint != self.temp_setpoint or new_hysteresis != self.temp_hysteresis:
                self.logger.info(f"Updating temperature settings:")
                if new_setpoint != self.temp_setpoint:
                    self.logger.info(f"- Setpoint: {self.temp_setpoint}°C -> {new_setpoint}°C")
                if new_hysteresis != self.temp_hysteresis:
                    self.logger.info(f"- Hysteresis: {self.temp_hysteresis}°C -> {new_hysteresis}°C")
                
            self.temp_setpoint = new_setpoint
            self.temp_hysteresis = new_hysteresis
            
            # Reset error counter on successful settings update
            self.consecutive_errors = 0
            
        except (KeyError, ValueError) as e:
            self.consecutive_errors += 1
            self.logger.error(f"Error updating temperature settings: {e}")
            if self.consecutive_errors >= self.max_consecutive_errors:
                self.logger.error("Too many consecutive errors, using default settings")
                self.temp_setpoint = 20.0
                self.temp_hysteresis = 0.5
    
    async def control(self, current_temp: float) -> None:
        """
        Control the temperature by turning the heater on or off.
        
        Args:
            current_temp: Current temperature in Celsius
        """
        try:
            # Get current settings
            settings = await self.device_manager.settings_manager.load_settings()
            current_phase = settings['environment']['current_phase']
            phase_settings = settings['environment']['phases'][current_phase]
            setpoint = float(phase_settings['temp_setpoint'])
            
            # Calculate temperature bounds with hysteresis
            upper_bound = setpoint + self.temp_hysteresis
            lower_bound = setpoint - self.temp_hysteresis
            
            # Get current control state
            control_state = settings.get('control_states', {}).get('heater', {
                'desired_state': False,
                'last_change': None,
                'last_change_reason': None
            })
            
            current_time = time.time()
            new_state = control_state['desired_state']
            reason = None
            
            # Check if enough time has passed since last state change
            if current_time - self.last_state_change >= self.min_state_change_interval:
                # Determine required heater state
                if current_temp < lower_bound and not new_state:
                    new_state = True
                    reason = f"Temperature {current_temp}°C below lower bound {lower_bound}°C"
                    self.logger.info(f"{reason} - turning heater ON")
                    
                elif current_temp > upper_bound and new_state:
                    new_state = False
                    reason = f"Temperature {current_temp}°C above upper bound {upper_bound}°C"
                    self.logger.info(f"{reason} - turning heater OFF")
                
                # If state needs to change, update both device and control state
                if new_state != control_state['desired_state']:
                    # Log the desired state change to InfluxDB
                    await self.device_manager.log_heater_state(
                        state=control_state['desired_state'],  # Current actual state before change
                        current_temp=current_temp,
                        desired_state=new_state,  # New desired state
                        reason=reason
                    )
                    
                    # Update the physical device first
                    success = await self.device_manager.set_device_state('heater', new_state)
                    
                    if success:
                        # Update control state in settings
                        control_state.update({
                            'desired_state': new_state,
                            'last_change': current_time,
                            'last_change_reason': reason
                        })
                        
                        # Save the updated control state
                        settings.setdefault('control_states', {})['heater'] = control_state
                        await self.device_manager.settings_manager.save_settings(settings)
                        
                        # Update last state change time
                        self.last_state_change = current_time
                        self.heater_state = new_state
                        
                        # Log the actual state change to InfluxDB
                        await self.device_manager.log_heater_state(
                            state=new_state,  # New actual state after change
                            current_temp=current_temp,
                            desired_state=new_state,  # Same as actual now
                            reason=reason
                        )
            else:
                # Log current state without changing it
                state_str = "ON" if new_state else "OFF"
                self.logger.debug(f"Temperature {current_temp}°C within bounds ({lower_bound}°C - {upper_bound}°C) - keeping heater {state_str}")
            
        except Exception as e:
            self.logger.error(f"Error in temperature control: {e}")
    
    async def _set_heater_state(self, state: bool) -> None:
        """
        Set the heater state and update the device if available.
        
        Args:
            state: True to turn ON, False to turn OFF
        """
        if self.heater_state == state:
            return  # No change needed
        
        self.heater_state = state
        
        # Update the actual device if device manager is available
        if self.device_manager:
            try:
                success = await self.device_manager.set_device_state("heater", state)
                if success:
                    self.logger.info(f"Set heater to {'ON' if state else 'OFF'}")
                    # Reset error counter on successful state change
                    self.consecutive_errors = 0
            except Exception as e:
                self.logger.error(f"Error setting heater state: {e}")
                self.consecutive_errors += 1
        else:
            self.logger.info(f"Simulation mode: Heater set to {'ON' if state else 'OFF'}")
    
    def get_state(self) -> bool:
        """
        Get the current state of the heater.
        
        Returns:
            bool: True if ON, False if OFF
        """
        return self.heater_state 