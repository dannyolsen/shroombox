# Shroombox Control System

A Raspberry Pi-based environmental control system for mushroom cultivation.

## Project Structure

The project has been reorganized into a more modular structure. For detailed information about the project structure, see [Project Structure Documentation](docs/project_structure.md).

```
shroombox3/
├── api/                  # API endpoints
├── backup/               # Backup files and deprecated code
├── config/               # Configuration files
│   ├── grafana/          # Grafana dashboard configurations
│   └── services/         # Systemd service files
├── data/                 # Data storage
├── devices/              # Device-specific code
├── docs/                 # Documentation
├── logs/                 # Log files
├── managers/             # High-level managers and controllers
├── scripts/              # Utility scripts
├── tests/                # Test files
│   └── unit/             # Unit tests
├── utils/                # Utility functions and helpers
└── web/                  # Web interface and frontend
```

## Key Components

### Devices

All hardware devices implement the `Device` interface defined in `devices/base.py`:

- **NoctuaFan**: Controls the PWM fan for air circulation and CO2 control
- **SCD30Controller**: Manages the SCD30 CO2, temperature, and humidity sensor
- **TapoController**: Controls Tapo smart plugs for heaters and humidifiers

### Managers

- **DeviceManager**: Provides a unified interface for accessing all hardware devices
- **SettingsManager**: Handles loading, saving, and updating configuration
- **Controllers**: High-level controllers for environment, fan, humidity, and temperature management

### Utils

- **singleton**: Decorator for implementing the singleton pattern
- **logging_setup**: Configures logging for the application

### Web Interface

The web interface provides a user-friendly way to monitor and control the system:

- **web_server.py**: Implements the web server and API endpoints
- **templates/**: Contains HTML templates for the web interface
- **static/**: Contains static files (CSS, JS, images)

## Usage

### Running the Main Application

```bash
python main.py
```

### Running the Web Interface

```bash
sudo systemctl start shroombox-web
```

### Running Tests

```bash
cd tests
python -m unittest discover
```

## Project Cleanup

The project has undergone a cleanup process to better organize files and directories. The cleanup plan is documented in [Cleanup Plan](cleanup_plan.md).

To run the cleanup script:

```bash
./scripts/cleanup_project.sh
```

To analyze directories for potential merges:

```bash
./scripts/analyze_directories.sh
```

## Development

When adding new devices:

1. Create a new class in the `devices` directory that implements the `Device` interface
2. Add the device to the `DeviceManager` class
3. Update the `__init__.py` files to expose the new device

## License

This project is licensed under the MIT License - see the LICENSE file for details. 