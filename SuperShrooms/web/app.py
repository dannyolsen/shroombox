from flask import Flask, render_template, jsonify, request
import json
import os
import logging

app = Flask(__name__)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'settings.json')

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

# Add at the bottom of app.py
if __name__ == '__main__':
    logger.info("Starting Shroombox Web Interface...")
    logger.info(f"Config file location: {CONFIG_PATH}")
    logger.info("Access the web interface at http://localhost:5000")
    app.run(host='0.0.0.0', port=5000)