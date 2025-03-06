#!/usr/bin/env python3
import asyncio
import os
from main import EnvironmentController

async def main():
    try:
        # Initialize controller
        controller = EnvironmentController()
        await controller.start()
        
        # Load device assignments
        controller._load_device_assignments()
        
        # Initialize devices
        await controller.initialize_devices()
        
        # Print device info
        print(f"Heater IP: {controller.heater_ip}")
        print(f"Humidifier IP: {controller.humidifier_ip}")
        
        # Clean up
        await controller.cleanup()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 