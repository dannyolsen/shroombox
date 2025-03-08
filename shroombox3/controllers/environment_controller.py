"""
Environment Controller
Orchestrates the environmental control system by coordinating individual controllers.
"""

import os
import time
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import traceback

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from managers.device_manager import DeviceManager
from controllers.fan_controller import FanController
from controllers.humidity_controller import HumidityController
from controllers.temperature_controller import TemperatureController

# Set up logging
logger = logging.getLogger('shroombox.environment')

class ConfigFileHandler(FileSystemEventHandler):
    """Handles config file changes."""
    
    def __init__(self, controller):
        """Initialize the config file handler.
        
        Args:
            controller: The EnvironmentController instance
        """
        self.controller = controller
        self.last_modified = 0
        self.cooldown = 1  # 1 second cooldown
        self.processing_event = False  # Flag to prevent multiple concurrent handlers
        
    def on_modified(self, event):
        """Called when the config file is modified."""
        # Only handle settings.json modifications
        if not event.is_directory and event.src_path.endswith('settings.json'):
            current_time = time.time()
            
            # Check cooldown period and ensure no other event is being processed
            if (current_time - self.last_modified > self.cooldown and 
                not self.processing_event):
                try:
                    # Set processing flag to prevent concurrent handling
                    self.processing_event = True
                    self.last_modified = current_time
                    
                    # Create a separate function to handle the change instead of using run_coroutine_threadsafe
                    # which can cause issues over time
                    self._schedule_config_reload()
                    
                    logger.debug("Config change event scheduled for processing")
                finally:
                    # Always ensure we reset the flag
                    self.processing_event = False
                
    def _schedule_config_reload(self):
        """Schedule the config reload on the next event loop iteration."""
        try:
            # Get the loop from the controller if it exists and is running
            loop = getattr(self.controller, 'loop', None)
            if loop and loop.is_running():
                # Use call_soon_threadsafe which is safer than run_coroutine_threadsafe
                # This will simply schedule the function to be called on the next loop iteration
                loop.call_soon_threadsafe(self._handle_config_change)
            else:
                logger.warning("Event loop not available, config change will not be processed")
        except Exception as e:
            logger.error(f"Failed to schedule config reload: {e}")
    
    def _handle_config_change(self):
        """Schedule a coroutine to handle the config change safely."""
        try:
            # Create a task that we don't await directly - let the event loop handle it
            asyncio.create_task(self._safe_reload_config())
        except Exception as e:
            logger.error(f"Failed to create config reload task: {e}")
    
    async def _safe_reload_config(self):
        """Safely reload the config with timeout protection."""
        try:
            # Try to reload with a timeout
            await asyncio.wait_for(
                self.controller.handle_config_change(), 
                timeout=10
            )
        except asyncio.TimeoutError:
            logger.error("Config reload timed out after 10 seconds")
        except Exception as e:
            logger.error(f"Error during config reload: {e}")
            logger.error(traceback.format_exc())

class EnvironmentController:
    """
    Orchestrates the environmental control system.
    
    This controller coordinates the individual controllers (fan, humidity, temperature)
    and manages the overall system state and configuration.
    """
    
    def __init__(self, device_manager: DeviceManager):
        """Initialize the environment controller.
        
        Args:
            device_manager: The device manager instance
        """
        logger.info("Initializing Environment Controller")
        
        # Store device manager
        self.device_manager = device_manager
        
        # Get settings manager from device manager
        self.settings_manager = device_manager.settings_manager
        
        # Initialize InfluxDB manager
        from managers.influxdb_manager import influxdb_manager
        self.influxdb_manager = influxdb_manager
        
        # System state
        self.system_running = False
        self.last_measurement_time = 0
        self.last_log_time = 0
        self.measurement_interval = 5  # Default, will be updated from settings
        self.logging_interval = 30     # Default, will be updated from settings
        
        # Store event loop reference
        self.loop = asyncio.get_event_loop()
        
        # Initialize file watcher
        self.observer = None
        self.config_handler = None
        
        # Controllers will be initialized in start()
        self.fan_controller = None
        self.humidity_controller = None
        self.temperature_controller = None
        
        logger.info("Environment controller initialized")
    
    async def start(self):
        """Initialize the controller."""
        try:
            logger.info("Initializing Environment Controller")
            
            # Store the event loop for later use
            try:
                # Get the current event loop or create a new one if none exists
                self.loop = asyncio.get_running_loop()
                logger.info(f"Using existing event loop: {self.loop!r}")
            except RuntimeError:
                # No running event loop
                # This should not happen normally, but just in case
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                logger.info(f"Created new event loop: {self.loop!r}")
            
            # Initialize device manager first with timeout
            logger.info("Initializing device manager...")
            try:
                await asyncio.wait_for(self.device_manager.initialize(), timeout=30)
                logger.info("Device manager initialized successfully")
            except asyncio.TimeoutError:
                logger.error("Timeout initializing device manager")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize device manager: {e}")
                raise
                
            # Initialize controllers with proper error handling
            logger.info("Initializing controllers...")
            try:
                self.fan_controller = FanController(
                    fan=self.device_manager.fan,
                    settings_manager=self.settings_manager,
                    set_fan_speed_callback=self.device_manager.set_fan_speed
                )
                
                self.humidity_controller = HumidityController(
                    device_manager=self.device_manager
                )
                
                self.temperature_controller = TemperatureController(
                    device_manager=self.device_manager
                )
                logger.info("Controllers initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize controllers: {e}")
                logger.error(traceback.format_exc())
                raise
            
            # Initialize file watcher for config changes
            logger.info("Setting up config file watcher...")
            try:
                self.config_handler = ConfigFileHandler(self)
                self.observer = Observer()
                config_dir = os.path.dirname(self.settings_manager.config_path)
                
                # Make sure the config directory exists
                if not os.path.exists(config_dir):
                    os.makedirs(config_dir, exist_ok=True)
                    logger.info(f"Created config directory: {config_dir}")
                
                self.observer.schedule(self.config_handler, config_dir, recursive=False)
                self.observer.start()
                logger.info(f"Started file watcher for config directory: {config_dir}")
            except Exception as e:
                logger.error(f"Failed to set up config file watcher: {e}")
                logger.error(traceback.format_exc())
                # We can continue without the file watcher
            
            # Load initial settings
            logger.info("Loading initial configuration...")
            try:
                await asyncio.wait_for(self.load_config(), timeout=10)
                logger.info("Initial configuration loaded successfully")
            except asyncio.TimeoutError:
                logger.error("Timeout loading initial configuration")
                raise
            except Exception as e:
                logger.error(f"Failed to load initial configuration: {e}")
                logger.error(traceback.format_exc())
                raise
                
            logger.info("Environment controller initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Error initializing environment controller: {e}")
            logger.error(traceback.format_exc())
            raise
    
    async def load_config(self) -> bool:
        """Load configuration from settings."""
        try:
            # Load settings
            settings = await self.settings_manager.load_settings(force_reload=True)
            
            # Update intervals
            self.measurement_interval = settings.get('sensor', {}).get('measurement_interval', 5)
            self.logging_interval = settings.get('logging', {}).get('interval', 30)
            
            # Update individual controllers
            if self.fan_controller:
                await self.fan_controller.initialize_from_settings(settings)
            if self.humidity_controller:
                await self.humidity_controller.update_settings(settings)
            if self.temperature_controller:
                await self.temperature_controller.update_settings(settings)
            
            logger.info(f"Loaded settings - Measurement interval: {self.measurement_interval}s, Logging interval: {self.logging_interval}s")
            return True
            
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return False
    
    async def handle_config_change(self):
        """Handle changes to the configuration file."""
        try:
            logger.info("\nConfig changed, updating settings...")
            # Create a task with timeout to prevent blocking
            config_task = asyncio.create_task(self.load_config())
            try:
                # Wait for the task with a timeout
                await asyncio.wait_for(config_task, timeout=10)
                
                # Get current phase settings
                settings = await self.settings_manager.load_settings()
                current_phase = settings['environment']['current_phase']
                phase_settings = settings['environment']['phases'][current_phase]
                
                # Log the new setpoints
                rh_setpoint = phase_settings.get('rh_setpoint', 'unknown')
                co2_setpoint = phase_settings.get('co2_setpoint', 'unknown')
                temp_setpoint = phase_settings.get('temp_setpoint', 'unknown')
                
                logger.info(f"New setpoints - RH: {rh_setpoint}%, CO2: {co2_setpoint}ppm, Temp: {temp_setpoint}°C")
                
            except asyncio.TimeoutError:
                logger.error("Timeout while reloading configuration")
                # Cancel the task to avoid orphaned tasks
                config_task.cancel()
            
        except Exception as e:
            logger.error(f"Error checking for config updates: {e}")
            logger.error(traceback.format_exc())
    
    async def initialize_devices(self):
        """Initialize all devices."""
        try:
            # Initialize devices through device manager
            await self.device_manager.initialize()
            logger.info("All devices initialized")
            return True
        except Exception as e:
            logger.error(f"Error initializing devices: {e}")
            return False
    
    async def start_system(self):
        """Start the environmental control system."""
        try:
            logger.info("\n=== Starting Environmental Control System ===")
            
            # Start the system
            self.system_running = True
            
            # Create a watchdog mechanism to detect frozen state
            last_successful_cycle = time.time()
            watchdog_timeout = max(30, self.measurement_interval * 5)  # 5x the measurement interval or at least 30 seconds
            
            # Main control loop
            while self.system_running:
                try:
                    # Log the start of a cycle for debugging
                    cycle_start_time = time.time()
                    logger.debug(f"Starting control cycle at {datetime.now().isoformat()}")
                    
                    # Get measurements with timeout
                    try:
                        # Create a task for getting measurements
                        measurements_task = asyncio.create_task(self.device_manager.get_measurements())
                        # Wait for the task with a timeout
                        measurements = await asyncio.wait_for(
                            measurements_task,
                            timeout=max(5, self.measurement_interval)  # Use at least 5 seconds timeout
                        )
                    except asyncio.TimeoutError:
                        logger.warning("Timeout getting measurements, skipping this cycle")
                        await asyncio.sleep(1)  # Short sleep before trying again
                        continue
                    
                    if measurements:
                        co2, temp, rh = measurements
                        measurement_time = datetime.utcnow()
                        
                        logger.debug(f"Measurements: CO2={co2:.1f}ppm, Temp={temp:.1f}°C, RH={rh:.1f}%")
                        
                        # Apply control logic through individual controllers with timeouts
                        try:
                            # Temperature control
                            temp_control_task = asyncio.create_task(self.temperature_controller.control(temp))
                            await asyncio.wait_for(temp_control_task, timeout=5)
                        except asyncio.TimeoutError:
                            logger.warning("Timeout in temperature control")
                        except Exception as e:
                            logger.error(f"Error in temperature control: {e}")
                        
                        try:
                            # Humidity control
                            hum_control_task = asyncio.create_task(self.humidity_controller.control(rh))
                            await asyncio.wait_for(hum_control_task, timeout=5)
                        except asyncio.TimeoutError:
                            logger.warning("Timeout in humidity control")
                        except Exception as e:
                            logger.error(f"Error in humidity control: {e}")
                        
                        # Fan control (not async, but wrapping in try/except)
                        try:
                            self.fan_controller.update_co2_control(co2)
                        except Exception as e:
                            logger.error(f"Error in fan control: {e}")
                        
                        # Log data if interval has passed
                        current_time = time.time()
                        if current_time - self.last_log_time >= self.logging_interval:
                            try:
                                log_task = asyncio.create_task(self.log_data(co2, temp, rh, measurement_time))
                                await asyncio.wait_for(log_task, timeout=10)
                                self.last_log_time = current_time
                            except asyncio.TimeoutError:
                                logger.warning("Timeout logging data")
                            except Exception as e:
                                logger.error(f"Error logging data: {e}")
                        
                        # Update the last successful cycle time
                        last_successful_cycle = time.time()
                        cycle_duration = last_successful_cycle - cycle_start_time
                        logger.debug(f"Control cycle completed in {cycle_duration:.2f} seconds")
                    else:
                        logger.warning("No measurements available")
                    
                    # Check if we've been stuck too long
                    current_time = time.time()
                    if current_time - last_successful_cycle > watchdog_timeout:
                        logger.error(f"Watchdog detected: No successful cycle for {watchdog_timeout} seconds, resetting system")
                        # Try to reinitialize the device manager
                        try:
                            await self.device_manager.initialize()
                        except Exception as e:
                            logger.error(f"Error reinitializing device manager: {e}")
                        # Reset the watchdog timer to avoid continuous resets
                        last_successful_cycle = current_time
                    
                    # Calculate how long to sleep
                    # If the cycle took longer than the measurement interval, sleep for a minimum time
                    cycle_time = time.time() - cycle_start_time
                    sleep_time = max(1, self.measurement_interval - cycle_time)
                    
                    # Sleep for calculated time
                    logger.debug(f"Sleeping for {sleep_time:.2f} seconds")
                    await asyncio.sleep(sleep_time)
                    
                except asyncio.CancelledError:
                    # Handle cancellation explicitly
                    logger.info("Control loop task was cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in control loop: {e}")
                    logger.error(f"Stack trace: {traceback.format_exc()}")
                    # Wait before retrying, but not too long
                    await asyncio.sleep(min(5, self.measurement_interval))
            
            logger.info("Environmental control system stopped")
            return True
            
        except asyncio.CancelledError:
            logger.info("System startup was cancelled")
            return False
        except Exception as e:
            logger.error(f"Error starting system: {e}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            return False
    
    async def log_data(self, co2: float, temp: float, rh: float, timestamp: datetime):
        """Log environmental data to InfluxDB."""
        try:
            # Get current fan speed
            fan_speed = self.fan_controller.get_current_speed()
            
            # Get device states
            heater_state = await self.device_manager.get_device_state('heater')
            humidifier_state = await self.device_manager.get_device_state('humidifier')
            
            # Log to InfluxDB
            await self.influxdb_manager.write_measurement(
                co2=co2,
                temp=temp,
                rh=rh,
                fan_speed=fan_speed,
                heater_state=heater_state,
                humidifier_state=humidifier_state,
                timestamp=timestamp
            )
            
            logger.debug(f"Data logged to InfluxDB - CO2: {co2}ppm, Temp: {temp}°C, RH: {rh}%, Fan: {fan_speed}%")
            
        except Exception as e:
            logger.error(f"Error logging data: {e}")
    
    async def cleanup(self):
        """Clean up resources before shutdown."""
        logger.info("\n=== Cleaning up resources ===")
        
        # Stop the system
        self.system_running = False
        
        # Stop the file observer
        if self.observer and self.observer.is_alive():
            try:
                self.observer.stop()
                self.observer.join()
                logger.info("File observer stopped")
            except Exception as e:
                logger.error(f"Error stopping file observer: {e}")
        
        # Clean up device manager (which will clean up individual devices)
        try:
            self.device_manager.cleanup()
            logger.info("Device manager cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up device manager: {e}")
        
        logger.info("Cleanup completed") 