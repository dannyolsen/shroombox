#!/usr/bin/env python3
"""
Tapo Device Finder
Utility to find and identify Tapo smart devices on the local network.
"""

import os
import asyncio
from dotenv import load_dotenv
from tapo import ApiClient
from kasa import Discover
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

async def find_tapo_devices():
    """Find Tapo devices using Kasa discovery and then verify with Tapo API."""
    # Load environment variables
    load_dotenv()
    
    # Get Tapo credentials from environment
    tapo_email = os.getenv('TAPO_EMAIL')
    tapo_password = os.getenv('TAPO_PASSWORD')
    
    if not tapo_email or not tapo_password:
        logger.error("❌ Error: Tapo credentials not found in .env file")
        return
    
    logger.info("\n=== Tapo Device Scanner ===")
    logger.info("Discovering devices...\n")
    
    try:
        # Use Kasa discovery to find all smart plugs
        devices = await Discover.discover()
        
        if devices:
            logger.info("=== Found Devices ===")
            tapo_client = ApiClient(tapo_email, tapo_password)
            
            for ip_addr, device in devices.items():
                try:
                    # Try to connect to the device using Tapo API
                    tapo_device = await tapo_client.p115(ip_addr)
                    device_info = await tapo_device.get_device_info()
                    
                    logger.info("\nDevice Information:")
                    logger.info(f"IP Address:  {ip_addr}")
                    logger.info(f"Name:        {device_info.nickname}")
                    logger.info(f"Model:       {device_info.model}")
                    logger.info(f"Type:        {device_info.type}")
                    logger.info(f"MAC:         {device_info.mac}")
                    logger.info(f"Status:      {'ON' if device_info.device_on else 'OFF'}")
                    logger.info(f"HW Version:  {device_info.hw_version}")
                    logger.info(f"FW Version:  {device_info.fw_version}")
                    logger.info("-" * 30)
                except Exception as e:
                    # Skip non-Tapo devices
                    continue
        else:
            logger.info("❌ No devices found on the network")
            
    except Exception as e:
        logger.error(f"❌ Error during device discovery: {e}")

async def find_device_by_mac(target_mac: str):
    """Find a Tapo device by its MAC address."""
    # Normalize MAC address format (remove colons/dashes, convert to uppercase)
    target_mac = target_mac.replace(':', '').replace('-', '').upper()
    
    # Load environment variables
    load_dotenv()
    
    # Get Tapo credentials from environment
    tapo_email = os.getenv('TAPO_EMAIL')
    tapo_password = os.getenv('TAPO_PASSWORD')
    
    if not tapo_email or not tapo_password:
        logger.error("❌ Error: Tapo credentials not found in .env file")
        return None
    
    logger.info(f"\n=== Searching for device with MAC: {target_mac} ===")
    logger.info("Discovering devices...\n")
    
    try:
        # Use Kasa discovery to find all smart plugs
        devices = await Discover.discover()
        found = False  # Add flag to track if device was found
        
        if devices:
            tapo_client = ApiClient(tapo_email, tapo_password)
            
            for ip_addr, device in devices.items():
                try:
                    # Try to connect to the device using Tapo API
                    tapo_device = await tapo_client.p115(ip_addr)
                    device_info = await tapo_device.get_device_info()
                    
                    # Normalize device MAC address
                    device_mac = device_info.mac.replace(':', '').replace('-', '').upper()
                    
                    if device_mac == target_mac:
                        found = True  # Set flag when device is found
                        logger.info("✓ Device found!")
                        logger.info("\nDevice Information:")
                        logger.info(f"IP Address:  {ip_addr}")
                        logger.info(f"Name:        {device_info.nickname}")
                        logger.info(f"Model:       {device_info.model}")
                        logger.info(f"Type:        {device_info.type}")
                        logger.info(f"MAC:         {device_info.mac}")
                        logger.info(f"Status:      {'ON' if device_info.device_on else 'OFF'}")
                        logger.info(f"HW Version:  {device_info.hw_version}")
                        logger.info(f"FW Version:  {device_info.fw_version}")
                        logger.info("-" * 30)
                        return ip_addr
                except Exception as e:
                    continue
            
            # Only show "not found" message if device wasn't found
            if not found:
                logger.info(f"❌ No device found with MAC address: {target_mac}")
            return None
        else:
            logger.info("❌ No devices found on the network")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error during device discovery: {e}")
        return None

async def list_all_devices():
    """List all Tapo devices found on the network."""
    await find_tapo_devices()  # Using the existing function

async def main():
    """Main entry point."""
    try:
        # Check if MAC address was provided as argument
        import sys
        if len(sys.argv) > 1:
            mac_address = sys.argv[1]
            await find_device_by_mac(mac_address)
        else:
            # If no MAC provided, list all devices
            await list_all_devices()
    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
    finally:
        # Clean up any remaining tasks
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\nScan cancelled by user")
    except Exception as e:
        logger.error(f"\n❌ Error: {e}") 