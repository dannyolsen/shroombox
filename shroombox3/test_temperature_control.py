#!/usr/bin/env python3
"""
Test script for temperature control logic with direct tapo module access
"""

import asyncio
import os
import json
from dotenv import load_dotenv
import sys
import traceback
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('temp_control_test')

# Load environment variables
load_dotenv()

# Get credentials
tapo_email = os.getenv('TAPO_EMAIL')
tapo_password = os.getenv('TAPO_PASSWORD')

try:
    from tapo import ApiClient
    logger.info("Successfully imported tapo.ApiClient")
except ImportError as e:
    logger.error(f"Error importing tapo: {e}")
    sys.exit(1)

def load_settings():
    """Load settings from file."""
    try:
        with open('config/settings.json', 'r') as f:
            settings = json.load(f)
        logger.info("Settings loaded successfully")
        return settings
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        return None

def find_heater(settings):
    """Find the heater device in settings."""
    if not settings:
        return None
        
    for device in settings.get('available_devices', []):
        if device.get('role') == 'heater':
            logger.info(f"Found heater: {device['name']} at {device['ip']}")
            return device
    
    logger.error("No heater found in settings")
    return None

async def check_temp_control_logic(temperature):
    """Check if the heater should be on based on the temperature control logic."""
    
    settings = load_settings()
    if not settings:
        return
        
    heater = find_heater(settings)
    if not heater:
        return
    
    # Get temperature settings
    current_phase = settings['environment']['current_phase']
    setpoint = float(settings['environment']['phases'][current_phase]['temp_setpoint'])
    hysteresis = float(settings['environment']['phases'][current_phase]['temp_hysteresis'])
    
    # Calculate threshold
    temp_low = setpoint - hysteresis
    
    # Determine if heater should be on
    should_heat = temperature < temp_low
    
    logger.info("===== TEMPERATURE CONTROL LOGIC =====")
    logger.info(f"Current temperature: {temperature}°C")
    logger.info(f"Current phase: {current_phase}")
    logger.info(f"Temperature setpoint: {setpoint}°C")
    logger.info(f"Hysteresis: {hysteresis}°C")
    logger.info(f"Heat-on threshold: {temp_low}°C")
    logger.info(f"Should heat? {should_heat} (temp < threshold? {temperature} < {temp_low})")
    
    # Connect to heater and check current state
    try:
        client = ApiClient(tapo_email, tapo_password)
        device = await client.p115(heater['ip'])
        
        # Get current state
        info = await device.get_device_info()
        current_state = info.device_on
        logger.info(f"Current heater state: {'ON' if current_state else 'OFF'}")
        
        # Check for mismatch
        if should_heat != current_state:
            logger.warning(f"State mismatch! Current: {'ON' if current_state else 'OFF'}, Should be: {'ON' if should_heat else 'OFF'}")
            
            # Ask if user wants to fix
            response = input(f"\nCorrect heater state to {'ON' if should_heat else 'OFF'}? (y/n): ")
            if response.lower() == 'y':
                logger.info(f"Setting heater to {'ON' if should_heat else 'OFF'}...")
                if should_heat:
                    await device.on()
                else:
                    await device.off()
                
                # Wait briefly
                await asyncio.sleep(2)
                
                # Verify change
                info = await device.get_device_info()
                new_state = info.device_on
                logger.info(f"Heater state after change: {'ON' if new_state else 'OFF'}")
                
                # Update settings
                for device in settings.get('available_devices', []):
                    if device.get('role') == 'heater':
                        device['state'] = new_state
                
                with open('config/settings.json', 'w') as f:
                    json.dump(settings, f, indent=4)
                logger.info(f"Updated settings.json with state: {'ON' if new_state else 'OFF'}")
            else:
                logger.info("Keeping current state")
        else:
            logger.info("Heater state is correct according to temperature control logic")
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
        logger.error(traceback.format_exc())

async def main():
    """Main test function."""
    logger.info("===== TEMPERATURE CONTROL LOGIC TEST =====")
    
    # Ask for temperature input
    try:
        temp_input = input("\nEnter current temperature in °C: ")
        temperature = float(temp_input)
        logger.info(f"Using temperature: {temperature}°C")
        
        await check_temp_control_logic(temperature)
        
    except ValueError:
        logger.error(f"Invalid temperature input: {temp_input}")
    except Exception as e:
        logger.error(f"Error during test: {e}")
        logger.error(traceback.format_exc())
    
    logger.info("Test completed")

if __name__ == "__main__":
    asyncio.run(main()) 