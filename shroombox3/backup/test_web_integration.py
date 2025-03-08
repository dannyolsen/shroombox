#!/usr/bin/env python3
"""
Test script to verify that the web app works with the new structure.
"""

import asyncio
import logging
import sys
import os
from utils import logging_setup
from devices.fan import NoctuaFan
from devices.sensor import SCD30Controller
from managers.device_manager import DeviceManager
import aiohttp

# Set up logging
logging_setup.setup_logging()
logger = logging_setup.get_logger('test_web')

async def test_web_api():
    """Test the web API endpoints."""
    logger.info("Testing web API endpoints...")
    
    # Create a session
    async with aiohttp.ClientSession() as session:
        # Test the health endpoint
        logger.info("Testing health endpoint...")
        try:
            async with session.get('http://localhost:5000/health') as response:
                if response.status == 200:
                    logger.info("Health endpoint OK")
                else:
                    logger.error(f"Health endpoint failed: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Error connecting to web server: {e}")
            logger.info("Make sure the web server is running with: python web/web_server.py")
            return False
        
        # Test the settings endpoint
        logger.info("Testing settings endpoint...")
        try:
            async with session.get('http://localhost:5000/api/settings') as response:
                if response.status == 200:
                    settings = await response.json()
                    logger.info(f"Settings endpoint OK: {len(settings)} settings loaded")
                else:
                    logger.error(f"Settings endpoint failed: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Error testing settings endpoint: {e}")
            return False
        
        # Test the status endpoint
        logger.info("Testing status endpoint...")
        try:
            async with session.get('http://localhost:5000/api/status') as response:
                if response.status == 200:
                    status = await response.json()
                    logger.info(f"Status endpoint OK: {status}")
                else:
                    logger.error(f"Status endpoint failed: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Error testing status endpoint: {e}")
            return False
        
        # Test the measurements endpoint
        logger.info("Testing measurements endpoint...")
        try:
            async with session.get('http://localhost:5000/api/measurements/latest') as response:
                if response.status == 200:
                    measurements = await response.json()
                    logger.info(f"Measurements endpoint OK: {measurements}")
                else:
                    logger.error(f"Measurements endpoint failed: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Error testing measurements endpoint: {e}")
            return False
        
        # Test the fan control endpoint
        logger.info("Testing fan control endpoint...")
        try:
            data = {'speed': 50}
            async with session.post('http://localhost:5000/api/fan/control', json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"Fan control endpoint OK: {result}")
                else:
                    logger.error(f"Fan control endpoint failed: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Error testing fan control endpoint: {e}")
            return False
        
        # Reset fan speed to 0
        logger.info("Resetting fan speed to 0...")
        try:
            data = {'speed': 0}
            async with session.post('http://localhost:5000/api/fan/control', json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"Fan reset OK: {result}")
                else:
                    logger.error(f"Fan reset failed: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Error resetting fan speed: {e}")
            return False
        
        logger.info("All web API tests passed!")
        return True

async def main():
    """Run the tests."""
    logger.info("Starting web integration tests...")
    
    try:
        # Test web API
        success = await test_web_api()
        
        if success:
            logger.info("All tests completed successfully")
        else:
            logger.error("Tests failed")
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
    
if __name__ == "__main__":
    asyncio.run(main()) 