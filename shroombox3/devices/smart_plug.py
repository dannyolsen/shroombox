"""
Tapo Smart Plug Controller
Manages TP-Link Tapo smart plugs for controlling heaters and humidifiers.
"""

import os
import asyncio
from dotenv import load_dotenv
from tapo import ApiClient
from kasa import Discover
import logging
import time
from typing import Optional, Dict, Any, List
import json

from devices.base import Device
from utils.singleton import singleton

# Set up logging
logger = logging.getLogger('shroombox.device')

@singleton
class TapoController(Device):
    """
    Controller for TP-Link Tapo smart plugs.
    
    This class implements the Device interface and provides methods
    to control Tapo smart plugs for heaters, humidifiers, etc.
    """
    
    def __init__(self, email: str = None, password: str = None, settings_path: str = None):
        """
        Initialize TapoController with credentials.
        
        Args:
            email: Tapo account email (if None, loads from .env)
            password: Tapo account password (if None, loads from .env)
            settings_path: Path to settings.json file (if None, uses default path)
        """
        # Load credentials from .env if not provided
        if email is None or password is None:
            load_dotenv()
            email = os.getenv('TAPO_EMAIL')
            password = os.getenv('TAPO_PASSWORD')
            
        self.email = email
        self.password = password
        self.client = None
        self._device_cache: Dict[str, Any] = {}  # Cache for device connections
        self._last_session_refresh = 0
        self._initialized = False
        
        # Initialize settings manager
        try:
            from managers.settings_manager import SettingsManager
            self.settings_manager = SettingsManager()
        except ImportError:
            logger.warning("SettingsManager not available, some features will be disabled")
            self.settings_manager = None
        
        # Set default values for configuration parameters
        self._session_ttl = 3600  # Refresh session every hour
        self._connection_retries = 3  # Number of retries for connection issues
        self._retry_delay = 1  # Delay between retries in seconds
        self._discovery_ttl = 300  # Cache discovery results for 5 minutes
        
        # Add discovery cache
        self._discovery_cache: List[Dict[str, Any]] = []
        self._last_discovery = 0
        
        # Load configuration from settings.json if available
        if settings_path is None:
            # Use default path relative to the script location
            script_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(script_dir)  # Go up one level
            settings_path = os.path.join(parent_dir, 'config', 'settings.json')
        
        self._load_config_from_settings(settings_path)
        
        self.initialize()
    
    def _load_config_from_settings(self, settings_path: str) -> None:
        """
        Load configuration parameters from settings.json.
        
        Args:
            settings_path: Path to settings.json file
        """
        try:
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                
                # Load Tapo configuration if available
                if 'tapo' in settings:
                    tapo_config = settings['tapo']
                    
                    # Load session TTL
                    if 'session_ttl' in tapo_config:
                        self._session_ttl = tapo_config['session_ttl']
                        logger.info(f"Using session TTL from settings: {self._session_ttl}s")
                    
                    # Load connection retries
                    if 'connection_retries' in tapo_config:
                        self._connection_retries = tapo_config['connection_retries']
                        logger.info(f"Using connection retries from settings: {self._connection_retries}")
                    
                    # Load discovery TTL
                    if 'discovery_ttl' in tapo_config:
                        self._discovery_ttl = tapo_config['discovery_ttl']
                        logger.info(f"Using discovery TTL from settings: {self._discovery_ttl}s")
        except Exception as e:
            logger.warning(f"Error loading configuration from settings.json: {e}")
            logger.info("Using default configuration values")
    
    def initialize(self) -> bool:
        """
        Initialize the Tapo controller.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        try:
            if not self.email or not self.password:
                logger.error("Tapo credentials not provided")
                return False
                
            self.client = ApiClient(self.email, self.password)
            self._last_session_refresh = time.time()
            self._initialized = True
            logger.info("Tapo controller initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Error initializing Tapo controller: {e}")
            return False
    
    async def _refresh_session_if_needed(self):
        """Refresh the Tapo session if it's expired."""
        if not self.is_initialized:
            logger.warning("Cannot refresh session: controller not initialized")
            if not self.initialize():
                return
                
        current_time = time.time()
        if current_time - self._last_session_refresh > self._session_ttl:
            logger.info("Refreshing Tapo session...")
            try:
                # Create a new client
                self.client = ApiClient(self.email, self.password)
                # Clear device cache to force reconnection
                self._device_cache = {}
                self._last_session_refresh = current_time
                logger.info("Tapo session refreshed successfully")
            except Exception as e:
                logger.error(f"Error refreshing Tapo session: {e}")
                self._initialized = False
    
    async def verify_device(self, device_config: Dict[str, str]) -> bool:
        """
        Verify if a device's stored configuration is still valid.
        
        Args:
            device_config: Device configuration dictionary
            
        Returns:
            bool: True if device is accessible and MAC matches
        """
        if not self.is_initialized:
            logger.warning("Cannot verify device: controller not initialized")
            return False
            
        try:
            await self._refresh_session_if_needed()
            device = await self.client.p115(device_config['ip'])
            info = await device.get_device_info()
            
            # Get MAC address from info (handle different return types)
            device_mac = None
            
            # Handle different return types from the API
            if hasattr(info, 'mac'):
                # Object with attributes
                device_mac = info.mac
            elif isinstance(info, dict) and 'mac' in info:
                # Dictionary
                device_mac = info['mac']
            else:
                # Try to convert to dictionary if it's a custom object
                try:
                    info_dict = vars(info)
                    if 'mac' in info_dict:
                        device_mac = info_dict['mac']
                except:
                    pass
                
                if device_mac is None:
                    logger.error(f"Unexpected device info type: {type(info)}")
                    return False
            
            # Normalize MAC format and compare
            if device_mac.replace(':', '-').upper() == device_config['mac'].upper():
                return True
            else:
                logger.warning(f"MAC mismatch for device {device_config['name']}: "
                              f"expected {device_config['mac']}, got {device_mac}")
                return False
        except Exception as e:
            logger.error(f"Error verifying device {device_config['name']}: {e}")
            return False
    
    async def update_device_info(self, device_config: Dict[str, str]) -> Optional[Dict[str, str]]:
        """
        Update device information.
        
        Args:
            device_config: Device configuration dictionary
            
        Returns:
            Optional[Dict[str, str]]: Updated device configuration or None if failed
        """
        if not self.is_initialized:
            logger.warning("Cannot update device info: controller not initialized")
            return None
            
        try:
            await self._refresh_session_if_needed()
            device = await self.client.p115(device_config['ip'])
            info = await device.get_device_info()
            
            # Extract device information (handle different return types)
            device_mac = None
            device_model = None
            device_type = None
            
            # Handle different return types from the API
            if hasattr(info, 'mac') and hasattr(info, 'model') and hasattr(info, 'type'):
                # Object with attributes
                device_mac = info.mac
                device_model = info.model
                device_type = info.type
            elif isinstance(info, dict) and 'mac' in info and 'model' in info and 'type' in info:
                # Dictionary
                device_mac = info['mac']
                device_model = info['model']
                device_type = info['type']
            else:
                # Try to convert to dictionary if it's a custom object
                try:
                    info_dict = vars(info)
                    if 'mac' in info_dict and 'model' in info_dict and 'type' in info_dict:
                        device_mac = info_dict['mac']
                        device_model = info_dict['model']
                        device_type = info_dict['type']
                except:
                    pass
                
                if device_mac is None:
                    logger.error(f"Unexpected device info type: {type(info)}")
                    return None
            
            # Update device info
            updated_config = device_config.copy()
            updated_config['mac'] = device_mac.replace(':', '-').upper()
            updated_config['model'] = device_model
            updated_config['type'] = device_type
            
            return updated_config
        except Exception as e:
            logger.error(f"Error updating device info for {device_config['name']}: {e}")
            return None
    
    async def find_device_by_mac(self, target_mac: str) -> Optional[str]:
        """
        Find a device's IP address by MAC address.
        
        Args:
            target_mac: MAC address to search for
            
        Returns:
            Optional[str]: IP address if found, None otherwise
        """
        if not self.is_initialized:
            logger.warning("Cannot find device: controller not initialized")
            return None
            
        # Normalize MAC format
        target_mac = target_mac.replace('-', ':').lower()
        
        try:
            # Try Kasa discovery first (faster)
            logger.info(f"Searching for device with MAC {target_mac} using Kasa discovery...")
            devices = await Discover.discover()
            
            for addr, device in devices.items():
                if device.mac.lower() == target_mac:
                    logger.info(f"Found device with MAC {target_mac} at {addr}")
                    return addr
            
            # If not found, try Tapo discovery
            logger.info(f"Device not found with Kasa, trying Tapo discovery...")
            await self._refresh_session_if_needed()
            
            # Get all devices
            devices = await self.discover_devices()
            
            for device in devices:
                device_mac = device.get('mac', '').replace('-', ':').lower()
                if device_mac == target_mac:
                    logger.info(f"Found device with MAC {target_mac} at {device['ip']}")
                    return device['ip']
            
            logger.warning(f"Device with MAC {target_mac} not found")
            return None
        except Exception as e:
            logger.error(f"Error finding device by MAC {target_mac}: {e}")
            return None
    
    async def get_device(self, ip_addr: str):
        """
        Get a device instance by IP address.
        
        Args:
            ip_addr: IP address of the device
            
        Returns:
            Device instance or None if failed
        """
        if not self.is_initialized:
            logger.warning("Cannot get device: controller not initialized")
            return None
            
        # Check if device is in cache
        if ip_addr in self._device_cache:
            return self._device_cache[ip_addr]
            
        # Try to connect to device
        for attempt in range(self._connection_retries):
            try:
                await self._refresh_session_if_needed()
                device = await self.client.p115(ip_addr)
                
                # Cache device
                self._device_cache[ip_addr] = device
                return device
            except Exception as e:
                if attempt < self._connection_retries - 1:
                    logger.warning(f"Error connecting to device at {ip_addr} (attempt {attempt+1}/{self._connection_retries}): {e}")
                    await asyncio.sleep(self._retry_delay)
                else:
                    logger.error(f"Failed to connect to device at {ip_addr} after {self._connection_retries} attempts: {e}")
                    return None
    
    async def set_device_state(self, ip_addr: str, state: bool) -> bool:
        """
        Set device state (on/off).
        
        Args:
            ip_addr: IP address of the device
            state: True for on, False for off
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_initialized:
            logger.warning("Cannot set device state: controller not initialized")
            return False
            
        # Get device
        device = await self.get_device(ip_addr)
        if device is None:
            return False
            
        # Set state
        for attempt in range(self._connection_retries):
            try:
                if state:
                    await device.on()
                    logger.info(f"Turned ON device at {ip_addr}")
                    # Log state change
                    try:
                        from managers.influxdb_manager import influxdb_manager
                        # Determine device role from settings
                        settings = await self.settings_manager.load_settings()
                        device_config = next((d for d in settings.get('available_devices', []) if d.get('ip') == ip_addr), None)
                        if device_config and device_config.get('role'):
                            if device_config['role'] == 'heater':
                                await influxdb_manager.log_heater_state(True, None, None, settings['environment']['current_phase'])
                            elif device_config['role'] == 'humidifier':
                                await influxdb_manager.log_humidifier_state(True, None, None, settings['environment']['current_phase'])
                    except Exception as e:
                        logger.error(f"Error logging state change to InfluxDB: {e}")
                else:
                    await device.off()
                    logger.info(f"Turned OFF device at {ip_addr}")
                    # Log state change
                    try:
                        from managers.influxdb_manager import influxdb_manager
                        # Determine device role from settings
                        settings = await self.settings_manager.load_settings()
                        device_config = next((d for d in settings.get('available_devices', []) if d.get('ip') == ip_addr), None)
                        if device_config and device_config.get('role'):
                            if device_config['role'] == 'heater':
                                await influxdb_manager.log_heater_state(False, None, None, settings['environment']['current_phase'])
                            elif device_config['role'] == 'humidifier':
                                await influxdb_manager.log_humidifier_state(False, None, None, settings['environment']['current_phase'])
                    except Exception as e:
                        logger.error(f"Error logging state change to InfluxDB: {e}")
                return True
            except Exception as e:
                if attempt < self._connection_retries - 1:
                    logger.warning(f"Error setting device state at {ip_addr} (attempt {attempt+1}/{self._connection_retries}): {e}")
                    
                    # Clear cache and try to reconnect
                    if ip_addr in self._device_cache:
                        del self._device_cache[ip_addr]
                    
                    # Get device again
                    device = await self.get_device(ip_addr)
                    if device is None:
                        return False
                        
                    await asyncio.sleep(self._retry_delay)
                else:
                    logger.error(f"Failed to set device state at {ip_addr} after {self._connection_retries} attempts: {e}")
                    return False
    
    async def get_device_info(self, ip_addr: str) -> Optional[Dict]:
        """
        Get device information.
        
        Args:
            ip_addr: IP address of the device
            
        Returns:
            Optional[Dict]: Device information or None if failed
        """
        if not self.is_initialized:
            logger.warning("Cannot get device info: controller not initialized")
            return None
            
        # Get device
        device = await self.get_device(ip_addr)
        if device is None:
            return None
            
        # Get device info
        try:
            info = await device.get_device_info()
            return {
                'device_id': info.device_id,
                'type': info.type,
                'model': info.model,
                'hw_version': info.hw_version,
                'fw_version': info.fw_version,
                'nickname': info.nickname,
                'state': await device.get_device_state()
            }
        except Exception as e:
            logger.error(f"Error getting device info for {ip_addr}: {e}")
            return None
    
    async def discover_devices(self) -> List[Dict[str, Any]]:
        """
        Discover all Tapo devices on the network.
        
        Returns:
            List[Dict[str, Any]]: List of discovered devices
        """
        if not self.is_initialized:
            logger.warning("Cannot discover devices: controller not initialized")
            return []
            
        current_time = time.time()
        if current_time - self._last_discovery > self._discovery_ttl:
            logger.info("Refreshing Tapo discovery cache")
            self._discovery_cache = []
            self._last_discovery = current_time
        
        if self._discovery_cache:
            logger.info("Using cached Tapo discovery results")
            return self._discovery_cache
        
        discovered_devices = []
        
        # Try Kasa discovery first
        try:
            logger.info("Discovering devices using Kasa...")
            kasa_devices = await Discover.discover()
            
            for addr, device in kasa_devices.items():
                try:
                    # Only add P115 devices
                    if 'P115' in device.model:
                        # Get the actual device name by directly querying the device
                        actual_name = None
                        try:
                            # Try to get the device info directly
                            tapo_device = await self.get_device(addr)
                            if tapo_device:
                                device_info = await tapo_device.get_device_info()
                                if device_info and 'alias' in device_info and device_info['alias']:
                                    actual_name = device_info['alias']
                                    logger.info(f"Retrieved actual name from device at {addr}: {actual_name}")
                        except Exception as e:
                            logger.warning(f"Error getting device info for {addr}: {e}")
                        
                        # Use the actual name if available, otherwise use the alias from Kasa
                        name = actual_name or device.alias
                        
                        # If still no name, use a default
                        if not name or name == "":
                            logger.info(f"Device at {addr} has no name, using model and IP")
                            name = f"{device.model} ({addr})"
                        
                        device_info = {
                            'name': name,
                            'ip': addr,
                            'mac': device.mac.upper().replace(':', '-'),
                            'model': device.model,
                            'type': 'SMART.TAPOPLUG',
                            'state': device.is_on
                        }
                        discovered_devices.append(device_info)
                        logger.info(f"Discovered Kasa device: {name} at {addr}")
                except Exception as e:
                    logger.warning(f"Error processing Kasa device at {addr}: {e}")
        except Exception as e:
            logger.warning(f"Error during Kasa discovery: {e}")
        
        # Try Tapo discovery
        try:
            logger.info("Discovering devices using Tapo...")
            await self._refresh_session_if_needed()
            
            # Get all devices from Tapo cloud
            cloud_devices = await self.client.find_devices()
            
            for device in cloud_devices:
                try:
                    # Check if device is already in the list
                    device_mac = device['mac'].upper().replace(':', '-')
                    if not any(d['mac'] == device_mac for d in discovered_devices):
                        # Get the actual device name by directly querying the device
                        actual_name = None
                        try:
                            # Try to get the device info directly
                            tapo_device = await self.get_device(device['ip'])
                            if tapo_device:
                                device_info = await tapo_device.get_device_info()
                                if device_info and 'alias' in device_info and device_info['alias']:
                                    actual_name = device_info['alias']
                                    logger.info(f"Retrieved actual name from device at {device['ip']}: {actual_name}")
                        except Exception as e:
                            logger.warning(f"Error getting device info for {device['ip']}: {e}")
                        
                        # Use the actual name if available, otherwise use the alias from Tapo cloud
                        name = actual_name or device.get('alias')
                        
                        # If still no name, use a default
                        if not name or name == "":
                            logger.info(f"Device at {device['ip']} has no name, using model and IP")
                            name = f"{device.get('model', 'Device')} ({device['ip']})"
                        
                        device_info = {
                            'name': name,
                            'ip': device['ip'],
                            'mac': device_mac,
                            'model': device['model'],
                            'type': device['type'],
                            'state': device['status'] == 1
                        }
                        discovered_devices.append(device_info)
                        logger.info(f"Discovered Tapo device: {name} at {device['ip']}")
                except Exception as e:
                    logger.warning(f"Error processing Tapo device: {e}")
        except Exception as e:
            logger.warning(f"Error during Tapo discovery: {e}")
        
        self._discovery_cache = discovered_devices
        return discovered_devices
    
    async def get_or_update_device(self, device_config: Dict[str, str]) -> Optional[str]:
        """
        Get device IP or update it if needed.
        
        Args:
            device_config: Device configuration dictionary
            
        Returns:
            Optional[str]: IP address if found, None otherwise
        """
        if not self.is_initialized:
            logger.warning("Cannot get or update device: controller not initialized")
            return None
            
        # Check if device is still at the same IP
        if await self.verify_device(device_config):
            return device_config['ip']
            
        # If not, try to find it by MAC
        logger.info(f"Device {device_config['name']} not found at {device_config['ip']}, searching by MAC...")
        new_ip = await self.find_device_by_mac(device_config['mac'])
        
        if new_ip:
            logger.info(f"Found device {device_config['name']} at new IP: {new_ip}")
            return new_ip
        else:
            logger.warning(f"Device {device_config['name']} not found")
            return None
    
    async def find_by_name(self, device_name: str) -> Optional[Dict[str, Any]]:
        """
        Find a device by name.
        
        Args:
            device_name: Name of the device to find
            
        Returns:
            Optional[Dict[str, Any]]: Device information or None if not found
        """
        if not self.is_initialized:
            logger.warning("Cannot find device by name: controller not initialized")
            return None
            
        # Discover all devices
        devices = await self.discover_devices()
        
        # Find device by name
        for device in devices:
            if device['name'].lower() == device_name.lower():
                return device
                
        # If not found by exact match, try partial match
        for device in devices:
            if device_name.lower() in device['name'].lower():
                return device
                
        logger.warning(f"Device with name '{device_name}' not found")
        return None
    
    async def find_by_mac(self, mac_address: str) -> Optional[Dict[str, Any]]:
        """
        Find a device by MAC address.
        
        Args:
            mac_address: MAC address of the device to find
            
        Returns:
            Optional[Dict[str, Any]]: Device information or None if not found
        """
        if not self.is_initialized:
            logger.warning("Cannot find device by MAC: controller not initialized")
            return None
            
        # Normalize MAC format
        mac_address = mac_address.replace('-', ':').lower()
        
        # Discover all devices
        devices = await self.discover_devices()
        
        # Find device by MAC
        for device in devices:
            device_mac = device['mac'].replace('-', ':').lower()
            if device_mac == mac_address:
                return device
                
        logger.warning(f"Device with MAC '{mac_address}' not found")
        return None
    
    async def find_device(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Find a device by name, MAC, or IP address.
        
        Args:
            identifier: Name, MAC, or IP address of the device to find
            
        Returns:
            Optional[Dict[str, Any]]: Device information or None if not found
        """
        # Check if identifier is an IP address
        if identifier.count('.') == 3 and all(part.isdigit() and 0 <= int(part) <= 255 for part in identifier.split('.')):
            # Get device info
            device = await self.get_device(identifier)
            if device:
                info = await device.get_device_info()
                return {
                    'name': info['alias'],
                    'ip': identifier,
                    'mac': info['mac'].upper().replace(':', '-'),
                    'model': info['model'],
                    'type': info['type'],
                    'state': info['state']
                }
            return None
            
        # Check if identifier is a MAC address
        if ':' in identifier or '-' in identifier:
            return await self.find_by_mac(identifier)
            
        # Otherwise, assume it's a name
        return await self.find_by_name(identifier)
    
    async def get_device_state(self, ip: str) -> Optional[bool]:
        """
        Get the current state of a device.
        
        Args:
            ip: IP address of the device
            
        Returns:
            Optional[bool]: True if on, False if off, None if failed
        """
        if not self.is_initialized:
            logger.warning("Cannot get device state: controller not initialized")
            return None
            
        # Get device
        device = await self.get_device(ip)
        if device is None:
            return None
            
        # Get device state
        for attempt in range(self._connection_retries):
            try:
                info = await device.get_device_info()
                
                # Handle different return types from the API
                # The API might return either a dictionary or an object with attributes
                if hasattr(info, 'device_on'):
                    # Object with attributes
                    return info.device_on
                elif isinstance(info, dict) and 'device_on' in info:
                    # Dictionary
                    return info['device_on']
                else:
                    # Try to convert to dictionary if it's a custom object
                    try:
                        info_dict = vars(info)
                        if 'device_on' in info_dict:
                            return info_dict['device_on']
                    except:
                        pass
                    
                    # If all else fails, log the type and return None
                    logger.error(f"Unexpected device info type: {type(info)}")
                    return None
                    
            except Exception as e:
                if attempt < self._connection_retries - 1:
                    logger.warning(f"Error getting device state at {ip} (attempt {attempt+1}/{self._connection_retries}): {e}")
                    
                    # Clear cache and try to reconnect
                    if ip in self._device_cache:
                        del self._device_cache[ip]
                    
                    # Get device again
                    device = await self.get_device(ip)
                    if device is None:
                        return None
                        
                    await asyncio.sleep(self._retry_delay)
                else:
                    logger.error(f"Failed to get device state at {ip} after {self._connection_retries} attempts: {e}")
                    return None
    
    def cleanup(self) -> None:
        """Clean up resources before shutdown."""
        logger.info("Cleaning up Tapo controller")
        self._device_cache = {}
        self._initialized = False
    
    @property
    def is_initialized(self) -> bool:
        """
        Check if the controller is initialized.
        
        Returns:
            bool: True if the controller is initialized, False otherwise
        """
        return self._initialized and self.client is not None
    
    @property
    def name(self) -> str:
        """
        Get the device name.
        
        Returns:
            str: The name of the device
        """
        return "Tapo Smart Plug Controller"
    
    async def monitor_device_states(self, settings_path: str, interval: int = None, shutdown_event=None):
        """
        Periodically monitor device states and update settings.json.
        
        This method runs in the background and checks the state of all devices
        at regular intervals, updating the settings file when changes are detected.
        
        Args:
            settings_path: Path to the settings file
            interval: Monitoring interval in seconds (if None, reads from settings.json)
            shutdown_event: Optional asyncio Event to signal shutdown
        """
        if not self.is_initialized:
            logger.warning("Cannot monitor devices: controller not initialized")
            if not self.initialize():
                return
        
        # If interval is not specified, read it from settings.json
        if interval is None:
            interval = self._get_monitoring_interval_from_settings(settings_path)
        
        logger.info(f"Starting device state monitoring (interval: {interval}s)")
        
        # Track when we last checked the monitoring interval
        last_interval_check = time.time()
        interval_check_frequency = 300  # Check for interval changes every 5 minutes
        
        while True:
            try:
                # Check if shutdown was requested
                if shutdown_event and shutdown_event.is_set():
                    logger.info("Shutdown requested, stopping device monitoring")
                    break
                
                # Load current settings
                try:
                    with open(settings_path, 'r') as f:
                        settings = json.load(f)
                except Exception as e:
                    logger.error(f"Error loading settings file: {e}")
                    settings = {}
                
                # Check if we should update the monitoring interval
                current_time = time.time()
                if current_time - last_interval_check > interval_check_frequency:
                    last_interval_check = current_time
                    new_interval = self._get_monitoring_interval_from_settings(settings_path)
                    if new_interval != interval:
                        logger.info(f"Monitoring interval changed: {interval}s -> {new_interval}s")
                        interval = new_interval
                
                if 'available_devices' not in settings:
                    logger.warning("No available_devices in settings, skipping monitoring cycle")
                    await asyncio.sleep(interval)
                    continue
                
                # Track if any changes were made
                changes_made = False
                
                # Check each device state
                for i, device in enumerate(settings['available_devices']):
                    if 'ip' not in device:
                        logger.warning(f"Device {device.get('name', 'unknown')} has no IP address, skipping")
                        continue
                    
                    # Get current device state
                    current_state = await self.get_device_state(device['ip'])
                    
                    if current_state is None:
                        logger.warning(f"Could not get state for device {device.get('name', device['ip'])}")
                        # Try to find the device by MAC if IP has changed
                        new_ip = await self.find_device_by_mac(device['mac'])
                        if new_ip and new_ip != device['ip']:
                            logger.info(f"Device {device.get('name', device['mac'])} found at new IP: {new_ip} (was {device['ip']})")
                            device['ip'] = new_ip
                            changes_made = True
                            # Try again with new IP
                            current_state = await self.get_device_state(new_ip)
                    
                    # Update state if it has changed
                    if current_state is not None and current_state != device.get('state'):
                        logger.info(f"Device {device.get('name', device['ip'])} state changed: {device.get('state')} -> {current_state}")
                        device['state'] = current_state
                        changes_made = True
                
                # Save settings if changes were made
                if changes_made:
                    try:
                        # Create a backup of the settings file
                        backup_path = f"{settings_path}.bak"
                        try:
                            with open(settings_path, 'r') as src, open(backup_path, 'w') as dst:
                                dst.write(src.read())
                            logger.info(f"Created backup of settings at {backup_path}")
                        except Exception as e:
                            logger.warning(f"Failed to create settings backup: {e}")
                        
                        # Write updated settings
                        with open(settings_path, 'w') as f:
                            json.dump(settings, f, indent=4)
                        logger.info(f"Updated device states in settings file")
                    except Exception as e:
                        logger.error(f"Error saving settings file: {e}")
                
                # Wait for next check
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                logger.info("Device monitoring task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in device monitoring: {e}")
                # Wait a bit before retrying
                await asyncio.sleep(10)
    
    def _get_monitoring_interval_from_settings(self, settings_path: str) -> int:
        """
        Get the monitoring interval from settings.json.
        
        Args:
            settings_path: Path to settings.json file
            
        Returns:
            int: Monitoring interval in seconds
        """
        try:
            with open(settings_path, 'r') as f:
                settings = json.load(f)
            
            # Check if tapo section exists and has monitoring_interval
            if 'tapo' in settings and 'monitoring_interval' in settings['tapo']:
                interval = settings['tapo']['monitoring_interval']
                return interval
        except Exception as e:
            logger.warning(f"Error reading monitoring interval from settings.json: {e}")
        
        # Return default if not found in settings
        return 60  # Default to 60 seconds
    
    async def scan_and_update_settings(self, settings_path: str, force_scan: bool = False) -> bool:
        """
        Scan for devices and update the settings file.
        
        Args:
            settings_path: Path to the settings file
            force_scan: Whether to force a new scan even if cache is available
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_initialized:
            logger.warning("Cannot scan for devices: controller not initialized")
            if not self.initialize():
                return False
        
        try:
            logger.info(f"Scanning for devices and updating settings at {settings_path}")
            
            # If force_scan is true, clear the discovery cache
            if force_scan:
                self._discovery_cache = []
                self._last_discovery = 0
                logger.info("Forcing a new device scan")
            
            # Load current settings first to get existing device names
            try:
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                    
                # Create a mapping of MAC addresses to existing device names
                existing_device_names = {}
                if 'available_devices' in settings:
                    for device in settings['available_devices']:
                        if 'mac' in device and 'name' in device and device['name']:
                            existing_device_names[device['mac']] = device['name']
                            logger.info(f"Found existing device name in settings: {device['mac']} -> {device['name']}")
            except Exception as e:
                logger.error(f"Error loading settings file: {e}")
                settings = {}
                existing_device_names = {}
            
            # Discover all devices
            discovered_devices = await self.discover_devices()
            
            if not discovered_devices:
                logger.warning("No devices discovered")
                return False
                
            logger.info(f"Discovered {len(discovered_devices)} devices")
            
            # For each discovered device, try to get the actual name directly from the device
            for device in discovered_devices:
                logger.info(f"Processing device - IP: {device.get('ip', 'Unknown')}, MAC: {device.get('mac', 'Unknown')}")
                
                # First check if we already have a name for this device in settings.json
                if device['mac'] in existing_device_names:
                    original_name = device['name']
                    device['name'] = existing_device_names[device['mac']]
                    logger.info(f"Using existing name from settings for {device['mac']}: '{original_name}' -> '{device['name']}'")
                    continue  # Skip to next device since we're using the existing name
                
                # If this is a new device, try to get the actual name directly from the device
                try:
                    logger.info(f"Attempting to get name directly for device at {device.get('ip')}")
                    tapo_device = await self.get_device(device.get('ip'))
                    if tapo_device:
                        device_info = await tapo_device.get_device_info()
                        
                        # Handle different return types from the API
                        actual_name = None
                        
                        # Try to extract the alias/name from device_info
                        if hasattr(device_info, 'alias') and device_info.alias:
                            actual_name = device_info.alias
                        elif isinstance(device_info, dict) and 'alias' in device_info and device_info['alias']:
                            actual_name = device_info['alias']
                        elif hasattr(device_info, 'nickname') and device_info.nickname:
                            actual_name = device_info.nickname
                        elif isinstance(device_info, dict) and 'nickname' in device_info and device_info['nickname']:
                            actual_name = device_info['nickname']
                        
                        # If we found a name, use it
                        if actual_name:
                            logger.info(f"Retrieved actual name from device: '{actual_name}' (was '{device['name']}')")
                            device['name'] = actual_name
                        else:
                            logger.warning(f"No alias or nickname found in device_info for {device.get('ip')}")
                except Exception as e:
                    logger.warning(f"Error getting device name directly: {e}")
            
            # Update or add devices
            if 'available_devices' not in settings:
                settings['available_devices'] = []
                
            # Keep track of existing devices by MAC
            existing_macs = {device['mac']: i for i, device in enumerate(settings['available_devices'])}
            
            # Update existing devices and add new ones
            for device in discovered_devices:
                if device['mac'] in existing_macs:
                    # Update existing device
                    index = existing_macs[device['mac']]
                    # Preserve role if it exists
                    if 'role' in settings['available_devices'][index]:
                        device['role'] = settings['available_devices'][index]['role']
                    # Preserve name if it exists in settings
                    if 'name' in settings['available_devices'][index] and settings['available_devices'][index]['name']:
                        device['name'] = settings['available_devices'][index]['name']
                    settings['available_devices'][index] = device
                    logger.info(f"Updated device {device['name']} in settings")
                else:
                    # Add new device
                    device['role'] = None  # No role assigned by default
                    settings['available_devices'].append(device)
                    logger.info(f"Added new device {device['name']} to settings")
            
            # Save updated settings
            try:
                with open(settings_path, 'w') as f:
                    json.dump(settings, f, indent=4)
                logger.info(f"Settings updated successfully at {settings_path}")
                return True
            except Exception as e:
                logger.error(f"Error saving settings file: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error scanning for devices: {e}")
            return False 