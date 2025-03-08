#!/usr/bin/env python3
import json
import sys
import os
import asyncio
import logging
from settings_manager import SettingsManager

async def update_setpoint(phase, setpoint_type, value):
    """Update a setpoint in the settings.json file using SettingsManager."""
    try:
        # Initialize settings manager
        settings_manager = SettingsManager()
        
        # Map frontend field names to backend field names
        field_mapping = {
            'temperature': 'temp_setpoint',
            'humidity': 'rh_setpoint',
            'co2': 'co2_setpoint'
        }
        
        # Get the correct field name
        field_name = field_mapping.get(setpoint_type)
        if not field_name:
            print(f"Error: Unknown setpoint type: {setpoint_type}")
            return False
        
        # Load current settings
        settings = await settings_manager.load_settings(force_reload=True)
        
        # Ensure the phase exists
        if phase not in settings['environment']['phases']:
            print(f"Error: Unknown phase: {phase}")
            return False
        
        # Convert value to the right type
        if setpoint_type == 'co2':
            value = int(value)
        else:
            value = float(value)
        
        # Get old value for logging
        old_value = settings['environment']['phases'][phase][field_name]
        
        # Create update structure
        updates = {
            'environment': {
                'phases': {
                    phase: {
                        field_name: value
                    }
                }
            }
        }
        
        # Update settings using settings manager
        success = await settings_manager.update_settings(updates)
        
        if success:
            print(f"Updated {phase} {setpoint_type} setpoint from {old_value} to {value}")
            return True
        else:
            print(f"Failed to update {phase} {setpoint_type} setpoint")
            return False
    
    except Exception as e:
        print(f"Error updating setpoint: {e}")
        return False

def main():
    """Main function to parse arguments and update setpoint."""
    if len(sys.argv) != 4:
        print("Usage: python test_setpoints.py <phase> <setpoint_type> <value>")
        print("  phase: colonisation, growing, cake")
        print("  setpoint_type: temperature, humidity, co2")
        print("  value: numeric value")
        return
    
    phase = sys.argv[1]
    setpoint_type = sys.argv[2]
    value = sys.argv[3]
    
    # Run the async function
    asyncio.run(update_setpoint(phase, setpoint_type, value))

if __name__ == "__main__":
    main() 