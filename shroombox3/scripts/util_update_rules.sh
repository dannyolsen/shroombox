#!/bin/bash

# Script to update Cursor rules

# Create bestpractices.mdc
cat > .cursor/rules/bestpractices.mdc << 'EOL'
# Best Practices

This rule ensures code quality, maintainability, and stability throughout the Shroombox project.

## Code Structure
- Use the singleton pattern for managers (DeviceManager, SettingsManager, etc.)
- Implement proper error handling with specific exceptions and meaningful error messages
- Follow PEP 8 style guidelines for Python code
- Keep functions focused on a single responsibility
- Use type hints to improve code readability and IDE support

## File Organization
- Group related functionality in appropriate directories
- Use consistent naming conventions (as defined in FOLDER_DESCRIPTION files)
- Avoid duplicate code and files across the project
- Maintain a clear separation between core functionality and utilities

## Performance & Stability
- Cache expensive operations when appropriate
- Implement timeouts for network operations
- Use atomic file operations when writing to configuration or data files
- Add graceful degradation when components fail (e.g., sensor fallbacks)
- Include logging at appropriate levels for debugging and monitoring

## Examples
```python
# Good: Singleton pattern for managers
class DeviceManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DeviceManager, cls).__new__(cls)
            cls._instance.initialize()
        return cls._instance
        
# Good: Atomic file writing
def save_measurements(data, filepath):
    temp_file = f"{filepath}.tmp"
    try:
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(temp_file, filepath)  # Atomic operation
    except Exception as e:
        logger.error(f"Failed to save measurements: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)
        raise
```
EOL

# Create documentation.mdc
cat > .cursor/rules/documentation.mdc << 'EOL'
# Documentation Guidelines

This rule ensures comprehensive and up-to-date documentation throughout the Shroombox project.

## Documentation Types

### Folder Documentation
- Each folder must have a `1FOLDER_DESCRIPTION.md` file explaining:
  - The purpose of the folder
  - What types of files belong there
  - How the files in the folder relate to the overall system
  - Any naming conventions specific to that folder

### Code Documentation
- Use docstrings for all modules, classes, and functions
- Include parameter descriptions, return values, and exceptions raised
- Document complex algorithms with explanations of the approach
- Add inline comments for non-obvious code sections

### System Documentation
- Maintain a comprehensive README.md at the project root
- Include setup instructions, dependencies, and usage examples
- Document the system architecture and component interactions
- Provide troubleshooting guides for common issues

## Maintenance Guidelines
- Update documentation whenever code functionality changes
- Review documentation for accuracy during code reviews
- Keep the todo.txt file updated with current tasks and progress
- Document API endpoints with expected inputs and outputs

## Example Docstring Format
```python
def get_measurements():
    """
    Retrieve current sensor measurements.
    
    Returns:
        tuple: A tuple containing (co2_ppm, temperature_celsius, humidity_percent)
              or None if measurements could not be obtained
    
    Raises:
        SensorConnectionError: If the sensor cannot be reached
        CalibrationError: If the sensor is not properly calibrated
    """
```
EOL

# Create folderdescription.mdc
cat > .cursor/rules/folderdescription.mdc << 'EOL'
# Folder Description Guidelines

This rule ensures consistent documentation of the project's folder structure.

## Naming Convention
- Name all folder description files as `1FOLDER_DESCRIPTION.md` so they appear first when sorted alphabetically
- Use Markdown format for all folder description files

## Required Content
Each folder description file must include:

1. **Title**: The name of the folder with a brief description
2. **Purpose**: What the folder is used for in the project
3. **File Types**: What types of files should be stored in this folder
4. **Naming Conventions**: Any specific naming patterns for files in this folder
5. **Usage Examples**: How to properly use or interact with files in this folder

## Template
```markdown
# [Folder Name] Directory

This directory contains [brief description of contents and purpose].

## File Types

- `*.py`: [Description of Python files in this folder]
- `*.json`: [Description of JSON files in this folder]
- [Other file types as needed]

## Naming Conventions

Files in this directory follow these naming conventions:
- `[pattern]_*.py`: [Description of what these files do]
- [Other naming patterns as needed]

## Usage Examples

### [Example Name]
```python
# Example code showing how to use files from this directory
```

## Important Notes

- [Any special considerations or warnings]
- [Common pitfalls to avoid]
```

## Implementation
- Create a folder description file in every directory, even if it seems obvious
- Update folder descriptions when adding new file types or changing conventions
- Reference the folder description in code comments when appropriate
EOL

# Create tapoplugs.mdc
cat > .cursor/rules/tapoplugs.mdc << 'EOL'
# Tapo Smart Plug Integration Guidelines

This rule ensures consistent and reliable integration with TP-Link Tapo smart plugs throughout the Shroombox project.

## Device Identification
- Support finding Tapo plugs by name, not just by IP address
- Maintain a mapping of device names to IP addresses in the settings
- Implement automatic device discovery on the local network
- Handle IP address changes gracefully with periodic rediscovery

## Device Control
- Implement proper error handling for all device operations
- Add retry logic for failed operations with exponential backoff
- Cache device states to reduce unnecessary network requests
- Implement graceful degradation when devices are unreachable

## Configuration
- Allow assigning roles to devices (heater, humidifier, etc.)
- Support custom naming of devices in the user interface
- Provide clear status indicators for device connectivity
- Allow manual override of automatic device control

## Security
- Store device credentials securely
- Implement proper authentication for device control
- Validate all inputs before sending to devices
- Log all device control operations for auditing

## Example Implementation
```python
class TapoDeviceManager:
    def find_device_by_name(self, name):
        """
        Find a Tapo device by its friendly name.
        
        Args:
            name (str): The friendly name of the device
            
        Returns:
            dict: Device information including IP, MAC, etc.
            None: If no device with that name is found
        """
        # Implementation details
        
    def control_device(self, identifier, state, retries=3):
        """
        Control a Tapo device by name or IP address.
        
        Args:
            identifier (str): Device name or IP address
            state (bool): True to turn on, False to turn off
            retries (int): Number of retry attempts if control fails
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            DeviceNotFoundError: If the device cannot be found
            ConnectionError: If connection to the device fails
        """
        # Implementation details
```
EOL

# Create todos.mdc
cat > .cursor/rules/todos.mdc << 'EOL'
# Todo List Management Guidelines

This rule ensures proper tracking and management of tasks in the Shroombox project.

## Todo File Location and Format
- Maintain a single `todo.txt` file at the project root
- Use consistent formatting with clear sections
- Mark completed tasks with [✓] and pending tasks with [ ]
- Group tasks by priority or component

## Task Management
- Keep the todo list updated as tasks are completed or new ones are identified
- Only work on tasks that have been explicitly agreed upon
- Add new tasks to the appropriate section when identified
- Include enough detail in task descriptions to understand the requirements

## Task Prioritization
- Current tasks: Actively being worked on or next in line
- Backlog: Tasks for future consideration
- Completed tasks: Keep a record of finished work
- Notes: Additional information relevant to the project

## Example Todo Format
```
SHROOMBOX PROJECT TODO LIST
=======================

CURRENT TASKS:
-------------
[ ] Implement feature X
    - Subtask 1
    - Subtask 2

COMPLETED TASKS:
--------------
[✓] Fixed bug Y
[✓] Implemented feature Z

BACKLOG:
-------
[ ] Future enhancement A
[ ] Future enhancement B

NOTES:
-----
- Important information about the project
- Technical limitations to be aware of
```

## Implementation Rules
- Review the todo list at the beginning of each work session
- Only perform tasks from the list when explicitly agreed upon
- Update the todo list after completing tasks
- Add detailed notes for complex tasks to aid implementation
EOL

# Create turnoffservices.mdc
cat > .cursor/rules/turnoffservices.mdc << 'EOL'
# Service Management Guidelines

This rule ensures proper configuration and management of system services in the Shroombox project.

## Service Configuration
- Configure all services to restart only on failure (`Restart=on-failure`)
- Set appropriate restart delays to prevent rapid cycling (`RestartSec=10s`)
- Use descriptive service names with the `shroombox-` prefix
- Include clear descriptions in service files
- Set proper dependencies between services

## Service Implementation
- Create separate service files for each component
- Use environment files for configuration when appropriate
- Implement proper logging for all services
- Add status reporting capabilities

## Service Management
- Restart affected services after code changes to verify functionality
- Use systemd for service management (start, stop, enable, disable)
- Monitor service status and logs for issues
- Implement graceful shutdown procedures

## Example Service File
```ini
[Unit]
Description=Shroombox Measurement Service
After=network.target

[Service]
Type=simple
User=shroombox
WorkingDirectory=/home/shroombox/shroombox3
ExecStart=/home/shroombox/shroombox3/scripts/run_measurements.sh
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

## Service Deployment
- Use the `install_services.sh` script to deploy services
- Verify service status after installation
- Test service recovery after failure
- Document service dependencies and startup order

## Service Monitoring
- Check service status before and after making changes
- Monitor service logs for errors or warnings
- Implement health checks for critical services
- Set up notifications for service failures
EOL

# Create virtualenvs.mdc
cat > .cursor/rules/virtualenvs.mdc << 'EOL'
# Virtual Environment Guidelines

This rule ensures proper use of Python virtual environments in the Shroombox project.

## Virtual Environment Setup
- Use a dedicated virtual environment for all development and testing
- Create the virtual environment in the project root as `venv/`
- Include the virtual environment directory in `.gitignore`
- Document all dependencies in `requirements.txt`

## Virtual Environment Usage
- Always activate the virtual environment before running scripts or tests
- Use the virtual environment for all package installations
- Keep the virtual environment synchronized with `requirements.txt`
- Use the correct Python interpreter from the virtual environment

## Activation Commands
### Linux/macOS
```bash
source venv/bin/activate
```

### Windows
```bash
venv\Scripts\activate
```

## Package Management
- Install packages with `pip install -r requirements.txt`
- Add new dependencies to `requirements.txt` with versions
- Use `pip freeze > requirements.txt` to update dependency list
- Consider using `pip-tools` for more advanced dependency management

## Testing with Virtual Environments
- Always run tests within the virtual environment
- Verify the correct Python interpreter is being used
- Use the virtual environment in CI/CD pipelines
- Test with fresh virtual environments periodically

## Example Usage in Scripts
```bash
#!/bin/bash
# Activate virtual environment
source "$(dirname "$0")/../venv/bin/activate"

# Run Python script with the virtual environment's Python
python my_script.py

# Deactivate when done
deactivate
```
EOL

echo "All rule files have been updated successfully!" 