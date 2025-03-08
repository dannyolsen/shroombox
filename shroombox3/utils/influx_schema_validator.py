"""
InfluxDB Schema Validator

Utilities for validating and automatically updating the InfluxDB schema structure.
"""

import os
import json
import logging
import threading
from typing import Dict, Any, List, Optional, Union, Set

# Set up logging
logger = logging.getLogger("shroombox.influx_schema")

class InfluxSchemaValidator:
    """
    Validates and manages the InfluxDB schema structure.
    
    This class ensures that all data logged to InfluxDB conforms to 
    the structure defined in influx_structure.json. It also 
    automatically updates the structure when new fields or measurements 
    are encountered.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(InfluxSchemaValidator, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        with self._lock:
            if self._initialized:
                return
                
            self._schema = {}
            self._schema_path = self._find_schema_path()
            self._load_schema()
            self._dirty = False
            self._initialized = True
            logger.info(f"InfluxDB schema validator initialized with schema from {self._schema_path}")
    
    def _find_schema_path(self) -> str:
        """Find the path to the influx_structure.json file."""
        # Try project root first (most likely location)
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        possible_paths = [
            os.path.join(script_dir, 'config', 'influx_structure.json'),
            os.path.join(script_dir, 'influx_structure.json'),
            os.path.join(os.path.dirname(script_dir), 'config', 'influx_structure.json')
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # If not found, default to the first location and create an empty structure
        default_path = possible_paths[0]
        os.makedirs(os.path.dirname(default_path), exist_ok=True)
        with open(default_path, 'w') as f:
            json.dump({"measurements": {}}, f, indent=2)
        
        return default_path
    
    def _load_schema(self) -> None:
        """Load the schema from the influx_structure.json file."""
        try:
            with open(self._schema_path, 'r') as f:
                self._schema = json.load(f)
                
            # Ensure basic structure exists
            if "measurements" not in self._schema:
                self._schema["measurements"] = {}
                self._dirty = True
                
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading schema: {e}. Creating new schema.")
            self._schema = {"measurements": {}}
            self._dirty = True
    
    def _save_schema(self) -> None:
        """Save the schema to the influx_structure.json file."""
        if not self._dirty:
            return
            
        try:
            # Create backup of current file
            if os.path.exists(self._schema_path):
                backup_path = f"{self._schema_path}.bak"
                try:
                    with open(self._schema_path, 'r') as src, open(backup_path, 'w') as dst:
                        dst.write(src.read())
                except Exception as e:
                    logger.warning(f"Failed to create schema backup: {e}")
            
            # Write updated schema
            with open(self._schema_path, 'w') as f:
                json.dump(self._schema, f, indent=2)
                
            self._dirty = False
            logger.info(f"Updated InfluxDB schema saved to {self._schema_path}")
        except Exception as e:
            logger.error(f"Error saving schema: {e}")
    
    def validate_point(self, measurement: str, fields: Dict[str, Any], 
                      tags: Dict[str, str]) -> Dict[str, Any]:
        """
        Validate a data point against the schema and update if needed.
        
        Args:
            measurement: The measurement name
            fields: Dictionary of fields and their values
            tags: Dictionary of tags and their values
            
        Returns:
            Dict[str, Any]: Validated fields dictionary
        """
        with self._lock:
            # Check if measurement exists in schema
            if measurement not in self._schema["measurements"]:
                logger.info(f"Adding new measurement to schema: {measurement}")
                self._schema["measurements"][measurement] = {
                    "description": f"Automatically added measurement for {measurement}",
                    "fields": {},
                    "tags": {},
                    "recommended_retention": "30d",
                    "typical_interval": "event-based"
                }
                self._dirty = True
            
            # Check and add fields
            schema_fields = self._schema["measurements"][measurement].get("fields", {})
            for field_name, field_value in fields.items():
                if field_name not in schema_fields:
                    logger.info(f"Adding new field to schema: {measurement}.{field_name}")
                    
                    # Determine field type and unit
                    field_type = self._determine_field_type(field_value)
                    unit = self._determine_unit(field_name, field_value)
                    
                    schema_fields[field_name] = {
                        "type": field_type,
                        "unit": unit,
                        "description": f"Automatically added field for {field_name}"
                    }
                    self._dirty = True
            
            # Ensure fields are in schema
            if "fields" not in self._schema["measurements"][measurement]:
                self._schema["measurements"][measurement]["fields"] = schema_fields
                self._dirty = True
            
            # Check and add tags
            schema_tags = self._schema["measurements"][measurement].get("tags", {})
            for tag_name, tag_value in tags.items():
                if tag_name not in schema_tags:
                    logger.info(f"Adding new tag to schema: {measurement}.{tag_name}")
                    
                    schema_tags[tag_name] = {
                        "description": f"Automatically added tag for {tag_name}",
                        "example": tag_value
                    }
                    self._dirty = True
            
            # Ensure tags are in schema
            if "tags" not in self._schema["measurements"][measurement]:
                self._schema["measurements"][measurement]["tags"] = schema_tags
                self._dirty = True
            
            # Save schema if changed
            if self._dirty:
                self._save_schema()
            
            return fields
    
    def _determine_field_type(self, value: Any) -> str:
        """Determine the field type based on the value."""
        if isinstance(value, bool):
            return "integer"  # InfluxDB uses 0/1 for booleans
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "float"
        elif isinstance(value, str):
            return "string"
        else:
            return "float"  # Default to float for most values in time series
    
    def _determine_unit(self, field_name: str, value: Any) -> str:
        """Determine the unit based on the field name and value."""
        # Common pattern matching
        if isinstance(value, bool) or (isinstance(value, (int, float)) and value in (0, 1)):
            if "state" in field_name.lower():
                return "boolean"
        
        # Temperature fields
        if any(temp in field_name.lower() for temp in ["temp", "temperature"]):
            return "°C"
        
        # Humidity fields
        if any(humid in field_name.lower() for humid in ["humidity", "rh"]):
            return "%"
        
        # CO2 fields
        if "co2" in field_name.lower():
            return "ppm"
        
        # Fan speed
        if "fan" in field_name.lower() and "speed" in field_name.lower():
            return "%"
        
        # Duration fields
        if any(dur in field_name.lower() for dur in ["duration", "time", "interval"]):
            return "seconds"
        
        # Progress fields
        if "progress" in field_name.lower():
            return "%"
        
        # PID fields
        if field_name in ["p_term", "i_term", "d_term", "pid_output", "error"]:
            return "varies"
        
        # Default
        return "varies"
    
    def get_all_measurements(self) -> List[str]:
        """Get a list of all measurements in the schema."""
        with self._lock:
            return list(self._schema.get("measurements", {}).keys())
    
    def get_measurement_fields(self, measurement: str) -> Dict[str, Dict[str, Any]]:
        """Get all fields for a specific measurement."""
        with self._lock:
            if measurement in self._schema.get("measurements", {}):
                return self._schema["measurements"][measurement].get("fields", {})
            return {}
    
    def get_measurement_tags(self, measurement: str) -> Dict[str, Dict[str, Any]]:
        """Get all tags for a specific measurement."""
        with self._lock:
            if measurement in self._schema.get("measurements", {}):
                return self._schema["measurements"][measurement].get("tags", {})
            return {}


# Create a global instance for easy access
influx_schema_validator = InfluxSchemaValidator() 