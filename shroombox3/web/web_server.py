from quart import Quart, jsonify, request, Response, render_template, make_response
import json
import os
import logging
import sys
import subprocess
import time
import signal
from quart_cors import cors
import asyncio
from influxdb_client import InfluxDBClient
from datetime import datetime, timedelta
from hypercorn.config import Config
from hypercorn.asyncio import serve
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List, Tuple
from functools import wraps
import psutil
import aiohttp
from managers.settings_manager import SettingsManager

# Add parent directory to Python path so we can import from root
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Import from new structure
from utils import logging_setup
from devices.fan import NoctuaFan
from devices.smart_plug import TapoController
from managers.device_manager import DeviceManager, device_manager
from managers.influxdb_manager import influxdb_manager
from managers.env_manager import env_manager
from managers.environment_controller import EnvironmentController

# Load environment variables from .env file
load_dotenv()

# Initialize log buffer and lock for Safari compatibility
import threading
log_buffer = []
log_buffer_lock = threading.Lock()
MAX_LOG_BUFFER_SIZE = 1000  # Maximum number of log entries to keep in memory

# Get the parent directory path for file operations
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Set up logging
os.makedirs('logs/web', exist_ok=True)  # For web server logs

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.handlers.RotatingFileHandler(
            'logs/web/api_requests.log',  # API request log
            maxBytes=1024*1024,  # 1MB per file
            backupCount=5,       # Keep 5 backup files
        ),
        logging.handlers.RotatingFileHandler(
            'logs/web/web_errors.log',  # Error log
            maxBytes=1024*1024,
            backupCount=5,
        )
    ]
)

# Set up loggers for different components
api_logger = logging.getLogger('shroombox.web.api')
api_logger.addHandler(logging.handlers.RotatingFileHandler(
    'logs/web/api_requests.log',
    maxBytes=1024*1024,
    backupCount=5
))

error_logger = logging.getLogger('shroombox.web.error')
error_logger.addHandler(logging.handlers.RotatingFileHandler(
    'logs/web/web_errors.log',
    maxBytes=1024*1024,
    backupCount=5
))

# Main web logger
logger = logging.getLogger('shroombox.web')
logger.addHandler(logging.handlers.RotatingFileHandler(
    'logs/web/web_server.log',
    maxBytes=1024*1024,
    backupCount=5
))

# Prevent duplicate logging
for logger in [api_logger, error_logger]:
    logger.propagate = False

logger.info("Starting Shroombox web server")

# Initialize Quart app
app = Quart(__name__,
    static_folder='static',  # Serve static files from the 'static' directory
    template_folder='templates'
)

# Simplified CORS setup
app = cors(app, allow_origin="*", allow_methods=["GET", "POST", "OPTIONS"])

# Global variables
controller = None
sensor = None
shutdown_event = asyncio.Event()
settings_manager = SettingsManager()

# Add global variables for the Tapo controller
tapo_controller = None
tapo_monitor_task = None

# Add signal handlers to prevent premature shutdown
def signal_handler(sig, frame):
    logger.info("Received shutdown signal, cleaning up...")
    if controller:
        asyncio.create_task(controller.cleanup())
    # Don't exit - let the service manager handle shutdown
    
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

async def initialize_controller():
    """Initialize the environment controller and sensor."""
    global controller, settings_manager
    try:
        # Use the global device_manager instance
        logger.info("Using global device_manager instance")
        settings_manager = device_manager.settings_manager
        
        # Initialize the controller with the device_manager
        controller = EnvironmentController(device_manager_instance=device_manager)
        await controller.start()
        
        logger.info("Controller initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing controller: {e}")
        return False

@app.before_serving
async def startup():
    """Initialize the controller before the first request."""
    await initialize_controller()

@app.after_serving
async def shutdown():
    """Cleanup when the server is shutting down."""
    global tapo_monitor_task
    
    logger.info("Shutting down web server...")
    
    # Set the shutdown event to stop background tasks
    shutdown_event.set()
    
    # Cancel the Tapo monitoring task if it exists
    if tapo_monitor_task:
        try:
            tapo_monitor_task.cancel()
            await asyncio.wait_for(tapo_monitor_task, timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
    
    # Clean up the controller
    if controller:
        await controller.cleanup()
    
    logger.info("Web server shutdown complete")

# Add background task to keep the app running
async def keep_alive():
    """Keep the application running."""
    try:
        while not shutdown_event.is_set():
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass

# Add background task to monitor Tapo device states
async def monitor_tapo_devices():
    """Monitor Tapo device states and update settings.json."""
    global tapo_controller
    
    try:
        logger.info("Starting Tapo device monitoring background task")
        
        # Create a TapoController instance if it doesn't exist
        if tapo_controller is None:
            tapo_controller = TapoController(
                email=os.getenv('TAPO_EMAIL'),
                password=os.getenv('TAPO_PASSWORD')
            )
        
        # Get the settings path
        settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'settings.json')
        
        # Start monitoring device states
        await tapo_controller.monitor_device_states(
            settings_path=settings_path,
            shutdown_event=shutdown_event
        )
    except asyncio.CancelledError:
        logger.info("Tapo device monitoring task cancelled")
    except Exception as e:
        logger.error(f"Error in Tapo device monitoring task: {e}")
    finally:
        # Clean up the Tapo controller
        if tapo_controller:
            tapo_controller.cleanup()
            logger.info("Tapo controller cleaned up")

@app.before_serving
async def start_background_tasks():
    """Start background tasks."""
    global tapo_monitor_task
    
    app.background_tasks = set()
    
    # Add keep_alive task
    keep_alive_task = asyncio.create_task(keep_alive())
    app.background_tasks.add(keep_alive_task)
    
    # Add Tapo device monitoring task
    tapo_monitor_task = asyncio.create_task(monitor_tapo_devices())
    app.background_tasks.add(tapo_monitor_task)
    logger.info("Started Tapo device monitoring background task")

@app.route('/safari-check')
async def safari_check():
    """Simple endpoint to check if Safari is working properly."""
    return jsonify({
        "status": "ok", 
        "message": "Safari compatibility check successful",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/')
async def index():
    """Render the main index page."""
    try:
        response = await make_response(await render_template('index.html'))
        
        # Set cache control headers to prevent caching
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['Last-Modified'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        return response
    except Exception as e:
        logger.error(f"Error rendering index: {e}", exc_info=True)
        return f"Error loading page: {str(e)}", 500

@app.route('/test')
async def test_page():
    """Render a simple test page."""
    try:
        response = await make_response(await render_template('test.html'))
        
        # Set cache control headers to prevent caching
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['Last-Modified'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        return response
    except Exception as e:
        logger.error(f"Error rendering test page: {e}", exc_info=True)
        return f"Error loading test page: {str(e)}", 500

@app.route('/simple')
async def simple_page():
    """Render a simplified control interface."""
    try:
        response = await make_response(await render_template('simple.html'))
        
        # Set cache control headers to prevent caching
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['Last-Modified'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        return response
    except Exception as e:
        logger.error(f"Error rendering simple page: {e}", exc_info=True)
        return f"Error loading simple page: {str(e)}", 500

@app.route('/api/settings', methods=['GET'])
async def get_settings():
    """Get settings from settings.json."""
    try:
        settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'settings.json')
        
        if not os.path.exists(settings_path):
            app.logger.warning(f"Settings file not found at {settings_path}")
            # Return default settings to avoid breaking the UI
            return jsonify({
                'environment': {
                    'current_phase': 'vegetative',
                    'phases': {
                        'vegetative': {
                            'temperature': 24,
                            'humidity': 85,
                            'co2': 800
                        },
                        'fruiting': {
                            'temperature': 22,
                            'humidity': 90,
                            'co2': 1000
                        }
                    }
                },
                'available_devices': [],
                'fan': {
                    'speed': 50,
                    'manual_mode': True
                },
                'message': 'Settings file not found, using default values'
            })
            
        with open(settings_path, 'r') as f:
            settings = json.load(f)
            
        return jsonify(settings)
    except Exception as e:
        app.logger.error(f"Error getting settings: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings', methods=['POST'])
async def update_settings():
    """Update settings in settings.json."""
    try:
        settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'settings.json')
        data = await request.get_json()
        
        # Check if settings file exists
        if os.path.exists(settings_path):
            # Load existing settings
            with open(settings_path, 'r') as f:
                settings = json.load(f)
                
            # Update settings with new data
            settings.update(data)
        else:
            # Create new settings file with provided data
            app.logger.info(f"Creating new settings file at {settings_path}")
            settings = data
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        
        # Save updated settings
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=4)
            
        return jsonify({'message': 'Settings updated successfully'})
    except Exception as e:
        app.logger.error(f"Error updating settings: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/devices', methods=['GET'])
async def get_devices():
    """Get all devices and their current states."""
    try:
        settings = await settings_manager.load_settings()
        devices = settings.get('available_devices', [])
        return jsonify(devices)
    except Exception as e:
        logger.error(f"Error getting devices: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/device/<ip>/state', methods=['POST'])
async def update_device_state(ip):
    """Update device state."""
    try:
        data = await request.get_json()
        new_state = data.get('state', False)
        
        # Update device state using device manager
        success = await device_manager.set_device_state('heater' if ip == HEATER_IP else 'humidifier', new_state)
        
        if success:
            return jsonify({'status': 'success'})
        else:
            return jsonify({'error': 'Failed to update device state'}), 500
    except Exception as e:
        logger.error(f"Error updating device state: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status')
async def get_status():
    """Get current system status and readings."""
    try:
        logger.info("get_status called")
        
        # Get current measurements from device manager
        measurements = await device_manager.get_measurements()
        logger.info(f"Device manager measurements: {measurements}")
        
        if measurements:
            co2, temp, rh = measurements
        else:
            # If no real-time measurements, try to get the latest from InfluxDB
            logger.info("No real-time measurements, trying InfluxDB")
            influx_data = await influxdb_manager.get_latest_measurements()
            logger.info(f"InfluxDB data: {influx_data}")
            
            if influx_data:
                logger.info(f"Using measurements from InfluxDB: {influx_data}")
                co2 = influx_data.get('co2', 0)
                temp = influx_data.get('temperature', 0)
                rh = influx_data.get('humidity', 0)
                
                # Also update the fan speed from InfluxDB
                if 'fan_speed' in influx_data:
                    logger.info(f"Setting fan speed to {influx_data.get('fan_speed', 0)}")
                    device_manager.fan.set_speed(influx_data.get('fan_speed', 0))
            else:
                logger.warning("No measurements available from any source")
                co2, temp, rh = 0, 0, 0

        # Get system status
        status = {
            'fanSpeed': device_manager.get_fan_speed(),
            'heaterOn': device_manager.get_heater_state(),
            'humidifierOn': device_manager.get_humidifier_state(),
            'cpuTemp': get_cpu_temperature()
        }
        logger.info(f"System status: {status}")

        return jsonify({
            'readings': {
                'temperature': temp,
                'humidity': rh,
                'co2': co2
            },
            'status': status
        })
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/devices/scan', methods=['POST'])
async def scan_devices():
    """Scan for Tapo devices and update settings."""
    global tapo_controller
    
    try:
        # Check if we should force a new scan
        force_scan = request.args.get('force_scan', 'false').lower() == 'true'
        
        # Use the global TapoController instance or create a new one if it doesn't exist
        if tapo_controller is None:
            app.logger.info("Initializing TapoController for device scan")
            tapo_controller = TapoController(
                email=os.getenv('TAPO_EMAIL'),
                password=os.getenv('TAPO_PASSWORD')
            )
        
        # Get the settings path
        settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'settings.json')
        
        app.logger.info(f"Starting device scan (force_scan={force_scan})")
        
        # Create a background task for scanning to avoid blocking the response
        # This allows us to return immediately while the scan continues in the background
        async def background_scan():
            try:
                # Run the scan_and_update_settings method
                success = await tapo_controller.scan_and_update_settings(settings_path, force_scan)
                app.logger.info(f"Background device scan completed: {'success' if success else 'failed'}")
            except Exception as e:
                app.logger.error(f"Error in background device scan: {e}")
        
        # Start the background task
        asyncio.create_task(background_scan())
        
        # Return immediately with a success message
        return jsonify({
            "status": "success", 
            "message": "Device scan started in background",
            "background": True
        })
        
    except Exception as e:
        app.logger.error(f"Error starting device scan: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/system/status')
async def get_system_status():
    """Get system status including device states."""
    try:
        # Get settings
        settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'settings.json')
        
        if not os.path.exists(settings_path):
            app.logger.warning(f"Settings file not found at {settings_path}")
            # Return default status to avoid breaking the UI
            return jsonify({
                'heater': {'state': False, 'device': None},
                'humidifier': {'state': False, 'device': None},
                'fan': {'speed': 0, 'manual_mode': False},
                'cpu_temp': get_cpu_temperature(),
                'message': 'Settings file not found, using default values'
            })
            
        with open(settings_path, 'r') as f:
            settings = json.load(f)
            
        # Get device states
        heater_device = None
        humidifier_device = None
        
        if 'available_devices' in settings:
            for device in settings['available_devices']:
                if device.get('role') == 'heater':
                    heater_device = device
                elif device.get('role') == 'humidifier':
                    humidifier_device = device
        
        # Get fan settings
        fan_settings = {
            'speed': 0,
            'manual_mode': False
        }
        
        if 'fan' in settings:
            fan_settings = settings['fan']
        
        # Build response
        response = {
            'heater': {
                'state': heater_device.get('state', False) if heater_device else False,
                'device': heater_device
            },
            'humidifier': {
                'state': humidifier_device.get('state', False) if humidifier_device else False,
                'device': humidifier_device
            },
            'fan': fan_settings,
            'cpu_temp': get_cpu_temperature()
        }
        
        return jsonify(response)
        
    except Exception as e:
        app.logger.error(f"Error getting system status: {str(e)}")
        # Return default status to avoid breaking the UI
        return jsonify({
            'heater': {'state': False, 'device': None},
            'humidifier': {'state': False, 'device': None},
            'fan': {'speed': 0, 'manual_mode': False},
            'cpu_temp': get_cpu_temperature(),
            'error': str(e)
        })

@app.route('/api/system/control', methods=['POST'])
async def system_control():
    """Start or stop the control system."""
    try:
        data = await request.get_json()
        action = data.get('action')
        if action not in ['start', 'stop']:
            return jsonify({'error': 'Invalid action'}), 400

        if action == 'start':
            # Initialize controller if needed
            if not controller:
                await initialize_controller()
            return jsonify({'success': True})
            
        else:  # stop
            if controller:
                await controller.stop_system()  # This should just stop control logic, not services
            return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error controlling system: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/fan/control', methods=['POST'])
async def fan_control():
    """Control fan speed."""
    try:
        data = await request.get_json()
        speed = data.get('speed', 0)
        
        logger.info(f"Setting fan speed to {speed}%")
        
        # Use the device_manager to set fan speed
        try:
            await device_manager.set_fan_speed(speed)
            
            # If controller exists, update its fan_percentage to keep in sync
            if controller:
                controller.fan_percentage = speed
                logger.info(f"Updated controller fan_percentage to {speed}%")
            
            # Get the current fan speed from the device manager to confirm it was set
            current_speed = device_manager.get_fan_speed()
            logger.info(f"Fan speed successfully set to {current_speed}%")
                
            return jsonify({
                'success': True, 
                'message': f'Fan speed set to {current_speed}%',
                'current_speed': current_speed
            })
        except Exception as e:
            logger.error(f"Error setting fan speed: {e}")
            return jsonify({'error': f'Failed to set fan speed: {str(e)}'}), 500
        
    except Exception as e:
        logger.error(f"Error in fan control endpoint: {e}")
        return jsonify({'error': str(e)}), 500

def get_cpu_temperature():
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = float(f.read()) / 1000.0
        return round(temp, 1)
    except:
        return 0

# Define the path to the measurements file
MEASUREMENTS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'measurements.json')

@app.route('/api/measurements/latest')
async def get_latest_measurements():
    """Get latest sensor measurements."""
    try:
        logger.info("get_latest_measurements called")
        
        # Default sensor status
        sensor_status = {
            'available': False,
            'message': 'Sensor not initialized'
        }
        
        # Try to get measurements from the sensor first to check if it's working
        if device_manager.sensor:
            try:
                # Try to get measurements directly to verify the sensor is working
                measurements = await device_manager.sensor.get_measurements()
                if measurements:
                    # If we got measurements, the sensor is working
                    sensor_status['available'] = True
                    sensor_status['message'] = 'Sensor connected and working'
                    logger.info(f"Sensor is working, got measurements: {measurements}")
                else:
                    # If we didn't get measurements, the sensor might be having issues
                    sensor_status['available'] = False
                    sensor_status['message'] = 'Sensor not providing measurements'
                    logger.warning("Sensor returned None for measurements")
            except Exception as e:
                logger.warning(f"Error getting measurements from sensor: {e}")
                sensor_status['available'] = False
                sensor_status['message'] = f'Sensor error: {str(e)}'
        else:
            sensor_status['message'] = 'No sensor configured'
            logger.warning("No sensor configured in device manager")
        
        # First try to get measurements from the file
        try:
            if os.path.exists(MEASUREMENTS_FILE):
                with open(MEASUREMENTS_FILE, 'r') as f:
                    file_data = json.load(f)
                    
                # Check if data is fresh (less than 30 seconds old)
                if 'unix_timestamp' in file_data:
                    age = time.time() - file_data['unix_timestamp']
                    if age < 30:  # 30 seconds
                        logger.info(f"Using measurements from file (age: {age:.1f}s)")
                        
                        # Add age to the response
                        file_data['cache_age'] = age
                        
                        # Use fan_speed from measurements.json if available, otherwise get from device manager
                        if 'fan_speed' not in file_data:
                            file_data['fan_speed'] = round(float(device_manager.get_fan_speed()), 1)
                        else:
                            # Ensure fan_speed is rounded to 1 decimal place
                            file_data['fan_speed'] = round(float(file_data['fan_speed']), 1)
                        
                        # Add sensor status
                        file_data['sensor_status'] = sensor_status
                        
                        return jsonify(file_data)
                    else:
                        logger.info(f"File measurements are stale ({age:.1f}s old), trying real-time")
        except Exception as e:
            logger.warning(f"Error reading measurements from file: {e}")
        
        # If file doesn't exist or data is stale, try to get measurements from device manager (real-time)
        measurements = await device_manager.get_measurements()
        logger.info(f"Device manager measurements: {measurements}")
        
        if measurements:
            co2, temp, rh = measurements
            
            # Round values for display
            co2 = round(co2) if co2 is not None else None
            temp = round(temp, 1) if temp is not None else None
            rh = round(rh, 1) if rh is not None else None
            
            # Get fan speed from device manager and round to 1 decimal place
            fan_speed = round(float(device_manager.get_fan_speed()), 1)
            
            # If we got measurements, the sensor is available
            sensor_status['available'] = True
            sensor_status['message'] = 'Sensor connected and working'
            
            return jsonify({
                'co2': co2,
                'temperature': temp,
                'humidity': rh,
                'fan_speed': fan_speed,
                'timestamp': datetime.now().isoformat(),
                'source': 'sensor',
                'sensor_status': sensor_status
            })
        else:
            # Try to get cached measurements from device manager
            logger.info("No real-time measurements, trying device manager cache")
            cached_data = await device_manager.get_cached_measurements()
            
            if cached_data['is_fresh']:
                logger.info(f"Using cached measurements from device manager: {cached_data}")
                
                # Get fan speed from device manager and round to 1 decimal place
                fan_speed = round(float(device_manager.get_fan_speed()), 1)
                
                return jsonify({
                    'co2': round(cached_data['co2']) if cached_data['co2'] is not None else None,
                    'temperature': round(cached_data['temperature'], 1) if cached_data['temperature'] is not None else None,
                    'humidity': round(cached_data['humidity'], 1) if cached_data['humidity'] is not None else None,
                    'fan_speed': fan_speed,
                    'timestamp': datetime.now().isoformat(),
                    'source': 'cache',
                    'cache_age': cached_data['age'],
                    'sensor_status': sensor_status
                })
            
            # If no cached data, try to get the latest from InfluxDB
            logger.info("No cached measurements, trying InfluxDB")
            influx_data = await influxdb_manager.get_latest_measurements()
            logger.info(f"InfluxDB data: {influx_data}")
            
            if influx_data:
                logger.info(f"Using measurements from InfluxDB: {influx_data}")
                
                # Ensure fan_speed is rounded to 1 decimal place
                if 'fan_speed' in influx_data:
                    influx_data['fan_speed'] = round(float(influx_data['fan_speed']), 1)
                else:
                    influx_data['fan_speed'] = round(float(device_manager.get_fan_speed()), 1)
                
                return jsonify({
                    'co2': influx_data.get('co2'),
                    'temperature': influx_data.get('temperature'),
                    'humidity': influx_data.get('humidity'),
                    'fan_speed': influx_data.get('fan_speed'),
                    'timestamp': datetime.now().isoformat(),
                    'source': 'influxdb',
                    'sensor_status': sensor_status
                })
            else:
                # If no measurements available from any source
                logger.warning("No measurements available from any source")
                return jsonify({
                    'co2': None,
                    'temperature': None,
                    'humidity': None,
                    'fan_speed': 0.0,
                    'timestamp': datetime.now().isoformat(),
                    'message': 'No measurements available',
                    'sensor_status': sensor_status
                })
    except Exception as e:
        logger.error(f"Error getting latest measurements: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/devices/status/<ip>')
async def get_device_status(ip):
    """Get the current status of a device."""
    global tapo_controller
    
    try:
        # Use the global TapoController instance or create a new one if it doesn't exist
        if tapo_controller is None:
            tapo_controller = TapoController(
                email=os.getenv('TAPO_EMAIL'),
                password=os.getenv('TAPO_PASSWORD')
            )
            
        # Get the device state
        state = await tapo_controller.get_device_state(ip)
        
        # If state is None, the device might be offline
        if state is None:
            return jsonify({'online': False, 'state': None})
        
        return jsonify({'online': True, 'state': state})
        
    except Exception as e:
        logger.error(f"Error checking device status: {e}")
        return jsonify({'error': str(e), 'online': False, 'state': None}), 500

# Simplified after_request handler
@app.after_request
async def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    
    # Add cache prevention headers to all API responses
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['X-Accel-Expires'] = '0'
        
        # Add a timestamp to prevent browser caching
        response.headers['Last-Modified'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    return response

@app.route('/health')
async def health_check():
    """Simple health check endpoint."""
    return jsonify({'status': 'ok'})

@app.route('/service-worker.js')
async def service_worker():
    """Serve service worker from root path."""
    try:
        with open(os.path.join(BASE_DIR, 'web', 'static', 'service-worker.js'), 'r') as f:
            content = f.read()
        
        response = await make_response(content)
        response.headers['Content-Type'] = 'application/javascript'
        response.headers['Cache-Control'] = 'no-cache'
        return response
    except Exception as e:
        logger.error(f"Error serving service worker: {e}")
        return "", 404

@app.route('/api/logs/stream')
async def log_stream():
    """Stream logs to the frontend."""
    async def generate():
        log_file = os.path.join(BASE_DIR, 'logs', 'main.log')
        
        # Create logs directory if it doesn't exist
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # Create log file if it doesn't exist
        if not os.path.exists(log_file):
            open(log_file, 'a').close()
        
        # Send initial connection message
        yield "data: Connected to log stream\n\n"
        
        try:
            last_position = 0
            last_size = 0
            
            while True:
                try:
                    # Check if file exists and get current size
                    current_size = os.path.getsize(log_file) if os.path.exists(log_file) else 0
                    
                    # If file was truncated or deleted, reset position
                    if current_size < last_size:
                        last_position = 0
                        last_size = 0
                        yield "data: Log file was truncated, resetting...\n\n"
                    
                    # If file has new content
                    if current_size > last_position:
                        with open(log_file, 'r') as f:
                            f.seek(last_position)
                            new_lines = f.readlines()
                            for line in new_lines:
                                if line.strip():
                                    # Add to log buffer for Safari compatibility
                                    with log_buffer_lock:
                                        log_buffer.append(line.strip())
                                        # Keep buffer size limited
                                        if len(log_buffer) > MAX_LOG_BUFFER_SIZE:
                                            log_buffer.pop(0)
                                    yield f"data: {line.strip()}\n\n"
                            last_position = f.tell()
                            last_size = current_size
                    
                    # Send heartbeat every 5 seconds
                    await asyncio.sleep(5)
                    yield "data: ♥\n\n"
                    
                except Exception as e:
                    logger.error(f"Error reading log file: {e}")
                    yield f"data: Error reading log file: {e}\n\n"
                    await asyncio.sleep(5)  # Wait before retrying
            
        except Exception as e:
            yield f"data: Error in log stream: {str(e)}\n\n"
            logger.error(f"Error in log stream: {e}")

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Content-Type': 'text/event-stream'
        }
    )

@app.route('/api/logging/levels', methods=['GET'])
async def get_logging_levels():
    """Get current logging levels for all loggers."""
    loggers = {
        'shroombox': logging.getLogger('shroombox').level,
        'shroombox.sensor': logging.getLogger('shroombox.sensor').level,
        'shroombox.device': logging.getLogger('shroombox.device').level,
        'shroombox.web': logging.getLogger('shroombox.web').level
    }
    
    # Convert numeric levels to names
    level_names = {
        logging.DEBUG: 'DEBUG',
        logging.INFO: 'INFO',
        logging.WARNING: 'WARNING',
        logging.ERROR: 'ERROR',
        logging.CRITICAL: 'CRITICAL'
    }
    
    return jsonify({name: level_names.get(level, level) for name, level in loggers.items()})

@app.route('/api/logging/levels', methods=['POST'])
async def set_logging_levels():
    """Set logging levels for specified loggers."""
    data = await request.get_json()
    
    # Map level names to numeric values
    level_values = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    # Update logger levels
    for logger_name, level_name in data.items():
        if logger_name.startswith('shroombox') and level_name in level_values:
            logger = logging.getLogger(logger_name)
            logger.setLevel(level_values[level_name])
            
    return jsonify({'success': True})

@app.route('/logging')
async def logging_page():
    """Render the logging control page."""
    try:
        response = await make_response(await render_template('logging.html'))
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        return response
    except Exception as e:
        logger.error(f"Error rendering logging page: {e}", exc_info=True)
        return f"Error loading page: {str(e)}", 500

@app.route('/env-settings')
async def env_settings_page():
    """Render the environment settings page."""
    try:
        return await render_template('env_settings.html')
    except Exception as e:
        logger.error(f"Error rendering environment settings page: {e}")
        return "Error loading environment settings page", 500

# Add a route to explicitly serve the main.js file
@app.route('/static/js/main.js')
async def serve_main_js():
    try:
        with open(os.path.join(current_dir, 'static', 'js', 'main.js'), 'r') as f:
            content = f.read()
        
        response = await make_response(content)
        response.headers['Content-Type'] = 'application/javascript'
        response.headers['Cache-Control'] = 'no-cache'
        return response
    except Exception as e:
        logger.error(f"Error serving main.js: {e}")
        return "", 404

@app.route('/api/logs/latest')
async def get_latest_logs():
    """Endpoint for Safari browsers to fetch latest logs without streaming."""
    try:
        count = int(request.args.get('count', '10'))
        # Cap the count to avoid excessive responses
        count = min(count, 50)
        
        # Get the last N lines from the log buffer
        latest_logs = []
        with log_buffer_lock:
            # Get the most recent logs from the circular buffer
            if log_buffer:
                latest_logs = list(log_buffer)[-count:]
        
        return jsonify(latest_logs)
    except Exception as e:
        app.logger.error(f"Error fetching latest logs: {e}")
        return jsonify([f"Error fetching logs: {str(e)}"]), 500

@app.route('/api/devices/control', methods=['POST'])
async def control_device():
    """Control a device (turn it on or off)."""
    try:
        if not controller:
            return jsonify({'error': 'Controller not initialized'}), 500
            
        data = await request.get_json()
        device_role = data.get('device')
        state = data.get('state')
        
        if not device_role or state is None:
            return jsonify({'error': 'Missing device or state parameter'}), 400
            
        if device_role not in ['heater', 'humidifier']:
            return jsonify({'error': 'Invalid device role'}), 400
            
        # Control the device
        success = False
        if device_role == 'heater':
            success = await controller.set_heater_state(state)
        elif device_role == 'humidifier':
            success = await controller.set_humidifier_state(state)
            
        if success:
            # Get the updated device state
            device_state = controller.heater_on if device_role == 'heater' else controller.humidifier_on
            return jsonify({
                'success': True,
                'device': device_role,
                'state': device_state,
                'text': 'ON' if device_state else 'OFF'
            })
        else:
            return jsonify({'error': f'Failed to set {device_role} state'}), 500
            
    except Exception as e:
        logger.error(f"Error controlling device: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/env/status')
async def get_env_status():
    """Check if the .env file exists and return its status."""
    try:
        exists = await env_manager.env_file_exists()
        return jsonify({
            "exists": exists,
            "path": env_manager.env_path
        })
    except Exception as e:
        logger.error(f"Error checking .env status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/env/variables')
async def get_env_variables():
    """Get all environment variables from the .env file."""
    try:
        env_vars = await env_manager.load_env_vars()
        
        # Mask sensitive values
        masked_vars = {}
        for key, value in env_vars.items():
            if 'password' in key.lower() or 'token' in key.lower() or 'secret' in key.lower():
                masked_vars[key] = '********'  # Mask sensitive values
            else:
                masked_vars[key] = value
        
        return jsonify(masked_vars)
    except Exception as e:
        logger.error(f"Error getting environment variables: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/env/variables', methods=['POST'])
async def update_env_variables():
    """Update environment variables in the .env file."""
    try:
        data = await request.get_json()
        
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid data format. Expected a dictionary."}), 400
        
        # Update environment variables
        success = await env_manager.update_env_vars(data)
        
        if success:
            # Reload environment variables to apply changes
            from dotenv import load_dotenv
            load_dotenv(override=True)
            
            return jsonify({"success": True, "message": "Environment variables updated successfully."})
        else:
            return jsonify({"success": False, "message": "Failed to update environment variables."}), 500
    except Exception as e:
        logger.error(f"Error updating environment variables: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/env/template')
async def get_env_template():
    """Get a template for the .env file with required variables."""
    try:
        # Define the template with default values
        template = {
            "TAPO_EMAIL": "",
            "TAPO_PASSWORD": "",
            "INFLUXDB_URL": "http://localhost:8086",
            "INFLUXDB_TOKEN": "",
            "INFLUXDB_ORG": "supershrooms",
            "INFLUXDB_BUCKET": "test"
        }
        
        # If .env file exists, merge with existing values
        if await env_manager.env_file_exists():
            existing_vars = await env_manager.load_env_vars()
            for key in template:
                if key in existing_vars:
                    # Don't expose actual passwords or tokens
                    if 'password' in key.lower() or 'token' in key.lower() or 'secret' in key.lower():
                        template[key] = '********'
                    else:
                        template[key] = existing_vars[key]
        
        return jsonify(template)
    except Exception as e:
        logger.error(f"Error getting environment template: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/devices/all')
async def get_all_devices():
    """Get all devices and their current states from settings.json."""
    try:
        # Get the settings path
        settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'settings.json')
        
        # Read the settings file
        with open(settings_path, 'r') as f:
            settings = json.load(f)
        
        # Extract available devices
        devices = settings.get('available_devices', [])
        
        # Return the devices
        return jsonify({
            'status': 'success',
            'devices': devices
        })
    except Exception as e:
        logger.error(f"Error getting all devices: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/devices/control/direct', methods=['POST'])
async def control_device_direct():
    """Control a device directly by IP address."""
    global tapo_controller
    
    try:
        # Get request data
        data = await request.get_json()
        ip = data.get('ip')
        state = data.get('state')
        
        # Validate input
        if not ip or state is None:
            return jsonify({'status': 'error', 'message': 'Missing ip or state parameter'}), 400
        
        # Ensure tapo_controller is initialized
        if tapo_controller is None:
            tapo_controller = TapoController(
                email=os.getenv('TAPO_EMAIL'),
                password=os.getenv('TAPO_PASSWORD')
            )
        
        # Set device state
        success = await tapo_controller.set_device_state(ip, state)
        
        if success:
            # Get the updated state to confirm
            current_state = await tapo_controller.get_device_state(ip)
            
            # Update settings.json
            settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'settings.json')
            try:
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                
                # Find the device in available_devices and update its state
                for device in settings.get('available_devices', []):
                    if device.get('ip') == ip:
                        device['state'] = current_state
                        break
                
                # Write updated settings
                with open(settings_path, 'w') as f:
                    json.dump(settings, f, indent=4)
                
                logger.info(f"Updated device state in settings.json: {ip} -> {current_state}")
            except Exception as e:
                logger.warning(f"Error updating settings.json: {e}")
            
            return jsonify({
                'status': 'success',
                'ip': ip,
                'state': current_state
            })
        else:
            return jsonify({'status': 'error', 'message': f'Failed to set device state for {ip}'}), 500
    
    except Exception as e:
        logger.error(f"Error controlling device directly: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/settings')
async def settings_page():
    """Render the settings page."""
    try:
        return await render_template('settings.html')
    except Exception as e:
        logger.error(f"Error rendering settings page: {e}")
        return "Error loading settings page", 500

@app.route('/api/grafana/token')
def get_grafana_token():
    """Return the Grafana API token from environment variables."""
    token = os.getenv('GRAFANA_API_TOKEN')
    if token:
        return jsonify({'token': token})
    else:
        return jsonify({'error': 'Grafana token not configured'}), 404

@app.route('/grafana')
async def grafana_page():
    """Render the standalone Grafana dashboard page."""
    return await render_template('grafana.html')

@app.route('/api/devices/available', methods=['GET'])
async def get_available_devices():
    """Get available devices from settings file."""
    try:
        settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'settings.json')
        
        if not os.path.exists(settings_path):
            app.logger.warning(f"Settings file not found at {settings_path}")
            # Return empty data but with a 200 status code to avoid breaking the UI
            return jsonify({
                'devices': [],
                'last_scan_time': None,
                'device_count': 0,
                'message': 'Settings file not found, but continuing with empty device list'
            }), 200
            
        with open(settings_path, 'r') as f:
            settings = json.load(f)
            
        # Extract available devices from settings
        available_devices = []
        if 'available_devices' in settings:
            available_devices = settings['available_devices']
            
        # Get last scan time if available
        last_scan_time = None
        if 'tapo' in settings and 'last_scan_time' in settings['tapo']:
            last_scan_time = settings['tapo']['last_scan_time']
        elif 'last_device_scan' in settings and 'timestamp' in settings['last_device_scan']:
            last_scan_time = settings['last_device_scan']['timestamp']
            
        # Get device count if available
        device_count = len(available_devices)
        
        return jsonify({
            'devices': available_devices,
            'last_scan_time': last_scan_time,
            'device_count': device_count
        })
        
    except Exception as e:
        app.logger.error(f"Error getting available devices: {str(e)}")
        # Return empty data but with a 200 status code to avoid breaking the UI
        return jsonify({
            'devices': [],
            'last_scan_time': None,
            'device_count': 0,
            'message': f'Error retrieving devices: {str(e)}'
        }), 200

if __name__ == '__main__':
    config = Config()
    config.bind = ["0.0.0.0:5000"]
    config.use_reloader = True  # Enable reloader for development
    config.accesslog = "-"      # Log to stdout
    config.errorlog = "-"       # Log errors to stdout
    config.debug = True         # Enable debug mode
    config.loglevel = "info"    # Set log level to info

    try:
        logger.info("Starting Hypercorn server...")
        asyncio.run(serve(app, config))
    except Exception as e:
        logger.error(f"Fatal error in web server: {e}")
        if controller:
            asyncio.run(controller.cleanup())
        raise  # Re-raise the exception to ensure the process exits 