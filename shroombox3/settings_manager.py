import os
import json
import asyncio
import logging
import copy
from typing import Dict, Any, Optional, List
import logging_setup

logger = logging_setup.get_logger('shroombox.settings')

class SettingsManager:
    """Manages reading and writing to settings.json file."""
    
    def __init__(self, config_path: str = None):
        """Initialize the settings manager.
        
        Args:
            config_path: Path to the settings.json file. If None, uses default path.
        """
        if config_path is None:
            # Use path relative to the script location
            script_dir = os.path.dirname(os.path.abspath(__file__))
            self.config_path = os.path.join(script_dir, 'config', 'settings.json')
        else:
            self.config_path = config_path
            
        logger.info(f"Settings manager initialized with config path: {self.config_path}")
        
        # Cache for settings to avoid frequent file reads
        self._settings_cache = None
        self._last_read_time = 0
        self._cache_ttl = 5  # Cache TTL in seconds
        
        # Lock for thread-safe file operations
        self._file_lock = asyncio.Lock()
    
    async def load_settings(self, force_reload: bool = False) -> Dict[str, Any]:
        """Load settings from the config file.
        
        Args:
            force_reload: If True, ignores the cache and reloads from file
            
        Returns:
            Dict containing the settings
        """
        current_time = asyncio.get_event_loop().time()
        
        # Return cached settings if available and not expired
        if not force_reload and self._settings_cache is not None and current_time - self._last_read_time < self._cache_ttl:
            return copy.deepcopy(self._settings_cache)
        
        try:
            async with self._file_lock:
                logger.debug(f"Loading settings from: {self.config_path}")
                with open(self.config_path, 'r') as f:
                    settings = json.load(f)
                
                # Update cache
                self._settings_cache = copy.deepcopy(settings)
                self._last_read_time = current_time
                
                # Ensure numeric values are properly converted
                if 'environment' in settings and 'phases' in settings['environment']:
                    for phase_name, phase_data in settings['environment']['phases'].items():
                        if 'temp_setpoint' in phase_data:
                            phase_data['temp_setpoint'] = float(phase_data['temp_setpoint'])
                        if 'rh_setpoint' in phase_data:
                            phase_data['rh_setpoint'] = float(phase_data['rh_setpoint'])
                        if 'co2_setpoint' in phase_data:
                            phase_data['co2_setpoint'] = int(phase_data['co2_setpoint'])
                
                return settings
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            # Return empty dict if file can't be read
            return {}
    
    async def save_settings(self, settings: Dict[str, Any]) -> bool:
        """Save settings to the config file.
        
        Args:
            settings: Dict containing the settings to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            async with self._file_lock:
                logger.debug(f"SettingsManager: Saving settings to: {self.config_path}")
                
                # Create a backup of the file first
                backup_path = f"{self.config_path}.bak"
                try:
                    if os.path.exists(self.config_path):
                        with open(self.config_path, 'r') as src:
                            with open(backup_path, 'w') as dst:
                                dst.write(src.read())
                        logger.debug(f"SettingsManager: Created backup at {backup_path}")
                except Exception as e:
                    logger.warning(f"SettingsManager: Failed to create backup: {e}")
                
                # Log device states before saving
                for device in settings.get('available_devices', []):
                    if 'role' in device and 'state' in device:
                        logger.debug(f"SettingsManager: Device {device['role']} state before save: {'ON' if device['state'] else 'OFF'}")
                
                # Write settings to a temporary file first
                temp_path = f"{self.config_path}.tmp"
                with open(temp_path, 'w') as f:
                    json.dump(settings, f, indent=4)
                
                # Verify the temporary file
                try:
                    with open(temp_path, 'r') as f:
                        temp_settings = json.load(f)
                    
                    # Check if all device states match
                    for device in settings.get('available_devices', []):
                        if 'role' in device and 'state' in device:
                            role = device['role']
                            expected_state = device['state']
                            
                            # Find the same device in temp settings
                            for temp_device in temp_settings.get('available_devices', []):
                                if temp_device.get('role') == role:
                                    actual_state = temp_device.get('state')
                                    if actual_state != expected_state:
                                        logger.error(f"SettingsManager: State mismatch in temp file! Expected {role} to be {'ON' if expected_state else 'OFF'} but got {'ON' if actual_state else 'OFF'}")
                                        return False
                except Exception as e:
                    logger.error(f"SettingsManager: Error verifying temp file: {e}")
                    return False
                
                # Rename the temporary file to the actual settings file
                os.replace(temp_path, self.config_path)
                logger.debug(f"SettingsManager: Successfully renamed temp file to {self.config_path}")
                
                # Update cache
                self._settings_cache = copy.deepcopy(settings)
                self._last_read_time = asyncio.get_event_loop().time()
                
                # Verify the file was written correctly
                try:
                    with open(self.config_path, 'r') as f:
                        saved_settings = json.load(f)
                    
                    # Check if device states were saved correctly
                    for device in saved_settings.get('available_devices', []):
                        if 'role' in device and 'state' in device:
                            logger.debug(f"SettingsManager: Device {device['role']} state after save: {'ON' if device['state'] else 'OFF'}")
                except Exception as e:
                    logger.error(f"SettingsManager: Error verifying saved settings: {e}")
                
                return True
        except Exception as e:
            logger.error(f"SettingsManager: Error saving settings: {e}")
            return False
    
    async def update_settings(self, updates: Dict[str, Any], merge: bool = True) -> bool:
        """Update specific settings while preserving the rest.
        
        Args:
            updates: Dict containing the settings to update
            merge: If True, merges with existing settings; if False, replaces them
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if merge:
                # Load current settings
                current_settings = await self.load_settings()
                
                # Deep merge updates into current settings
                self._deep_merge(current_settings, updates)
                
                # Save merged settings
                return await self.save_settings(current_settings)
            else:
                # Replace all settings
                return await self.save_settings(updates)
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            return False
    
    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Deep merge source dict into target dict.
        
        Args:
            target: Target dict to merge into
            source: Source dict to merge from
        """
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                # Recursively merge dicts
                self._deep_merge(target[key], value)
            else:
                # Replace or add value
                target[key] = value
    
    async def get_device_state(self, role: str) -> Optional[bool]:
        """Get the state of a device by role.
        
        Args:
            role: The role of the device (e.g., 'heater', 'humidifier')
            
        Returns:
            bool: The state of the device, or None if not found
        """
        settings = await self.load_settings()
        
        for device in settings.get('available_devices', []):
            if device.get('role') == role and 'state' in device:
                return device['state']
        
        return None
    
    async def set_device_state(self, role: str, state: bool) -> bool:
        """Set the state of a device by role.
        
        Args:
            role: The role of the device (e.g., 'heater', 'humidifier')
            state: The state to set (True for on, False for off)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"SettingsManager: Setting {role} state to {'ON' if state else 'OFF'}")
            settings = await self.load_settings(force_reload=True)
            
            # Find and update the device
            updated = False
            for device in settings.get('available_devices', []):
                if device.get('role') == role:
                    if device.get('state') != state:
                        logger.info(f"SettingsManager: Updating {role} state in settings.json: {'ON' if state else 'OFF'}")
                    device['state'] = state
                    updated = True
            
            if not updated:
                logger.warning(f"No device with role '{role}' found in settings")
                return False
            
            # Save the updated settings with direct file write (not using cache)
            async with self._file_lock:
                logger.info(f"SettingsManager: Writing {role} state directly to {self.config_path}")
                with open(self.config_path, 'w') as f:
                    json.dump(settings, f, indent=4)
                
                # Update cache
                self._settings_cache = copy.deepcopy(settings)
                self._last_read_time = asyncio.get_event_loop().time()
                
                # Verify the file was written correctly
                try:
                    with open(self.config_path, 'r') as f:
                        saved_settings = json.load(f)
                    
                    # Check if device state was saved correctly
                    for device in saved_settings.get('available_devices', []):
                        if device.get('role') == role:
                            actual_state = device.get('state')
                            if actual_state != state:
                                logger.error(f"SettingsManager: State mismatch after save! Expected {role} to be {'ON' if state else 'OFF'} but got {'ON' if actual_state else 'OFF'}")
                                return False
                            else:
                                logger.info(f"SettingsManager: Verified {role} state is now {'ON' if state else 'OFF'} in settings.json")
                                return True
                except Exception as e:
                    logger.error(f"SettingsManager: Error verifying saved settings: {e}")
                    return False
            
            return True
        except Exception as e:
            logger.error(f"SettingsManager: Error setting {role} state in settings: {e}")
            return False
    
    async def get_device_by_role(self, role: str) -> Optional[Dict[str, Any]]:
        """Get a device by role.
        
        Args:
            role: The role of the device (e.g., 'heater', 'humidifier')
            
        Returns:
            Dict: The device, or None if not found
        """
        settings = await self.load_settings()
        
        for device in settings.get('available_devices', []):
            if device.get('role') == role:
                return device
        
        return None
    
    async def get_all_devices(self) -> List[Dict[str, Any]]:
        """Get all devices from settings.
        
        Returns:
            List of device dictionaries
        """
        settings = await self.load_settings()
        return copy.deepcopy(settings.get('available_devices', []))
    
    async def update_device(self, role: str, updates: Dict[str, Any]) -> bool:
        """Update a device's information by role.
        
        Args:
            role: The role of the device (e.g., 'heater', 'humidifier')
            updates: Dict containing the fields to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            settings = await self.load_settings(force_reload=True)
            
            # Find and update the device
            updated = False
            for device in settings.get('available_devices', []):
                if device.get('role') == role:
                    for key, value in updates.items():
                        device[key] = value
                    updated = True
            
            if not updated:
                logger.warning(f"No device with role '{role}' found in settings")
                return False
            
            # Save the updated settings
            return await self.save_settings(settings)
        except Exception as e:
            logger.error(f"Error updating device in settings: {e}")
            return False
    
    async def get_environment_settings(self) -> Dict[str, Any]:
        """Get environment settings.
        
        Returns:
            Dict containing environment settings
        """
        settings = await self.load_settings()
        return copy.deepcopy(settings.get('environment', {}))
    
    async def get_current_phase(self) -> str:
        """Get the current growth phase.
        
        Returns:
            str: The current phase name
        """
        settings = await self.load_settings()
        return settings.get('environment', {}).get('current_phase', 'unknown')
    
    async def get_phase_settings(self, phase: Optional[str] = None) -> Dict[str, Any]:
        """Get settings for a specific phase or the current phase.
        
        Args:
            phase: The phase name, or None for current phase
            
        Returns:
            Dict containing phase settings
        """
        settings = await self.load_settings()
        env_settings = settings.get('environment', {})
        
        if phase is None:
            phase = env_settings.get('current_phase')
        
        return copy.deepcopy(env_settings.get('phases', {}).get(phase, {}))
    
    async def set_current_phase(self, phase: str) -> bool:
        """Set the current growth phase.
        
        Args:
            phase: The phase name to set as current
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            settings = await self.load_settings(force_reload=True)
            
            # Ensure the phase exists
            if phase not in settings.get('environment', {}).get('phases', {}):
                logger.warning(f"Phase '{phase}' does not exist in settings")
                return False
            
            # Update the current phase
            if 'environment' not in settings:
                settings['environment'] = {}
            
            settings['environment']['current_phase'] = phase
            logger.info(f"Setting current phase to: {phase}")
            
            # Save the updated settings
            return await self.save_settings(settings)
        except Exception as e:
            logger.error(f"Error setting current phase: {e}")
            return False
    
    async def invalidate_cache(self) -> None:
        """Invalidate the settings cache, forcing next load to read from file."""
        self._last_read_time = 0
        logger.debug("Settings cache invalidated")
    
    async def get_fan_settings(self) -> Dict[str, Any]:
        """Get fan control settings.
        
        Returns:
            Dict: Fan control settings, or empty dict if not found
        """
        settings = await self.load_settings()
        
        # Return fan settings if they exist, otherwise return default settings
        if 'fan' in settings:
            return settings['fan']
        else:
            # Default fan settings
            return {
                'manual_control': False,
                'speed': 0
            }
    
    async def set_fan_settings(self, manual_control: bool, speed: float) -> bool:
        """Set fan control settings.
        
        Args:
            manual_control: Whether the fan is under manual control
            speed: The fan speed (0-100)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"SettingsManager: Setting fan settings - manual: {manual_control}, speed: {speed}")
            settings = await self.load_settings(force_reload=True)
            
            # Create fan settings if they don't exist
            if 'fan' not in settings:
                settings['fan'] = {}
            
            # Update fan settings
            settings['fan']['manual_control'] = manual_control
            settings['fan']['speed'] = speed
            
            # Save the updated settings
            return await self.save_settings(settings)
            
        except Exception as e:
            logger.error(f"SettingsManager: Error setting fan settings: {e}")
            return False

# Example usage
async def test_settings_manager():
    """Test the SettingsManager functionality."""
    manager = SettingsManager()
    
    # Load settings
    settings = await manager.load_settings()
    print(f"Loaded settings: {settings}")
    
    # Get device state
    heater_state = await manager.get_device_state('heater')
    print(f"Heater state: {heater_state}")
    
    # Set device state
    success = await manager.set_device_state('heater', not heater_state)
    print(f"Set heater state: {success}")
    
    # Get current phase
    phase = await manager.get_current_phase()
    print(f"Current phase: {phase}")
    
    # Get phase settings
    phase_settings = await manager.get_phase_settings()
    print(f"Phase settings: {phase_settings}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_settings_manager()) 