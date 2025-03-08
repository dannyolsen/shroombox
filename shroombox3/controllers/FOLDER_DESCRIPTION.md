# Controllers

This directory contains controller classes for various subsystems of the Shroombox project. Controllers are responsible for implementing control logic for specific hardware components or environmental parameters.

## Files

- `__init__.py`: Package initialization file that exports controller classes
- `fan_controller.py`: Controller for fan speed based on CO2 levels using PID control

## Controllers

### FanController

The `FanController` class in `fan_controller.py` implements PID control for the fan based on CO2 readings. It handles:

- Initialization of PID controller with parameters from settings
- CO2 control logic using PID algorithm
- Synchronization of fan speed with settings.json
- Updating PID parameters and setpoints

The controller uses a negative PID control loop (higher CO2 → higher fan speed) to maintain CO2 levels at the desired setpoint by controlling the exhaust fan.

## Usage

Controllers are typically instantiated by the main `EnvironmentController` class and used to delegate specific control tasks. For example:

```python
# Create a fan controller
fan_controller = FanController(
    fan=fan_instance,
    settings_manager=settings_manager_instance,
    set_fan_speed_callback=device_manager.set_fan_speed
)

# Initialize from settings
await fan_controller.initialize_from_settings(settings)

# Update CO2 control
fan_controller.update_co2_control(co2_value)
```

This modular approach allows for better separation of concerns and more maintainable code. 