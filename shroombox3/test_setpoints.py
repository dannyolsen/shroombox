#!/usr/bin/env python3
import json
import sys
import os

def update_setpoint(phase, setpoint_type, value):
    """Update a setpoint in the settings.json file."""
    try:
        # Load current settings
        with open('config/settings.json', 'r') as f:
            settings = json.load(f)
        
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
        
        # Ensure the phase exists
        if phase not in settings['environment']['phases']:
            print(f"Error: Unknown phase: {phase}")
            return False
        
        # Convert value to the right type
        if setpoint_type == 'co2':
            value = int(value)
        else:
            value = float(value)
        
        # Update the setpoint
        old_value = settings['environment']['phases'][phase][field_name]
        settings['environment']['phases'][phase][field_name] = value
        
        # Save the updated settings
        with open('config/settings.json', 'w') as f:
            json.dump(settings, f, indent=4)
        
        print(f"Updated {phase} {setpoint_type} setpoint from {old_value} to {value}")
        return True
    
    except Exception as e:
        print(f"Error updating setpoint: {e}")
        return False

def main():
    """Main function."""
    if len(sys.argv) != 4:
        print("Usage: python test_setpoints.py <phase> <setpoint_type> <value>")
        print("  phase: colonisation, growing, cake")
        print("  setpoint_type: temperature, humidity, co2")
        print("  value: numeric value")
        return
    
    phase = sys.argv[1]
    setpoint_type = sys.argv[2]
    value = sys.argv[3]
    
    update_setpoint(phase, setpoint_type, value)

if __name__ == "__main__":
    main() 