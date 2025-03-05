import os
import asyncio
from dotenv import load_dotenv
from tapo import ApiClient
from kasa import Discover
import logging
from typing import Optional, Dict, Any
import json

logger = logging.getLogger(__name__)

class TapoController:
    """Controller class for managing Tapo devices."""
    
    def __init__(self, email: str, password: str):
        """Initialize TapoController with credentials."""
        self.email = email
        self.password = password
        self.client = ApiClient(email, password)
        self._device_cache: Dict[str, Any] = {}  # Cache for device connections
        
    async def verify_device(self, device_config: Dict[str, str]) -> bool:
        """
        Verify if a device's stored configuration is still valid.
        Returns True if device is accessible and MAC matches.
        """
        try:
            device = await self.client.p115(device_config['ip'])
            info = await device.get_device_info()
            
            # Normalize MAC addresses for comparison
            stored_mac = device_config['mac'].replace(':', '').replace('-', '').upper()
            actual_mac = info.mac.replace(':', '').replace('-', '').upper()
            
            if stored_mac == actual_mac:
                # Update cache if device is valid
                self._device_cache[device_config['ip']] = device
                return True
                
            logger.warning(f"MAC address mismatch for {device_config['name']}")
            return False
            
        except Exception as e:
            logger.error(f"Error verifying device {device_config['name']}: {e}")
            return False
    
    async def update_device_info(self, device_config: Dict[str, str]) -> Optional[Dict[str, str]]:
        """
        Update device information by finding current IP address.
        Returns updated device config if found, None if not found.
        """
        try:
            # Try to find device by MAC address
            new_ip = await self.find_device_by_mac(device_config['mac'])
            if new_ip:
                # Get fresh device info
                device_info = await self.get_device_info(new_ip)
                if device_info:
                    return {
                        'name': device_config['name'],
                        'mac': device_info['mac'],
                        'ip': new_ip,
                        'model': device_info['model'],
                        'type': device_info['type']
                    }
            return None
        except Exception as e:
            logger.error(f"Error updating device info for {device_config['name']}: {e}")
            return None
    
    async def find_device_by_mac(self, target_mac: str) -> Optional[str]:
        """
        Find a Tapo device's IP address by MAC address.
        Returns IP address if found, None otherwise.
        """
        # Normalize MAC address
        target_mac = target_mac.replace(':', '').replace('-', '').upper()
        
        try:
            devices = await Discover.discover()
            
            if not devices:
                logger.warning("No devices found on network")
                return None
                
            for ip_addr, device in devices.items():
                try:
                    tapo_device = await self.client.p115(ip_addr)
                    device_info = await tapo_device.get_device_info()
                    device_mac = device_info.mac.replace(':', '').replace('-', '').upper()
                    
                    if device_mac == target_mac:
                        logger.info(f"Found device at {ip_addr}")
                        # Cache the device connection
                        self._device_cache[ip_addr] = tapo_device
                        return ip_addr
                except Exception:
                    continue
                    
            logger.warning(f"No device found with MAC: {target_mac}")
            return None
            
        except Exception as e:
            logger.error(f"Error during device discovery: {e}")
            return None
    
    async def get_device(self, ip_addr: str):
        """
        Get a Tapo device instance by IP address.
        Uses cached connection if available.
        """
        try:
            # Return cached device if available
            if ip_addr in self._device_cache:
                return self._device_cache[ip_addr]
            
            # Create new connection if not cached
            device = await self.client.p115(ip_addr)
            self._device_cache[ip_addr] = device
            return device
        except Exception as e:
            logger.error(f"Error connecting to device at {ip_addr}: {e}")
            return None
    
    async def set_device_state(self, ip_addr: str, state: bool) -> bool:
        """Turn device on or off."""
        try:
            device = await self.get_device(ip_addr)
            if device:
                if state:
                    await device.on()
                else:
                    await device.off()
                return True
            return False
        except Exception as e:
            logger.error(f"Error setting device state: {e}")
            return False
    
    async def get_device_info(self, ip_addr: str) -> Optional[Dict[str, Any]]:
        """Get detailed device information."""
        try:
            device = await self.get_device(ip_addr)
            if device:
                info = await device.get_device_info()
                return {
                    'ip': ip_addr,
                    'name': info.nickname,
                    'model': info.model,
                    'type': info.type,
                    'mac': info.mac,
                    'state': info.device_on,
                    'hw_version': info.hw_version,
                    'fw_version': info.fw_version
                }
            return None
        except Exception as e:
            logger.error(f"Error getting device info: {e}")
            return None
    
    async def discover_devices(self) -> list[Dict[str, Any]]:
        """Discover all Tapo devices on the network using Kasa discovery."""
        devices_info = []
        try:
            logger.info("Starting Kasa device discovery...")
            
            # Use Kasa's discovery to find all devices
            found_devices = await Discover.discover()
            
            if found_devices:
                logger.info(f"Found {len(found_devices)} devices on network")
                
                for ip_addr, kasa_device in found_devices.items():
                    try:
                        # Get Tapo device info for each discovered device
                        device = await self.client.p115(ip_addr)
                        info = await device.get_device_info()
                        
                        # Only add P115 devices
                        if info.model == "P115":
                            device_info = {
                                'name': info.nickname,
                                'ip': ip_addr,
                                'mac': info.mac,
                                'model': info.model,
                                'type': info.type,
                                'state': info.device_on
                            }
                            devices_info.append(device_info)
                            logger.info(f"✓ Found Tapo P115: {device_info['name']} at {ip_addr}")
                    except Exception as e:
                        # Skip non-Tapo devices
                        logger.debug(f"Skipping non-Tapo device at {ip_addr}: {e}")
                        continue
                
                if devices_info:
                    logger.info(f"Discovery complete. Found {len(devices_info)} Tapo P115 devices")
                else:
                    logger.warning("No Tapo P115 devices found among discovered devices")
                    
                return devices_info
                
            else:
                logger.warning("No devices found on network")
                return []
                
        except Exception as e:
            logger.error(f"Error during device discovery: {e}")
            return []

    async def get_or_update_device(self, device_config: Dict[str, str]) -> Optional[str]:
        """
        Get device IP address, verifying and updating if necessary.
        Returns current IP address if device is accessible, None otherwise.
        """
        try:
            # First try stored IP
            if await self.verify_device(device_config):
                return device_config['ip']
            
            # If verification fails, try to find device
            logger.info(f"Searching for {device_config['name']}...")
            updated_config = await self.update_device_info(device_config)
            if updated_config:
                logger.info(f"Found {device_config['name']} at {updated_config['ip']}")
                return updated_config['ip']
            
            logger.warning(f"Could not find {device_config['name']}")
            return None
            
        except Exception as e:
            logger.error(f"Error accessing {device_config['name']}: {e}")
            return None

    async def find_by_name(self, device_name: str) -> Optional[Dict[str, Any]]:
        """
        Find a device by its name.
        Returns device info dictionary if found, None otherwise.
        """
        try:
            # Normalize name for comparison (lowercase)
            device_name = device_name.lower()
            
            # Discover all devices
            devices = await Discover.discover()
            if not devices:
                logger.warning("No devices found on network")
                return None
            
            # Check each device
            for ip_addr, _ in devices.items():
                try:
                    device = await self.client.p115(ip_addr)
                    info = await device.get_device_info()
                    
                    # Compare normalized names
                    if info.nickname.lower() == device_name:
                        device_info = {
                            'name': info.nickname,
                            'ip': ip_addr,
                            'mac': info.mac,
                            'model': info.model,
                            'type': info.type,
                            'state': info.device_on,
                            'hw_version': info.hw_version,
                            'fw_version': info.fw_version
                        }
                        # Cache the device connection
                        self._device_cache[ip_addr] = device
                        return device_info
                except Exception:
                    continue
            
            logger.warning(f"No device found with name: {device_name}")
            return None
            
        except Exception as e:
            logger.error(f"Error searching for device by name: {e}")
            return None
    
    async def find_by_mac(self, mac_address: str) -> Optional[Dict[str, Any]]:
        """
        Find a device by its MAC address.
        Returns device info dictionary if found, None otherwise.
        """
        try:
            # Normalize MAC address
            mac_address = mac_address.replace(':', '').replace('-', '').upper()
            
            # Discover all devices
            devices = await Discover.discover()
            if not devices:
                logger.warning("No devices found on network")
                return None
            
            # Check each device
            for ip_addr, _ in devices.items():
                try:
                    device = await self.client.p115(ip_addr)
                    info = await device.get_device_info()
                    
                    # Normalize device MAC for comparison
                    device_mac = info.mac.replace(':', '').replace('-', '').upper()
                    
                    if device_mac == mac_address:
                        device_info = {
                            'name': info.nickname,
                            'ip': ip_addr,
                            'mac': info.mac,
                            'model': info.model,
                            'type': info.type,
                            'state': info.device_on,
                            'hw_version': info.hw_version,
                            'fw_version': info.fw_version
                        }
                        # Cache the device connection
                        self._device_cache[ip_addr] = device
                        return device_info
                except Exception:
                    continue
            
            logger.warning(f"No device found with MAC: {mac_address}")
            return None
            
        except Exception as e:
            logger.error(f"Error searching for device by MAC: {e}")
            return None
    
    async def find_device(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Find a device by either name or MAC address.
        Automatically detects if the identifier is a MAC address or name.
        Returns device info dictionary if found, None otherwise.
        """
        # Check if identifier looks like a MAC address
        if ':' in identifier or '-' in identifier or len(identifier.replace(':', '').replace('-', '')) == 12:
            return await self.find_by_mac(identifier)
        else:
            return await self.find_by_name(identifier)

    async def scan_and_update_settings(self, settings_file: str) -> bool:
        """
        Scan for Tapo devices and update settings.json with found devices.
        Returns True if successful, False otherwise.
        """
        try:
            logger.info("Starting device scan and settings update...")
            devices = await self.discover_devices()
            
            if not devices:
                logger.warning("No devices found to update settings with")
                return False
            
            # Load current settings
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    
                # Get current role assignments from existing devices
                role_assignments = {}
                for device in settings.get('available_devices', []):
                    if 'role' in device:
                        role_assignments[device['mac']] = device['role']
                
                # Update devices with their roles
                for device in devices:
                    if device['mac'] in role_assignments:
                        device['role'] = role_assignments[device['mac']]
                    else:
                        device['role'] = None  # No role assigned yet
                
                # Update settings
                settings['available_devices'] = devices
                
                # Save updated settings
                with open(settings_file, 'w') as f:
                    json.dump(settings, f, indent=4)
                logger.info(f"Successfully updated settings with {len(devices)} devices")
                return True
                
            except Exception as e:
                logger.error(f"Error updating settings: {e}")
                return False
            
        except Exception as e:
            logger.error(f"Error in scan_and_update_settings: {e}")
            return False

    async def check_device_online(self, ip: str, retries: int = 2) -> bool:
        """Check if a device is online using both Kasa and Tapo APIs.
        
        Args:
            ip: The IP address of the device to check
            retries: Number of retry attempts (default: 2)
            
        Returns:
            bool: True if device is online, False otherwise
        """
        for attempt in range(retries):
            try:
                # First try Kasa discovery for the specific IP
                devices = await Discover.discover(target=ip, timeout=3)
                if ip in devices:
                    logger.debug(f"Device {ip} found via Kasa (attempt {attempt + 1})")
                    return True
                    
                # If Kasa fails, try Tapo as backup
                try:
                    device = await self.client.p115(ip)
                    info = await device.get_device_info()
                    if info and hasattr(info, 'device_on') and info.device_on is not None:
                        logger.debug(f"Device {ip} found via Tapo (attempt {attempt + 1})")
                        return True
                except Exception as e:
                    logger.debug(f"Tapo check failed for {ip}: {e}")
                    
                if attempt < retries - 1:
                    logger.debug(f"Retrying device check for {ip} (attempt {attempt + 1})")
                    await asyncio.sleep(1)  # Wait a second before retry
                
            except Exception as e:
                logger.error(f"Error checking device status for {ip}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(1)
                
        logger.warning(f"Device {ip} appears to be offline after {retries} attempts")
        return False

    async def get_device_state(self, ip: str) -> bool:
        """Get the current state (on/off) of a device.
        
        Args:
            ip: The IP address of the device
            
        Returns:
            bool: True if device is on, False if off or error
        """
        try:
            device = await self.client.p115(ip)
            info = await device.get_device_info()
            return info.device_on if info else False
        except Exception as e:
            logger.error(f"Error getting device state for {ip}: {e}")
            return False

async def test_device_scanning():
    """Test function to verify device scanning functionality."""
    import os
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    print("\n=== Testing Tapo Device Scanner ===")
    
    # Initialize controller
    tapo = TapoController(
        email=os.getenv('TAPO_EMAIL'),
        password=os.getenv('TAPO_PASSWORD')
    )
    
    try:
        print("\nScanning for devices and updating settings...")
        
        # Get the path to settings.json
        settings_file = 'config/settings.json'  # Simplified path since we run from project root
        print(f"Settings file: {settings_file}")
        
        # Verify the file exists
        if not os.path.exists(settings_file):
            print(f"Error: Could not find settings file at {settings_file}")
            return
        
        # Scan and update settings
        success = await tapo.scan_and_update_settings(settings_file)
        
        if success:
            print("\nSettings updated successfully!")
            
            # Read and display the updated settings
            with open(settings_file, 'r') as f:
                settings = json.load(f)
            
            print("\nAvailable devices in settings.json:")
            for device in settings.get('available_devices', []):
                print(f"\nDevice: {device['name']}")
                print(f"IP: {device['ip']}")
                print(f"MAC: {device['mac']}")
                print(f"Model: {device['model']}")
                print(f"Type: {device['type']}")
                print(f"State: {'ON' if device['state'] else 'OFF'}")
                
            print("\nDevice assignments:")
            for device_type, device in settings.get('devices', {}).items():
                print(f"\n{device_type.capitalize()}:")
                print(f"Name: {device.get('name', 'Not assigned')}")
                print(f"IP: {device.get('ip', 'Not assigned')}")
                print(f"MAC: {device.get('mac', 'Not assigned')}")
        else:
            print("\nFailed to update settings!")
            
    except Exception as e:
        print(f"\nError during test: {e}")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the test
    print("Starting device scanning test...")
    asyncio.run(test_device_scanning())
    print("\nTest complete!")