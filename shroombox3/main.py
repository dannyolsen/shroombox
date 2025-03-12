#!/usr/bin/env python3
"""
Shroombox Main Controller (Simplified)
A simplified version with extra safeguards against freezing.
"""

import os
import sys
import time
import asyncio
import logging
import logging.handlers
import signal
import traceback
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            'logs/simple_main.log', 
            maxBytes=1024*1024,  # 1MB
            backupCount=3
        )
    ]
)

logger = logging.getLogger('shroombox')

# Global flag to signal shutdown
shutdown_requested = False

def signal_handler(sig, frame):
    """Handle signals gracefully and log the exit reason."""
    global shutdown_requested
    
    signal_names = {
        signal.SIGINT: "SIGINT (Ctrl+C)",
        signal.SIGTERM: "SIGTERM",
        signal.SIGHUP: "SIGHUP",
        signal.SIGQUIT: "SIGQUIT"
    }
    signal_name = signal_names.get(sig, f"Signal {sig}")
    logger.warning(f"Received {signal_name} signal - initiating shutdown")
    
    # Log stack trace to help debug unexpected exits
    stack_trace = ''.join(traceback.format_stack(frame))
    logger.info(f"Stack trace at exit:\n{stack_trace}")
    
    # Set shutdown flag to trigger graceful shutdown
    shutdown_requested = True
    
    # Don't call asyncio.run() here as it can't be used inside an existing event loop
    # The main loop will handle cleanup when it detects shutdown_requested = True

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGHUP, signal_handler)
signal.signal(signal.SIGQUIT, signal_handler)

# Add a sys.excepthook to log unhandled exceptions
def exception_handler(exc_type, exc_value, exc_traceback):
    """Log unhandled exceptions."""
    logger.critical("Unhandled exception - program will exit", 
                   exc_info=(exc_type, exc_value, exc_traceback))
    # Call the original excepthook
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = exception_handler

async def initialize_components():
    """Initialize system components with timeouts"""
    try:
        # Import components here to avoid issues before event loop is set
        from managers.device_manager import DeviceManager
        from managers.settings_manager import SettingsManager
        from managers.environment_controller import EnvironmentController
        
        logger.info("Creating device manager...")
        device_manager = DeviceManager()
        
        logger.info("Creating environment controller...")
        controller = EnvironmentController(device_manager)
        
        logger.info("Initialization complete!")
        return controller
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        logger.error(traceback.format_exc())
        return None

async def run_with_timeout(coro, timeout, description):
    """Run a coroutine with a timeout"""
    try:
        logger.info(f"Starting {description}...")
        result = await asyncio.wait_for(coro, timeout=timeout)
        logger.info(f"{description} completed successfully")
        # For coroutines that don't return a value, consider it a success
        return True if result is None else result
    except asyncio.TimeoutError:
        logger.error(f"TIMEOUT: {description} took longer than {timeout} seconds")
        return False
    except Exception as e:
        logger.error(f"ERROR in {description}: {e}")
        logger.error(traceback.format_exc())
        return False

async def simple_control_cycle(controller):
    """Run a single control cycle"""
    try:
        device_manager = controller.device_manager
        
        # Get measurements
        logger.info("Getting measurements...")
        measurements = await asyncio.wait_for(device_manager.get_measurements(), timeout=5)
        
        if not measurements:
            logger.warning("No measurements available")
            return
            
        co2, temp, rh = measurements
        logger.info(f"Measurements: CO2={co2:.1f}ppm, Temp={temp:.1f}°C, RH={rh:.1f}%")
        
        # Apply control logic through individual controllers
        # Temperature control
        logger.info("Controlling temperature...")
        await asyncio.wait_for(controller.temperature_controller.control(temp), timeout=5)
        
        # Humidity control
        logger.info("Controlling humidity...")
        await asyncio.wait_for(controller.humidity_controller.control(rh), timeout=5)
        
        # Fan control
        logger.info("Controlling fan...")
        controller.fan_controller.update_co2_control(co2)
        
        # Log data if needed
        current_time = time.time()
        if hasattr(controller, 'last_log_time') and current_time - controller.last_log_time >= controller.logging_interval:
            logger.info("Logging data...")
            try:
                measurement_time = datetime.utcnow()
                await asyncio.wait_for(controller.log_data(co2, temp, rh, measurement_time), timeout=10)
                controller.last_log_time = current_time
                logger.info("Data logged successfully")
            except Exception as e:
                logger.error(f"Failed to log data: {e}")
        
        logger.info("Control cycle completed successfully")
        return True
        
    except asyncio.TimeoutError:
        logger.error("Timeout during control cycle")
        return False
    except Exception as e:
        logger.error(f"Error in control cycle: {e}")
        logger.error(traceback.format_exc())
        return False

async def main():
    """Main function with watchdog timer"""
    global controller  # Access the global controller variable
    
    try:
        # Initialize components
        controller = await run_with_timeout(
            initialize_components(),
            timeout=30,
            description="component initialization"
        )
        
        if not controller:
            logger.error("Initialization failed, exiting")
            return
        
        # Start controller
        success = await run_with_timeout(
            controller.start(),
            timeout=30,
            description="controller startup"
        )
        
        if not success:
            logger.error("Controller startup failed, exiting")
            return
        
        # Main control loop with watchdog
        cycle_count = 0
        error_count = 0
        last_successful_cycle = time.time()
        
        logger.info("Entering main control loop")
        while not shutdown_requested:
            try:
                cycle_start = time.time()
                cycle_count += 1
                
                # Run a control cycle with a timeout
                success = await run_with_timeout(
                    simple_control_cycle(controller),
                    timeout=15,  # 15 seconds max for a full cycle
                    description=f"control cycle #{cycle_count}"
                )
                
                if success:
                    # Reset error count on success
                    error_count = 0
                    last_successful_cycle = time.time()
                else:
                    # Increment error count
                    error_count += 1
                    logger.warning(f"Control cycle failed (error count: {error_count})")
                
                # If too many consecutive errors, try to restart
                if error_count >= 3:
                    logger.error(f"Too many consecutive errors ({error_count}), restarting controller")
                    try:
                        # Try cleanup
                        await asyncio.wait_for(controller.cleanup(), timeout=5)
                    except Exception:
                        # Ignore cleanup errors
                        pass
                        
                    # Re-initialize the controller
                    controller = await run_with_timeout(
                        initialize_components(),
                        timeout=30,
                        description="controller re-initialization"
                    )
                    
                    if controller:
                        await run_with_timeout(
                            controller.start(),
                            timeout=30,
                            description="controller restart"
                        )
                    
                    # Reset counters
                    error_count = 0
                    last_successful_cycle = time.time()
                
                # Check if system is completely stuck
                current_time = time.time()
                if current_time - last_successful_cycle > 120:  # 2 minutes
                    logger.critical("System appears to be stuck, forcing restart")
                    # Force exit - systemd or process manager will restart
                    os._exit(1)
                
                # Calculate sleep time (aim for 5-second cycles)
                cycle_duration = time.time() - cycle_start
                sleep_time = max(1, 5 - cycle_duration)  # At least 1 second, aim for 5-second cycles
                
                logger.info(f"Sleeping for {sleep_time:.1f} seconds")
                for _ in range(int(sleep_time * 10)):  # Check shutdown flag every 100ms
                    if shutdown_requested:
                        break
                await asyncio.sleep(0.1)
            
            except asyncio.CancelledError:
                logger.info("Main loop was cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                logger.error(traceback.format_exc())
                error_count += 1
                await asyncio.sleep(1)  # Brief pause before continuing
        
        logger.info("Main loop exited, cleaning up")
        
        # Clean up
        if controller:
            await run_with_timeout(
                controller.cleanup(),
                timeout=10,
                description="controller cleanup"
            )
        
    except asyncio.CancelledError:
        logger.info("Main task was cancelled")
    except Exception as e:
        logger.error(f"Fatal error in main function: {e}")
        logger.error(traceback.format_exc())
        return 1
    
    logger.info("Main function completed")
    return 0

if __name__ == "__main__":
    logger.info("Starting Shroombox Main Controller (Simplified)")
    
    # Set up exit code
    exit_code = 0
    controller = None  # Store controller globally for cleanup in case of crashes
    
    try:
        # Create new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Create global timeout for the whole program
        GLOBAL_TIMEOUT = 24 * 60 * 60  # 24 hours max runtime
        
        # Create a task for main
        main_task = loop.create_task(main())
        
        # Add a done callback to capture the controller for emergency cleanup
        def done_callback(task):
            global controller
            try:
                if task.exception() is not None:
                    logger.error(f"Main task failed with exception: {task.exception()}")
            except asyncio.CancelledError:
                pass
        
        main_task.add_done_callback(done_callback)
        
        # Run with global timeout
        try:
            loop.run_until_complete(
                asyncio.wait_for(main_task, timeout=GLOBAL_TIMEOUT)
            )
        except asyncio.TimeoutError:
            logger.warning(f"Global timeout reached after {GLOBAL_TIMEOUT} seconds")
        
    except KeyboardInterrupt:
        logger.info("Program interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        logger.error(traceback.format_exc())
        exit_code = 1
    finally:
        logger.info("Shutting down...")

        try:
            # Handle cleanup of device resources directly to avoid segfaults
            if 'loop' in locals() and loop.is_running():
                # Try to clean up any hardware resources first
                try:
                    if controller and hasattr(controller, 'device_manager'):
                        # Stop the fan
                        if hasattr(controller.device_manager, 'fan'):
                            logger.info("Emergency cleanup: Stopping fan")
                            controller.device_manager.fan.cleanup()
                            
                        # Stop the sensor
                        if hasattr(controller.device_manager, 'sensor'):
                            logger.info("Emergency cleanup: Stopping sensor")
                            controller.device_manager.sensor.cleanup()
                except Exception as e:
                    logger.error(f"Error during emergency hardware cleanup: {e}")
            
            # Cancel all pending tasks
            if 'loop' in locals() and loop.is_running():
                pending = asyncio.all_tasks(loop)
                if pending:
                    logger.info(f"Cancelling {len(pending)} pending tasks")
                    for task in pending:
                        task.cancel()
                    
                    # Give tasks a moment to cancel
                    loop.run_until_complete(asyncio.sleep(0.5))
                
                # Close the loop
                loop.close()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        
        logger.info("Program exited")
        
    sys.exit(exit_code) 