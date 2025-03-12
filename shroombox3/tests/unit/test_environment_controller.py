#!/usr/bin/env python3
"""
Test script for EnvironmentController
This script tests specific components of the EnvironmentController in isolation
to diagnose freezing issues.
"""

import asyncio
import logging
import time
import signal
import traceback
import sys
import os
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger('test')

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the components we want to test
from managers.device_manager import DeviceManager
from managers.environment_controller import EnvironmentController

# Global flag for shutdown
shutdown_requested = False

def handle_signal(signum, frame):
    """Handle termination signals"""
    global shutdown_requested
    logger.info(f"Signal {signum} received, initiating shutdown...")
    shutdown_requested = True

# Set up signal handlers
signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

async def test_initialization():
    """Test initialization of the environment controller"""
    logger.info("=== Test 1: Initialization ===")
    try:
        logger.info("Creating DeviceManager...")
        device_manager = DeviceManager()
        
        logger.info("Creating EnvironmentController...")
        controller = EnvironmentController(device_manager)
        
        logger.info("Initialization successful!")
        return device_manager, controller
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        logger.error(traceback.format_exc())
        return None, None

async def test_start(controller):
    """Test the start method of the controller"""
    logger.info("=== Test 2: Controller.start() ===")
    try:
        # Set a timeout using asyncio.wait_for
        logger.info("Starting controller with 10 second timeout...")
        await asyncio.wait_for(controller.start(), timeout=10)
        logger.info("Controller.start() completed successfully!")
        return True
    except asyncio.TimeoutError:
        logger.error("TIMEOUT: Controller.start() took too long")
        return False
    except Exception as e:
        logger.error(f"Controller.start() failed: {e}")
        logger.error(traceback.format_exc())
        return False

async def test_load_config(controller):
    """Test the load_config method of the controller"""
    logger.info("=== Test 3: Controller.load_config() ===")
    try:
        # Set a timeout using asyncio.wait_for
        logger.info("Loading config with 5 second timeout...")
        success = await asyncio.wait_for(controller.load_config(), timeout=5)
        if success:
            logger.info("Controller.load_config() completed successfully!")
        else:
            logger.error("Controller.load_config() returned False")
        return success
    except asyncio.TimeoutError:
        logger.error("TIMEOUT: Controller.load_config() took too long")
        return False
    except Exception as e:
        logger.error(f"Controller.load_config() failed: {e}")
        logger.error(traceback.format_exc())
        return False

async def test_get_measurements(device_manager):
    """Test getting measurements from the device manager"""
    logger.info("=== Test 4: DeviceManager.get_measurements() ===")
    try:
        # Set a timeout using asyncio.wait_for
        logger.info("Getting measurements with 5 second timeout...")
        measurements = await asyncio.wait_for(device_manager.get_measurements(), timeout=5)
        if measurements:
            co2, temp, rh = measurements
            logger.info(f"Measurements: CO2={co2:.1f}ppm, Temp={temp:.1f}°C, RH={rh:.1f}%")
            return True
        else:
            logger.warning("No measurements available")
            return False
    except asyncio.TimeoutError:
        logger.error("TIMEOUT: get_measurements() took too long")
        return False
    except Exception as e:
        logger.error(f"get_measurements() failed: {e}")
        logger.error(traceback.format_exc())
        return False

async def run_tests():
    """Run a series of tests to diagnose issues"""
    try:
        # Test 1: Initialization
        device_manager, controller = await test_initialization()
        if not controller:
            return
        
        # Test 2: Controller.start()
        if not await test_start(controller):
            logger.error("Controller.start() test failed, aborting further tests")
            return
        
        # Test 3: Controller.load_config()
        if not await test_load_config(controller):
            logger.warning("Controller.load_config() test failed, continuing with caution")
        
        # Test 4: Get measurements
        await test_get_measurements(device_manager)
        
        # If we've made it this far, optionally test a single control cycle
        logger.info("=== Test 5: Single Control Cycle ===")
        try:
            logger.info("Testing a single control cycle...")
            
            # Get measurements
            measurements = await asyncio.wait_for(device_manager.get_measurements(), timeout=5)
            if measurements:
                co2, temp, rh = measurements
                measurement_time = datetime.utcnow()
                
                # Apply temperature control
                logger.info("Testing temperature control...")
                await asyncio.wait_for(controller.temperature_controller.control(temp), timeout=5)
                
                # Apply humidity control
                logger.info("Testing humidity control...")
                await asyncio.wait_for(controller.humidity_controller.control(rh), timeout=5)
                
                # Apply fan control
                logger.info("Testing fan control...")
                controller.fan_controller.update_co2_control(co2)
                
                logger.info("Single control cycle completed successfully!")
            else:
                logger.warning("No measurements available for control cycle test")
        except asyncio.TimeoutError:
            logger.error("TIMEOUT during control cycle test")
        except Exception as e:
            logger.error(f"Error during control cycle test: {e}")
            logger.error(traceback.format_exc())
        
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        logger.error(traceback.format_exc())
    finally:
        # Always attempt cleanup
        if 'controller' in locals() and controller:
            logger.info("Cleaning up...")
            try:
                await asyncio.wait_for(controller.cleanup(), timeout=5)
                logger.info("Cleanup successful")
            except (asyncio.TimeoutError, Exception) as e:
                logger.error(f"Cleanup error: {e}")

async def main_with_timeout():
    """Run the main test suite with an overall timeout"""
    try:
        # Create a task for the test suite
        test_task = asyncio.create_task(run_tests())
        
        # Wait for the test to complete or for a shutdown request
        while not test_task.done() and not shutdown_requested:
            await asyncio.sleep(0.1)
        
        # If shutdown was requested but the task is still running, cancel it
        if not test_task.done() and shutdown_requested:
            logger.info("Cancelling tests due to shutdown request")
            test_task.cancel()
            try:
                await test_task
            except asyncio.CancelledError:
                logger.info("Tests cancelled")
        
        # If the task completed normally, get the result (and any exceptions)
        if test_task.done() and not test_task.cancelled():
            try:
                await test_task
            except Exception as e:
                logger.error(f"Tests failed with exception: {e}")
                logger.error(traceback.format_exc())
    
    except Exception as e:
        logger.error(f"Critical error in main_with_timeout: {e}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    logger.info("Starting environment controller tests...")
    
    try:
        # Create a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run our main function with a 2-minute overall timeout
        GLOBAL_TIMEOUT = 120  # 2 minutes
        logger.info(f"Setting overall timeout of {GLOBAL_TIMEOUT} seconds")
        
        try:
            loop.run_until_complete(
                asyncio.wait_for(main_with_timeout(), timeout=GLOBAL_TIMEOUT)
            )
        except asyncio.TimeoutError:
            logger.error(f"GLOBAL TIMEOUT: Test suite did not complete within {GLOBAL_TIMEOUT} seconds")
        
        logger.info("Tests completed")
    
    except KeyboardInterrupt:
        logger.info("Tests interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        logger.error(traceback.format_exc())
    finally:
        # Clean up the event loop
        if 'loop' in locals() and loop.is_running():
            # Cancel all tasks
            for task in asyncio.all_tasks(loop):
                task.cancel()
            
            # Run the event loop until all tasks are cancelled
            loop.run_until_complete(asyncio.sleep(0.1))
            
            # Close the loop
            loop.close()
        
        logger.info("Test script finished") 