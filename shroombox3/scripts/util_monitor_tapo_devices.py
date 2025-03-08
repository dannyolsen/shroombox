#!/usr/bin/env python3
"""
Utility script to monitor Tapo devices and update their state in settings.json
"""

import os
import sys
import time
import asyncio
import logging
from typing import Dict, Any
from utils import logging_setup
from managers.settings_manager import SettingsManager

# Set up logging
logger = logging_setup.get_logger('shroombox.tapo_monitor')

async def monitor_tapo_devices():
    """Monitor Tapo devices and update their state in settings."""
    try:
        # Initialize settings manager
        settings_manager = SettingsManager()
        
        # Get initial settings
        settings = await settings_manager.load_settings()
        monitoring_interval = settings.get('tapo', {}).get('monitoring_interval', 5)
        
        logger.info(f"Starting Tapo device monitoring with interval: {monitoring_interval}s")
        
        while True:
            try:
                # Load current settings
                settings = await settings_manager.load_settings(force_reload=True)
                
                # Get list of devices
                devices = settings.get('available_devices', [])
                
                # Update each device's state
                for device in devices:
                    if 'ip' in device:
                        from devices.smart_plug import TapoController
                        tapo = TapoController()
                        state = await tapo.get_device_state(device['ip'])
                        
                        if state is not None and state != device.get('state'):
                            # Update device state
                            device['state'] = state
                            logger.info(f"Device {device.get('role', 'unknown')} at {device['ip']} state changed to: {'ON' if state else 'OFF'}")
                            
                            # Save updated settings
                            await settings_manager.save_settings(settings)
                
                # Sleep for the monitoring interval
                await asyncio.sleep(monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)  # Wait 5 seconds before retrying on error
                
    except Exception as e:
        logger.error(f"Fatal error in Tapo device monitoring: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(monitor_tapo_devices()) 