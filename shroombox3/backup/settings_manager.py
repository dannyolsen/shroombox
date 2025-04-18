import os
import json
import asyncio
import logging
import copy
import time
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
        
        # Track file modification time to detect external changes
        self._last_known_mtime = 0
        
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
        
        # Check if file has been modified externally
        try:
            current_mtime = os.path.getmtime(self.config_path)
            if current_mtime > self._last_known_mtime:
                logger.info(f"Detected external change to settings.json (mtime: {current_mtime} > {self._last_known_mtime})")
                force_reload = True
                self._last_known_mtime = current_mtime
        except Exception as e:
            logger.warning(f"Error checking file modification time: {e}")
        
        # Return cached settings if available and not expired and not forced to reload
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
                
                # Update last known modification time
                try:
                    self._last_known_mtime = os.path.getmtime(self.config_path)
                except Exception as e:
                    logger.warning(f"Error updating file modification time: {e}")
                
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
                logger.info(f"SettingsManager: Saving settings to: {self.config_path}")
                
                # Check if file has been modified externally since last read
                try:
                    current_mtime = os.path.getmtime(self.config_path)
                    if current_mtime > self._last_known_mtime:
                        logger.warning(f"File has been modified externally since last read. Loading latest version before saving.")
                        with open(self.config_path, 'r') as f:
                            current_settings = json.load(f)
                        
                        # Merge our changes with the current file content
                        # This is a simplified merge that prioritizes our changes
                        # A more sophisticated merge might be needed for complex scenarios
                        self._deep_merge_with_priority(current_settings, settings)
                        settings = current_settings
                        self._last_known_mtime = current_mtime
                except Exception as e:
                    logger.warning(f"Error checking for external modifications: {e}")
                
                # Log the current phase and setpoints
                if 'environment' in settings and 'current_phase' in settings['environment']:
                    current_phase = settings['environment']['current_phase']
                    logger.info(f"SettingsManager: Current phase: {current_phase}")
                    
                    if 'phases' in settings['environment'] and current_phase in settings['environment']['phases']:
                        phase_data = settings['environment']['phases'][current_phase]
                        logger.info(f"SettingsManager: Phase data to save: {phase_data}")
                
                # Create a backup of the file first
                backup_path = f"{self.config_path}.bak"
                try:
                    if os.path.exists(self.config_path):
                        with open(self.config_path, 'r') as src:
                            with open(backup_path, 'w') as dst:
                                dst.write(src.read())
                        logger.info(f"SettingsManager: Created backup at {backup_path}")
                except Exception as e:
                    logger.warning(f"SettingsManager: Failed to create backup: {e}")
                
                # Log device states before saving
                for device in settings.get('available_devices', []):
                    if 'role' in device and 'state' in device:
                        logger.info(f"SettingsManager: Device {device['role']} state before save: {'ON' if device['state'] else 'OFF'}")
                
                # Write settings to a temporary file first
                temp_path = f"{self.config_path}.tmp"
                logger.info(f"SettingsManager: Writing to temporary file: {temp_path}")
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
                    
                    # Check if the CO2 setpoint was saved correctly
                    if 'environment' in settings and 'current_phase' in settings['environment']:
                        current_phase = settings['environment']['current_phase']
                        if 'phases' in settings['environment'] and current_phase in settings['environment']['phases']:
                            if 'co2_setpoint' in settings['environment']['phases'][current_phase]:
                                expected_co2 = settings['environment']['phases'][current_phase]['co2_setpoint']
                                actual_co2 = temp_settings['environment']['phases'][current_phase]['co2_setpoint']
                                logger.info(f"SettingsManager: CO2 setpoint in temp file - Expected: {expected_co2}, Actual: {actual_co2}")
                                if expected_co2 != actual_co2:
                                    logger.error(f"SettingsManager: CO2 setpoint mismatch in temp file!")
                                    return False
                except Exception as e:
                    logger.error(f"SettingsManager: Error verifying temp file: {e}")
                    return False
                
                # Rename the temporary file to the actual settings file
                logger.info(f"SettingsManager: Renaming temp file to {self.config_path}")
                os.replace(temp_path, self.config_path)
                logger.info(f"SettingsManager: Successfully renamed temp file to {self.config_path}")
                
                # Update cache and last modification time
                self._settings_cache = copy.deepcopy(settings)
                self._last_read_time = asyncio.get_event_loop().time()
                try:
                    self._last_known_mtime = os.path.getmtime(self.config_path)
                except Exception as e:
                    logger.warning(f"Error updating file modification time after save: {e}")
                
                # Verify the file was written correctly
                try:
                    with open(self.config_path, 'r') as f:
                        saved_settings = json.load(f)
                    
                    # Check if device states were saved correctly
                    for device in saved_settings.get('available_devices', []):
                        if 'role' in device and 'state' in device:
                            logger.info(f"SettingsManager: Device {device['role']} state after save: {'ON' if device['state'] else 'OFF'}")
                    
                    # Check if the CO2 setpoint was saved correctly
                    if 'environment' in saved_settings and 'current_phase' in saved_settings['environment']:
                        current_phase = saved_settings['environment']['current_phase']
                        if 'phases' in saved_settings['environment'] and current_phase in saved_settings['environment']['phases']:
                            if 'co2_setpoint' in saved_settings['environment']['phases'][current_phase]:
                                saved_co2 = saved_settings['environment']['phases'][current_phase]['co2_setpoint']
                                expected_co2 = settings['environment']['phases'][current_phase]['co2_setpoint']
                                logger.info(f"SettingsManager: CO2 setpoint after save - Expected: {expected_co2}, Saved: {saved_co2}")
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
                current_settings = await self.load_settings(force_reload=True)
                
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
    
    def _deep_merge_with_priority(self, target: Dict[str, Any], priority_source: Dict[str, Any]) -> None:
        """Deep merge priority_source dict into target dict, with priority_source taking precedence.
        
        Args:
            target: Target dict to merge into
            priority_source: Source dict to merge from, with priority
        """
        # This is similar to _deep_merge but ensures priority_source values take precedence
        for key, value in priority_source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                # Recursively merge dicts
                self._deep_merge_with_priority(target[key], value)
            else:
                # Replace or add value from priority source
                target[key] = value
    
    async def get_device_state(self, role: str) -> Optional[bool]:
        """Get the state of a device by role.
        
        Args:
            role: The role of the device (e.g., 'heater', 'humidifier')
            
        Returns:
            bool: The device state, or None if not found
        """
        try:
            settings = await self.load_settings()
            
            # Find the device
            for device in settings.get('available_devices', []):
                if device.get('role') == role:
                    return device.get('state')
            
            return None
        except Exception as e:
            logger.error(f"Error getting device state: {e}")
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
                
                # Update cache and last modification time
                self._settings_cache = copy.deepcopy(settings)
                self._last_read_time = asyncio.get_event_loop().time()
                try:
                    self._last_known_mtime = os.path.getmtime(self.config_path)
                except Exception as e:
                    logger.warning(f"Error updating file modification time after device state change: {e}")
                
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
        """Get device information by role.
        
        Args:
            role: The role of the device (e.g., 'heater', 'humidifier')
            
        Returns:
            Dict: Device information, or None if not found
        """
        settings = await self.load_settings()
        
        for device in settings.get('available_devices', []):
            if device.get('role') == role:
                return copy.deepcopy(device)
        
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