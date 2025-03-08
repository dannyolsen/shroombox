#!/usr/bin/env python3
"""
InfluxDB Schema Update Utility

This script synchronizes and prettifies the influx_structure.json file after
new fields or measurements have been added to the schema.
"""

import os
import json
import logging
import sys
from typing import Dict, Any

# Add project root to path for imports
script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if script_dir not in sys.path:
    sys.path.append(script_dir)

from utils.influx_schema_validator import influx_schema_validator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("schema_update")

def prettify_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Organize and prettify the schema structure.
    
    Args:
        schema: The schema dictionary to prettify
        
    Returns:
        Dict[str, Any]: The prettified schema
    """
    # Ensure required sections exist
    if "measurements" not in schema:
        schema["measurements"] = {}
        
    # Sort measurements alphabetically
    measurements = schema["measurements"]
    sorted_measurements = {}
    
    # First sort and process the core measurements
    for name in sorted(measurements.keys()):
        measurement = measurements[name]
        
        # Sort fields
        if "fields" in measurement:
            measurement["fields"] = {k: measurement["fields"][k] for k in sorted(measurement["fields"].keys())}
            
        # Sort tags
        if "tags" in measurement:
            measurement["tags"] = {k: measurement["tags"][k] for k in sorted(measurement["tags"].keys())}
            
        # Add to sorted measurements
        sorted_measurements[name] = measurement
    
    # Replace measurements with sorted version
    schema["measurements"] = sorted_measurements
    
    # Sort top-level keys
    schema = {k: schema[k] for k in sorted(schema.keys())}
    
    return schema

def update_schema_file():
    """Update and prettify the schema file."""
    # Force the schema validator to load the current schema
    schema = influx_schema_validator._schema
    
    # Prettify the schema
    schema = prettify_schema(schema)
    
    # Save the prettified schema
    schema_path = influx_schema_validator._schema_path
    
    # Create backup
    backup_path = f"{schema_path}.bak"
    try:
        with open(schema_path, 'r') as src, open(backup_path, 'w') as dst:
            dst.write(src.read())
    except Exception as e:
        logger.warning(f"Failed to create schema backup: {e}")
    
    # Write prettified schema
    with open(schema_path, 'w') as f:
        json.dump(schema, f, indent=2)
    
    logger.info(f"Schema file updated and prettified: {schema_path}")
    logger.info(f"Contains {len(schema['measurements'])} measurements")
    
    # Log the measurements
    for name, measurement in schema["measurements"].items():
        field_count = len(measurement.get("fields", {}))
        tag_count = len(measurement.get("tags", {}))
        logger.info(f"  - {name}: {field_count} fields, {tag_count} tags")

if __name__ == "__main__":
    logger.info("Updating InfluxDB schema file...")
    update_schema_file()
    logger.info("Done!") 