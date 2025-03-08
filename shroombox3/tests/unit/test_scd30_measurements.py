#!/usr/bin/env python3
"""
Test script for SCD30 CO2 sensor measurements.
This script tests if the SimpleSCD30Controller is working correctly by reading
measurements from the sensor and displaying them.
"""

import os
import sys
import asyncio
import argparse
import logging
import json
from datetime import datetime

# Add parent directory to Python path so we can import from root
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))  # Go up two levels
sys.path.insert(0, parent_dir)

# Import the test_sensor function from simple_sensor.py
from devices.simple_sensor import test_sensor, SimpleSCD30Controller

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('test_scd30_measurements')

# Suppress specific warning messages
original_warning = logging.Logger.warning
def filtered_warning(self, msg, *args, **kwargs):
    if "Failed to stop periodic measurement" not in str(msg):
        original_warning(self, msg, *args, **kwargs)
logging.Logger.warning = filtered_warning

def get_settings_measurement_interval():
    """Get the measurement interval from settings.json."""
    try:
        settings_path = os.path.join(parent_dir, 'config', 'settings.json')
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                settings = json.load(f)
                if 'sensor' in settings and 'measurement_interval' in settings['sensor']:
                    interval = settings['sensor']['measurement_interval']
                    logger.info(f"Found measurement interval in settings.json: {interval}s")
                    return interval
    except Exception as e:
        logger.warning(f"Error reading settings.json: {e}")
    
    # Default to 2 seconds if settings.json doesn't exist or doesn't contain the interval
    logger.info("Using default measurement interval: 2s")
    return 2

def parse_arguments():
    """Parse command line arguments."""
    # Get the default interval from settings.json
    default_interval = get_settings_measurement_interval()
    
    parser = argparse.ArgumentParser(description='Test SCD30 CO2 sensor measurements')
    parser.add_argument('--interval', type=int, default=default_interval, 
                        help=f'Measurement interval in seconds (minimum 2, default from settings.json: {default_interval})')
    parser.add_argument('--count', type=int, default=0, 
                        help='Number of measurements to take (0 for continuous)')
    parser.add_argument('--json', action='store_true', 
                        help='Output in JSON format')
    parser.add_argument('--output', type=str, 
                        help='Save measurements to a file')
    parser.add_argument('--verbose', '-v', action='store_true', 
                        help='Enable verbose output')
    return parser.parse_args()

async def save_measurements_to_file(file_path, measurements, json_format=False):
    """Save measurements to a file."""
    try:
        co2, temp, rh = measurements
        timestamp = datetime.now().isoformat()
        
        if json_format:
            data = {
                'co2': round(co2, 1),
                'temperature': round(temp, 1),
                'humidity': round(rh, 1),
                'timestamp': timestamp
            }
            with open(file_path, 'a') as f:
                f.write(json.dumps(data) + '\n')
        else:
            with open(file_path, 'a') as f:
                f.write(f"{timestamp}, {co2:.1f}, {temp:.1f}, {rh:.1f}\n")
                
        logger.debug(f"Saved measurement to {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving measurement to file: {e}")
        return False

async def test_scd30_with_file_output(interval, count, json_output, output_file, verbose):
    """Test the SCD30 sensor and optionally save measurements to a file."""
    # Create sensor instance
    sensor = None
    try:
        sensor = SimpleSCD30Controller()
        
        # Set measurement interval
        sensor.set_measurement_interval(interval)
        
        print(f"Reading measurements from {sensor.name} (interval: {interval}s)")
        print("Press Ctrl+C to stop")
        
        # Initialize output file if specified
        if output_file:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            
            # Write header to file
            if not json_output:
                with open(output_file, 'w') as f:
                    f.write("timestamp, co2, temperature, humidity\n")
            else:
                # Ensure the file exists but is empty
                open(output_file, 'w').close()
        
        count_taken = 0
        while count == 0 or count_taken < count:
            try:
                # Get measurements
                measurements = await sensor.get_measurements()
                
                if measurements:
                    co2, temp, rh = measurements
                    
                    # Output in requested format
                    if json_output:
                        data = {
                            'co2': round(co2, 1),
                            'temperature': round(temp, 1),
                            'humidity': round(rh, 1),
                            'timestamp': datetime.now().isoformat()
                        }
                        print(json.dumps(data))
                    else:
                        print(f"CO2: {co2:.1f} ppm, Temperature: {temp:.1f}°C, Humidity: {rh:.1f}%")
                    
                    # Save to file if specified
                    if output_file:
                        await save_measurements_to_file(output_file, measurements, json_output)
                    
                    count_taken += 1
                else:
                    print("Failed to get measurements")
                
                # Wait for next measurement
                if count == 0 or count_taken < count:
                    await asyncio.sleep(interval)
            except asyncio.CancelledError:
                # This is raised when the task is cancelled (e.g., by KeyboardInterrupt)
                break
    except KeyboardInterrupt:
        print("\nStopped by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Clean up
        if sensor:
            try:
                sensor.cleanup()
                print("Sensor cleaned up")
            except Exception as e:
                print(f"Error during cleanup: {e}")

def run_with_graceful_shutdown(coro):
    """Run a coroutine with graceful shutdown handling."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Create a task for the coroutine
    main_task = loop.create_task(coro)
    
    try:
        # Run the task until it's complete
        loop.run_until_complete(main_task)
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        print("\nShutting down gracefully...")
        
        # Cancel the main task
        main_task.cancel()
        
        # Run the event loop until the task is cancelled
        try:
            loop.run_until_complete(main_task)
        except asyncio.CancelledError:
            pass
    finally:
        # Close the event loop
        loop.close()

def main():
    """Main function."""
    args = parse_arguments()
    
    # Set logging level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger('shroombox.simple_sensor').setLevel(logging.DEBUG)
    
    # If output file is specified, use the extended test function
    if args.output:
        run_with_graceful_shutdown(
            test_scd30_with_file_output(
                interval=args.interval,
                count=args.count,
                json_output=args.json,
                output_file=args.output,
                verbose=args.verbose
            )
        )
    else:
        # Otherwise, use the existing test_sensor function
        run_with_graceful_shutdown(
            test_sensor(
                interval=args.interval,
                count=args.count,
                json_output=args.json
            )
        )

if __name__ == "__main__":
    main() 