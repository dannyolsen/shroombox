#!/usr/bin/env python3
"""
Test script for temperature control logic.
Tests various scenarios to verify the temperature controller behavior.
"""

import os
import sys
import time
import asyncio
import logging
from datetime import datetime

# Add parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Import our modules
from controllers.temperature_controller import TemperatureController
from managers.device_manager import DeviceManager

# Create logs directory if it doesn't exist
os.makedirs('logs/tests', exist_ok=True)

# Set up logging with timestamp in filename
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_file = f'logs/tests/temp_test_{timestamp}.log'

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler(log_file)  # Log to file with timestamp
    ]
)
logger = logging.getLogger("temp_test")
logger.info(f"Starting temperature control test, logging to: {log_file}")

# Also set temperature controller logger to DEBUG
temp_logger = logging.getLogger("shroombox.temperature")
temp_logger.setLevel(logging.DEBUG)
temp_logger.addHandler(logging.FileHandler(log_file))

# Set mock device manager logger to DEBUG
mock_logger = logging.getLogger("mock_device_manager")
mock_logger.setLevel(logging.DEBUG)
mock_logger.addHandler(logging.FileHandler(log_file))

# Prevent duplicate logging
for logger in [temp_logger, mock_logger]:
    logger.propagate = False

class MockDeviceManager:
    """Mock device manager for testing."""
    def __init__(self):
        self.device_states = {}
        self.logger = logging.getLogger("mock_device_manager")
        
    async def set_device_state(self, device_role: str, state: bool) -> bool:
        """Mock setting device state."""
        self.device_states[device_role] = state
        self.logger.info(f"Mock: Setting {device_role} to {'ON' if state else 'OFF'}")
        return True
        
    async def get_device_state(self, device_role: str) -> bool:
        """Mock getting device state."""
        return self.device_states.get(device_role, False)

class TestScenario:
    def __init__(self, name: str, temperatures: list, delays: list):
        self.name = name
        self.temperatures = temperatures
        self.delays = delays

async def run_test_scenario(controller: TemperatureController, scenario: TestScenario):
    """Run a test scenario through the temperature controller."""
    logger.info(f"\n=== Running Test Scenario: {scenario.name} ===")
    
    for temp, delay in zip(scenario.temperatures, scenario.delays):
        logger.info(f"\nTesting with temperature: {temp}°C")
        logger.info(f"Current controller state - Setpoint: {controller.temp_setpoint}°C, "
                   f"Hysteresis: {controller.temp_hysteresis}°C")
        
        # Apply temperature control
        await controller.control(temp)
        
        # Log the result
        logger.info(f"After control - Heater state: {'ON' if controller.get_state() else 'OFF'}")
        
        # Wait for specified delay
        if delay > 0:
            logger.info(f"Waiting {delay} seconds...")
            await asyncio.sleep(delay)

async def main():
    """Main test function."""
    try:
        # Initialize mock device manager and controller
        device_manager = MockDeviceManager()
        controller = TemperatureController(device_manager)
        
        # Reduce the minimum state change interval for testing
        controller.min_state_change_interval = 2.0  # 2 seconds for testing
        
        # Define test scenarios
        scenarios = [
            # Normal operation scenario
            TestScenario(
                name="Normal Operation",
                temperatures=[18.0, 19.0, 20.0, 21.0, 20.5, 19.5],
                delays=[3, 3, 3, 3, 3, 3]
            ),
            
            # Rapid temperature changes (should be debounced)
            TestScenario(
                name="Rapid Changes (Debouncing Test)",
                temperatures=[18.0, 21.0, 18.0, 21.0],
                delays=[1, 1, 1, 1]  # Short delays to test debouncing
            ),
            
            # Edge cases
            TestScenario(
                name="Edge Cases",
                temperatures=[-45.0, 95.0, 0.0, 50.0],
                delays=[3, 3, 3, 3]
            ),
            
            # Threshold testing
            TestScenario(
                name="Threshold Testing",
                temperatures=[
                    20.0,  # At setpoint
                    19.6,  # Just above turn-on threshold
                    19.4,  # Just below turn-on threshold
                    20.1,  # Just above turn-off threshold
                ],
                delays=[3, 3, 3, 3]
            )
        ]
        
        # Run each scenario
        for scenario in scenarios:
            await run_test_scenario(controller, scenario)
            logger.info("\nScenario completed.")
            await asyncio.sleep(2)  # Brief pause between scenarios
        
        logger.info("\n=== All test scenarios completed ===")
        
    except Exception as e:
        logger.error(f"Error during testing: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    # Run the test
    asyncio.run(main()) 