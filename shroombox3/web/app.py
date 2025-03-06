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

# Add parent directory to Python path so we can import from root
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Get the parent directory path for file operations
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Initialize logging
logger = logging.getLogger('shroombox')
if not logger.handlers:
    logger.setLevel(logging.INFO)
    
    # Prevent Hypercorn from duplicating messages
    logging.getLogger('hypercorn.error').handlers = []
    logging.getLogger('hypercorn.access').handlers = []
    
    # Customize Hypercorn's startup message
    hypercorn_logger = logging.getLogger('hypercorn.error')
    hypercorn_logger.setLevel(logging.INFO)
    startup_handler = logging.StreamHandler()
    startup_handler.setFormatter(logging.Formatter('INFO: Shroombox web server started on %(message)s'))
    hypercorn_logger.addHandler(startup_handler)
    
    # Try system log directory first
    log_dir = '/var/log/shroombox'
    if not os.path.exists(log_dir) or not os.access(log_dir, os.W_OK):
        # Fall back to local log directory
        log_dir = os.path.join(BASE_DIR, 'logs')
        logger.info(f"Cannot access system log directory, using local directory: {log_dir}")
    
    # Create log directory if needed
    os.makedirs(log_dir, exist_ok=True)
    
    # Set up file handler
    log_file = os.path.join(log_dir, 'main.log')
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=1024*1024,  # 1MB
            backupCount=5,
            mode='a'
        )
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
    except PermissionError:
        logger.warning(f"Cannot write to {log_file}, falling back to console-only logging")
    
    # Always add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    logger.addHandler(console_handler)

# Make logger not buffer output
logger.propagate = False

# Set environment variable for other modules to use local log directory
os.environ['SHROOMBOX_LOG_DIR'] = log_dir

# Now we can safely import our local modules
from scd30_controller import SCD30Controller
from tapo_controller import TapoController
from main import EnvironmentController

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
    global controller, sensor
    try:
        # First initialize the sensor
        logger.info("Checking I2C bus before sensor initialization...")
        try:
            import subprocess
            result = subprocess.run(['i2cdetect', '-y', '1'], capture_output=True, text=True)
            logger.info(f"I2C devices found:\n{result.stdout}")
        except Exception as e:
            logger.warning(f"Could not check I2C bus: {e}")

        sensor = SCD30Controller()
        try:
            sensor_available = sensor.is_available()
            if not sensor_available:
                logger.warning("SCD30 sensor not available (expected at address 0x61), continuing in monitoring-only mode")
                logger.info("Please check: \n1. Power connections to the sensor\n2. I2C connections (SDA and SCL)\n3. Pull-up resistors on I2C lines")
        except Exception as e:
            logger.warning(f"Error checking SCD30 sensor (CRC error): {e}")
            sensor_available = False
            # Continue anyway with sensor marked as unavailable

        # Then initialize the controller with the sensor
        controller = EnvironmentController()
        await controller.start()  # Initialize async resources
        
        status = " (monitoring-only mode)" if not sensor_available else ""
        logger.info(f"Controller initialized successfully{status}")
        return controller
    except Exception as e:
        logger.error(f"Error initializing controller: {e}")
        return None

@app.before_serving
async def startup():
    """Initialize the controller before the first request."""
    await initialize_controller()

@app.after_serving
async def shutdown():
    """Cleanup when the server is shutting down."""
    if controller:
        await controller.cleanup()

# Add background task to keep the app running
async def keep_alive():
    """Keep the application running."""
    try:
        while not shutdown_event.is_set():
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass

@app.before_serving
async def start_background_tasks():
    """Start background tasks."""
    app.background_tasks = set()
    task = asyncio.create_task(keep_alive())
    app.background_tasks.add(task)

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
    """Get current settings including available devices."""
    try:
        with open(os.path.join(BASE_DIR, 'config', 'settings.json'), 'r') as f:
            settings = json.load(f)
        return jsonify(settings)
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings', methods=['POST'])
async def save_settings():
    """Save updated settings."""
    try:
        # Get the request data
        data = await request.get_json()
        
        # Log the received data for debugging
        logger.info(f"Received settings update request with data: {json.dumps(data, indent=2)}")
        
        # Validate the data structure
        if not isinstance(data, dict):
            logger.error("Invalid settings format: not a dictionary")
            return jsonify({'error': 'Invalid settings format'}), 400
            
        # Ensure numeric values are properly converted
        if 'environment' in data and 'phases' in data['environment']:
            for phase_name, phase_data in data['environment']['phases'].items():
                if 'temp_setpoint' in phase_data:
                    phase_data['temp_setpoint'] = float(phase_data['temp_setpoint'])
                if 'rh_setpoint' in phase_data:
                    phase_data['rh_setpoint'] = float(phase_data['rh_setpoint'])
                if 'co2_setpoint' in phase_data:
                    phase_data['co2_setpoint'] = int(phase_data['co2_setpoint'])
        else:
            logger.error("Missing environment or phases in settings data")
            return jsonify({'error': 'Missing environment or phases in settings data'}), 400
            
        # Load current settings first to compare and verify changes
        settings_file = os.path.join(BASE_DIR, 'config', 'settings.json')
        logger.info(f"Settings file path: {settings_file}")
        
        try:
            with open(settings_file, 'r') as f:
                current_settings = json.load(f)
                logger.info(f"Successfully loaded current settings from {settings_file}")
        except Exception as e:
            logger.error(f"Error reading current settings file: {e}")
            return jsonify({'error': f'Error reading settings file: {str(e)}'}), 500
            
        # Log what's changing for debugging purposes
        if 'environment' in data and 'phases' in data['environment']:
            current_phase = data['environment']['current_phase']
            logger.info(f"Current phase: {current_phase}")
            
            if current_phase in data['environment']['phases'] and current_phase in current_settings['environment']['phases']:
                old_settings = current_settings['environment']['phases'][current_phase]
                new_settings = data['environment']['phases'][current_phase]
                
                logger.info(f"Old settings for {current_phase}: {json.dumps(old_settings, indent=2)}")
                logger.info(f"New settings for {current_phase}: {json.dumps(new_settings, indent=2)}")
                
                for key in ['temp_setpoint', 'rh_setpoint', 'co2_setpoint']:
                    if key in old_settings and key in new_settings:
                        if old_settings[key] != new_settings[key]:
                            logger.info(f"Changing {key} from {old_settings[key]} to {new_settings[key]} for {current_phase} phase")
                        else:
                            logger.info(f"No change for {key}: remains {old_settings[key]}")
                    else:
                        logger.warning(f"Key {key} missing in either old or new settings")
            else:
                logger.warning(f"Phase {current_phase} not found in both old and new settings")
        
        # Save to file with proper synchronization
        try:
            # First write to a temporary file
            temp_file = f"{settings_file}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=4)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk
            
            # Then rename the temporary file to the actual file (atomic operation)
            os.replace(temp_file, settings_file)
            
            # Verify the file was written correctly
            with open(settings_file, 'r') as f:
                saved_data = json.load(f)
                
            # Check if the saved data matches what we intended to save
            if saved_data['environment']['current_phase'] != data['environment']['current_phase']:
                logger.error(f"Verification failed: current_phase mismatch after save")
                return jsonify({'error': 'Settings verification failed after save'}), 500
                
            current_phase = data['environment']['current_phase']
            for key in ['temp_setpoint', 'rh_setpoint', 'co2_setpoint']:
                if saved_data['environment']['phases'][current_phase][key] != data['environment']['phases'][current_phase][key]:
                    logger.error(f"Verification failed: {key} mismatch after save")
                    return jsonify({'error': 'Settings verification failed after save'}), 500
                    
            logger.info(f"Successfully wrote and verified settings to {settings_file}")
            
        except Exception as e:
            logger.error(f"Error writing settings file: {e}")
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
            return jsonify({'error': f'Error writing settings file: {str(e)}'}), 500
            
        logger.info(f"Settings updated successfully for {data['environment']['current_phase']} phase")
        
        # Force the controller to reload settings
        if controller:
            try:
                # Update the last modified time to force a reload
                controller.config_last_modified = 0
                logger.info("Reset controller config_last_modified to 0")
                
                # Force an immediate check for config updates
                asyncio.create_task(controller.check_config_updates())
                logger.info("Created task to check config updates")
                
                # After settings update, force a state check to apply new settings
                asyncio.create_task(controller.diagnose_heater_control())
                logger.info("Running heater diagnostic to apply new settings")
            except Exception as e:
                logger.error(f"Error notifying controller of settings change: {e}")
                return jsonify({'error': str(e), 'message': 'Settings saved but controller update failed'}), 500
        else:
            logger.warning("Controller not initialized, settings will be loaded on next startup")
            
        # Return success with the updated settings
        return jsonify({
            'success': True, 
            'message': 'Settings updated successfully',
            'settings': data
        })
        
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/terminal')
def terminal():
    def generate():
        log_file = '/var/log/shroombox/main.log'
        local_log_file = os.path.join(BASE_DIR, 'logs', 'main.log')
        
        # Try system log first, fall back to local log if permission denied
        if not os.path.exists(log_file) or not os.access(log_file, os.R_OK):
            logger.info(f"Cannot access {log_file}, falling back to {local_log_file}")
            # Create local logs directory if it doesn't exist
            os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)
            log_file = local_log_file
            
            # Create local log file if it doesn't exist
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
                                    yield f"data: {line.strip()}\n\n"
                            last_position = f.tell()
                            last_size = current_size
                    
                    # Send heartbeat
                    time.sleep(1)
                    yield "data: ♥\n\n"
                    
                except Exception as e:
                    logger.error(f"Error reading log file: {e}")
                    yield f"data: Error reading log file: {e}\n\n"
                    time.sleep(5)  # Wait before retrying
            
        except Exception as e:
            yield f"data: Error in log stream: {str(e)}\n\n"
            logger.error(f"Error in terminal stream: {e}")

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive'
        }
    )

@app.route('/api/status')
async def get_status():
    """Get current system status and readings."""
    try:
        if not controller:
            await initialize_controller()
            if not controller:  # If initialization failed
                return jsonify({'error': 'Failed to initialize controller'}), 500
            
        # Get current measurements
        measurements = await controller.get_measurements()
        if measurements:
            co2, temp, rh = measurements
        else:
            co2, temp, rh = 0, 0, 0

        # Get system status
        status = {
            'fanSpeed': controller.fan.get_speed() if hasattr(controller, 'fan') else 0,
            'heaterOn': controller.heater_on,
            'humidifierOn': controller.humidifier_on,
            'cpuTemp': get_cpu_temperature()
        }

        return jsonify({
            'readings': {
                'temperature': temp,
                'humidity': rh,
                'co2': co2
            },
            'status': status
        })
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/devices/scan', methods=['POST'])
def scan_devices():
    """Scan for Tapo devices and update settings."""
    try:
        # Create a TapoController instance
        tapo = TapoController(
            email=os.getenv('TAPO_EMAIL'),
            password=os.getenv('TAPO_PASSWORD')
        )
        
        # Run the scan_and_update_settings method in an async context
        success = asyncio.run(tapo.scan_and_update_settings('config/settings.json'))
        
        if success:
            return jsonify({"status": "success", "message": "Device scan completed successfully"})
        else:
            return jsonify({"status": "error", "message": "Device scan failed"}), 500
    except Exception as e:
        app.logger.error(f"Error during device scan: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/system/status')
async def get_system_status():
    """Get current system status including fan speed, device states, and CPU temp."""
    try:
        if not controller:
            return jsonify({'error': 'Controller not initialized'}), 500
            
        # Update device states from actual device status
        await controller.update_device_states()
        
        # Also update states in settings.json to keep it in sync
        try:
            settings_file = os.path.join(BASE_DIR, 'config', 'settings.json')
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                
            # Update device states in settings
            for device in settings.get('available_devices', []):
                if device.get('role') == 'heater':
                    device['state'] = controller.heater_on
                elif device.get('role') == 'humidifier':
                    device['state'] = controller.humidifier_on
            
            # Save updated settings
            with open(settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            logger.error(f"Error updating device states in settings: {e}")
        
        # Get CPU temperature
        cpu_temp = controller.fan.get_cpu_temp() if controller.fan else None
        
        # Get fan speed
        fan_speed = controller.fan_percentage
        
        return jsonify({
            'fan_speed': round(fan_speed, 1) if fan_speed is not None else 0,
            'cpu_temp': round(cpu_temp, 1) if cpu_temp else None,
            'heater': {
                'state': controller.heater_on,
                'text': 'ON' if controller.heater_on else 'OFF'
            },
            'humidifier': {
                'state': controller.humidifier_on,
                'text': 'ON' if controller.humidifier_on else 'OFF'
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({
            'fan_speed': 0,
            'cpu_temp': None,
            'heater': {'state': False, 'text': 'OFF'},
            'humidifier': {'state': False, 'text': 'OFF'}
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

def get_cpu_temperature():
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = float(f.read()) / 1000.0
        return round(temp, 1)
    except:
        return 0

@app.route('/api/measurements/latest')
async def get_latest_measurements():
    """Get latest measurements from the running system."""
    try:
        global controller
        if not controller:
            success = await initialize_controller()
            if not success:
                logger.warning("Controller initialization failed, falling back to InfluxDB")
                # Continue to InfluxDB fallback

        if controller and controller.sensor:
            try:
                # Use get_measurements() from the controller instead of direct sensor access
                measurements = await controller.get_measurements()
                if measurements:
                    co2, temp, rh = measurements
                    # Validate measurements before returning
                    if all(isinstance(x, (int, float)) for x in [co2, temp, rh]):
                        logger.info(f"Live measurements - Temp: {temp}°C, RH: {rh}%, CO2: {co2}ppm")
                        return jsonify({
                            'temperature': round(float(temp), 1),
                            'humidity': round(float(rh), 1),
                            'co2': round(float(co2), 1)
                        })
                    else:
                        logger.warning("Invalid sensor readings, falling back to InfluxDB")
                        raise ValueError("Invalid sensor readings")
            except Exception as e:
                logger.warning(f"Error reading from sensor: {e}, falling back to InfluxDB")
        
        logger.info("Using InfluxDB for measurements")
        
        # Fallback to InfluxDB
        client = InfluxDBClient(
            url=os.getenv('INFLUXDB_URL', 'http://localhost:8086'),
            token=os.getenv('INFLUXDB_TOKEN'),
            org=os.getenv('INFLUXDB_ORG')
        )
        
        query_api = client.query_api()
        query = f'''
            from(bucket: "{os.getenv('INFLUXDB_BUCKET')}")
            |> range(start: -5m)
            |> filter(fn: (r) => r["_measurement"] == "environment")
            |> filter(fn: (r) => r["_field"] == "temperature" or r["_field"] == "humidity" or r["_field"] == "co2")
            |> last()
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        
        result = query_api.query(query)
        measurements = {'temperature': None, 'humidity': None, 'co2': None}
        
        if len(result) > 0 and len(result[0].records) > 0:
            record = result[0].records[0]
            measurements = {
                'temperature': round(float(record.values.get('temperature', 0)), 1),
                'humidity': round(float(record.values.get('humidity', 0)), 1),
                'co2': round(float(record.values.get('co2', 0)), 1)
            }
        
        client.close()
        logger.info(f"Retrieved measurements: {measurements}")
        return jsonify(measurements)
        
    except Exception as e:
        logger.error(f"Error fetching measurements: {e}")
        return jsonify({
            'temperature': None,
            'humidity': None,
            'co2': None
        })

@app.route('/api/devices/status/<ip>')
async def get_device_status(ip):
    """Get the current status of a device."""
    try:
        if not controller:
            return jsonify({'error': 'Controller not initialized'}), 500
            
        # Use the tapo controller to check device status
        online = await controller.tapo.check_device_online(ip)
        return jsonify({'online': online})
        
    except Exception as e:
        logger.error(f"Error checking device status: {e}")
        return jsonify({'error': str(e)}), 500

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

@app.route('/api/system/reload-config', methods=['POST'])
async def reload_config():
    """Force the controller to reload configuration and return current status."""
    try:
        if not controller:
            await initialize_controller()
            if not controller:  # If initialization failed
                return jsonify({'error': 'Failed to initialize controller'}), 500
        
        # Reset the config last modified time to force a reload
        controller.config_last_modified = 0
        
        # Force an immediate check for config updates
        await controller.check_config_updates()
        
        # Run a heater diagnostic to ensure correct state
        await controller.diagnose_heater_control()
        
        # Get the latest measurements
        measurements = await controller.get_measurements()
        if measurements:
            co2, temp, rh = measurements
        else:
            co2, temp, rh = 0, 0, 0
            
        # Get the current settings
        with open(os.path.join(BASE_DIR, 'config', 'settings.json'), 'r') as f:
            settings = json.load(f)
        
        # Get current phase and setpoints
        current_phase = settings['environment']['current_phase']
        phase_settings = settings['environment']['phases'][current_phase]
        
        return jsonify({
            'status': 'success',
            'message': 'Config reloaded successfully',
            'readings': {
                'temperature': temp,
                'humidity': rh,
                'co2': co2
            },
            'devices': {
                'heater': controller.heater_on,
                'humidifier': controller.humidifier_on
            },
            'current_phase': current_phase,
            'setpoints': {
                'temperature': phase_settings['temp_setpoint'],
                'humidity': phase_settings['rh_setpoint'],
                'co2': phase_settings['co2_setpoint']
            }
        })
    except Exception as e:
        logger.error(f"Error reloading config: {e}")
        return jsonify({'error': str(e)}), 500

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