#!/usr/bin/env python3
"""
Test script to diagnose heater control issues
"""

import asyncio
import logging
import os
from main import EnvironmentController
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('heater_diagnostics')

async def run_heater_diagnostics():
    """Run diagnostics on the heater control system"""
    
    logger.info("Starting heater diagnostics...")
    
    # Load environment variables
    load_dotenv()
    
    # Initialize the environment controller
    controller = EnvironmentController()
    
    # Give it a moment to initialize
    await asyncio.sleep(2)
    
    # Initialize devices
    logger.info("Initializing devices...")
    await controller.initialize_devices()
    
    # Run diagnostics
    logger.info("Running heater diagnostics...")
    await controller.diagnose_heater_control()
    
    # Clean up
    await controller.cleanup()
    
    logger.info("Heater diagnostics complete")
    
if __name__ == "__main__":
    asyncio.run(run_heater_diagnostics()) 