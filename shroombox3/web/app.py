from flask import Flask, render_template, jsonify, request, Response
import json
import os
import logging
import subprocess
import psutil
import time
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'settings.json')

def get_program_status():
    """Check if the main program is running."""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Get full command line as a string
                cmdline = ' '.join(proc.info.get('cmdline', []) or [])
                
                # More detailed debug logging
                logger.debug(f"Checking process - PID: {proc.info.get('pid')}, "
                           f"Name: {proc.info.get('name')}, "
                           f"Cmdline: {cmdline}")

                # Check if this is our main.py process
                if (proc.info.get('name', '').lower().startswith('python') and 
                    'main.py' in cmdline and 
                    'shroombox3' in cmdline):
                    logger.info(f"Found main process: PID={proc.info['pid']}")
                    return True, proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                logger.debug(f"Error checking process: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error checking process: {e}")
                continue
                
        logger.debug("Main process not found")
        return False, None
    except Exception as e:
        logger.error(f"Error in get_program_status: {e}")
        raise

def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=4)

@app.route('/')
def index():
    config = load_config()
    return render_template('index.html', config=config)

@app.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify(load_config())

@app.route('/api/settings', methods=['POST'])
def update_settings():
    config = load_config()
    updates = request.json
    
    if 'environment' in updates:
        config['environment'].update(updates['environment'])
    if 'humidifier' in updates:
        config['humidifier'].update(updates['humidifier'])
    
    save_config(config)
    return jsonify({"status": "success"})

@app.route('/api/phase', methods=['POST'])
def set_phase():
    phase = request.json.get('phase')
    config = load_config()
    config['environment']['current_phase'] = phase
    save_config(config)
    return jsonify({"status": "success"})

@app.route('/api/system/status')
def system_status():
    try:
        logger.info("Checking system status...")
        is_running, pid = get_program_status()
        logger.info(f"Status check result - Running: {is_running}, PID: {pid}")
        return jsonify({
            "running": is_running,
            "pid": pid
        })
    except Exception as e:
        logger.error(f"Error checking status: {str(e)}")
        return jsonify({
            "error": f"Status check failed: {str(e)}"
        }), 500

@app.route('/api/system/control', methods=['POST'])
def system_control():
    try:
        action = request.json.get('action')
        if action not in ['start', 'stop']:
            return jsonify({"error": f"Invalid action: {action}"}), 400

        if action == 'start':
            # Start using systemd
            try:
                subprocess.run(['sudo', 'systemctl', 'start', 'shroombox-main'], check=True)
                time.sleep(2)  # Wait for service to start
                return jsonify({"status": "started"})
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to start service: {e}")
                return jsonify({"error": "Failed to start service"}), 500

        elif action == 'stop':
            # Stop using systemd
            try:
                subprocess.run(['sudo', 'systemctl', 'stop', 'shroombox-main'], check=True)
                time.sleep(2)  # Wait for service to stop
                
                # Force fan stop after service stop
                try:
                    import RPi.GPIO as GPIO
                    GPIO.setmode(GPIO.BCM)
                    GPIO.setup(13, GPIO.OUT, initial=GPIO.LOW)
                    GPIO.output(13, GPIO.LOW)
                except Exception as e:
                    logger.error(f"Error stopping fan: {e}")
                
                return jsonify({"status": "stopped"})
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to stop service: {e}")
                return jsonify({"error": "Failed to stop service"}), 500

    except Exception as e:
        logger.error(f"System control error: {e}")
        return jsonify({"error": f"System control error: {e}"}), 500

# Add new endpoint for log streaming
@app.route('/api/logs')
def get_logs():
    def generate_logs():
        # Get last N lines first
        try:
            last_lines = subprocess.check_output(
                ['tail', '-n', '100', '/var/log/shroombox-main.log']
            ).decode('utf-8')
            # Send initial buffer
            for line in last_lines.splitlines():
                yield f"data: {line}\n\n"
        except Exception as e:
            logger.error(f"Error getting initial logs: {e}")

        # Then follow new lines
        log_command = f"tail -f /var/log/shroombox-main.log"
        process = subprocess.Popen(
            log_command.split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1  # Line buffered
        )
        
        try:
            while True:
                output = process.stdout.readline()
                if output:
                    yield f"data: {output.strip()}\n\n"
                else:
                    time.sleep(0.1)
        except GeneratorExit:
            # Clean up when client disconnects
            process.terminate()
            process.wait(timeout=5)
        except Exception as e:
            logger.error(f"Error in log streaming: {e}")
            if process:
                process.terminate()
                process.wait(timeout=5)
            
    return Response(generate_logs(), mimetype='text/event-stream')

@app.route('/log', methods=['POST'])
def log():
    """Receive log messages and write them to the system log file."""
    print("Received POST request to /log endpoint")  # Debug print
    try:
        data = request.get_json()
        message = data.get('message', '')
        print(f"Received message: {message}")  # Debug print
        
        # Write to the log file
        with open('/var/log/shroombox-main.log', 'a') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_line = f"{timestamp} - {message}\n"
            print(f"Writing to log: {log_line}")  # Debug print
            f.write(log_line)
            f.flush()  # Ensure it's written immediately
        
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"Error in /log endpoint: {e}")  # Debug print
        logger.error(f"Error writing to log: {e}")
        return jsonify({"error": str(e)}), 500

# Add at the bottom of app.py
if __name__ == '__main__':
    logger.info("Starting Shroombox Web Interface...")
    logger.info(f"Config file location: {CONFIG_PATH}")
    logger.info("Access the web interface at http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=True)
