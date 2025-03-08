#!/usr/bin/env python3
"""
InfluxDB Data Migration Utility

This script migrates data from the old event-based structure to the new
device-centered structure defined in influx_structure.json.
"""

import os
import sys
import logging
import argparse
from datetime import datetime, timedelta

# Add project root to path for imports
script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if script_dir not in sys.path:
    sys.path.append(script_dir)

from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from utils.influx_schema_validator import influx_schema_validator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("influx_migration")

def get_influxdb_client():
    """Get a client connection to InfluxDB."""
    token = os.getenv('INFLUXDB_TOKEN')
    url = os.getenv('INFLUXDB_URL', 'http://localhost:8086')
    org = os.getenv('INFLUXDB_ORG')
    
    if not all([token, url, org]):
        logger.error("Missing InfluxDB configuration. Set INFLUXDB_TOKEN, INFLUXDB_URL, and INFLUXDB_ORG environment variables.")
        sys.exit(1)
    
    return InfluxDBClient(url=url, token=token, org=org)

def migrate_data(start_time=None, end_time=None, dry_run=False):
    """
    Migrate data from old structure to new device-centered structure.
    
    Args:
        start_time: Optional start time for migration (datetime)
        end_time: Optional end time for migration (datetime)
        dry_run: If True, only show what would be done without making changes
    """
    client = get_influxdb_client()
    bucket = os.getenv('INFLUXDB_BUCKET')
    
    if not bucket:
        logger.error("INFLUXDB_BUCKET environment variable not set")
        return
    
    query_api = client.query_api()
    
    # Only proceed with writes if not a dry run
    write_api = None if dry_run else client.write_api(write_options=SYNCHRONOUS)
    
    # Define time range
    time_filter = ""
    if start_time:
        time_filter += f' |> range(start: {start_time.isoformat()}Z'
        if end_time:
            time_filter += f', stop: {end_time.isoformat()}Z)'
        else:
            time_filter += ')'
    elif end_time:
        time_filter += f' |> range(stop: {end_time.isoformat()}Z)'
    else:
        # Default to all data
        time_filter = ' |> range(start: 0)'
    
    # 1. Migrate environment data
    logger.info("Migrating shroombox_environment to environment measurement...")
    query = f'''
        from(bucket: "{bucket}")
        {time_filter}
        |> filter(fn: (r) => r["_measurement"] == "shroombox_environment")
    '''
    
    try:
        result = query_api.query(query)
        
        environment_points = []
        fan_points = []
        heater_points = []
        humidifier_points = []
        
        for table in result:
            for record in table.records:
                time = record.get_time()
                field = record.get_field()
                value = record.get_value()
                tags = {key: record.values.get(key) for key in record.values if key not in ['_time', '_value', '_field', '_measurement']}
                
                # Always include location tag
                tags['location'] = tags.get('location', 'shroombox')
                
                # Migrate data based on field name
                if field in ['temperature', 'humidity', 'co2']:
                    # These go to the environment measurement
                    point = {
                        'measurement': 'environment',
                        'tags': tags,
                        'fields': {field: value},
                        'time': time
                    }
                    environment_points.append(point)
                
                elif field == 'fan_speed':
                    # This goes to the fan measurement
                    tags['event_type'] = 'measurement'
                    point = {
                        'measurement': 'fan',
                        'tags': tags,
                        'fields': {'speed': value},
                        'time': time
                    }
                    fan_points.append(point)
                
                elif field == 'heater':
                    # This goes to the heater measurement
                    tags['event_type'] = 'state_poll'
                    point = {
                        'measurement': 'heater',
                        'tags': tags,
                        'fields': {'state': value},
                        'time': time
                    }
                    heater_points.append(point)
                
                elif field == 'humidifier':
                    # This goes to the humidifier measurement
                    tags['event_type'] = 'state_poll'
                    point = {
                        'measurement': 'humidifier',
                        'tags': tags,
                        'fields': {'state': value},
                        'time': time
                    }
                    humidifier_points.append(point)
        
        # Write points if not a dry run
        if not dry_run and write_api:
            if environment_points:
                write_api.write(bucket=bucket, record=environment_points)
                logger.info(f"Migrated {len(environment_points)} environment data points")
            
            if fan_points:
                write_api.write(bucket=bucket, record=fan_points)
                logger.info(f"Migrated {len(fan_points)} fan data points")
            
            if heater_points:
                write_api.write(bucket=bucket, record=heater_points)
                logger.info(f"Migrated {len(heater_points)} heater data points")
            
            if humidifier_points:
                write_api.write(bucket=bucket, record=humidifier_points)
                logger.info(f"Migrated {len(humidifier_points)} humidifier data points")
        else:
            logger.info(f"DRY RUN: Would migrate {len(environment_points)} environment, {len(fan_points)} fan, {len(heater_points)} heater, and {len(humidifier_points)} humidifier data points")
    
    except Exception as e:
        logger.error(f"Error migrating environment data: {e}")
    
    # 2. Migrate humidifier_state data
    logger.info("Migrating humidifier_state to humidifier measurement...")
    query = f'''
        from(bucket: "{bucket}")
        {time_filter}
        |> filter(fn: (r) => r["_measurement"] == "humidifier_state")
    '''
    
    try:
        result = query_api.query(query)
        
        humidifier_points = []
        
        for table in result:
            for record in table.records:
                time = record.get_time()
                field = record.get_field()
                value = record.get_value()
                tags = {key: record.values.get(key) for key in record.values if key not in ['_time', '_value', '_field', '_measurement']}
                
                # Always include location tag
                tags['location'] = tags.get('location', 'shroombox')
                # Add event_type tag for state changes
                tags['event_type'] = 'state_change'
                
                # For any record, collect all fields from the same timestamp to create a single point
                point_key = (time, frozenset(tags.items()))
                
                # Find existing point or create new one
                existing_point = next((p for p in humidifier_points if (p['time'], frozenset(p['tags'].items())) == point_key), None)
                
                if existing_point:
                    # Add this field to existing point
                    existing_point['fields'][field] = value
                else:
                    # Create a new point
                    humidifier_points.append({
                        'measurement': 'humidifier',
                        'tags': tags,
                        'fields': {field: value},
                        'time': time
                    })
        
        # Write points if not a dry run
        if not dry_run and write_api and humidifier_points:
            write_api.write(bucket=bucket, record=humidifier_points)
            logger.info(f"Migrated {len(humidifier_points)} humidifier state data points")
        else:
            logger.info(f"DRY RUN: Would migrate {len(humidifier_points)} humidifier state data points")
    
    except Exception as e:
        logger.error(f"Error migrating humidifier state data: {e}")
    
    # 3. Migrate heater_state data
    logger.info("Migrating heater_state to heater measurement...")
    query = f'''
        from(bucket: "{bucket}")
        {time_filter}
        |> filter(fn: (r) => r["_measurement"] == "heater_state")
    '''
    
    try:
        result = query_api.query(query)
        
        heater_points = []
        
        for table in result:
            for record in table.records:
                time = record.get_time()
                field = record.get_field()
                value = record.get_value()
                tags = {key: record.values.get(key) for key in record.values if key not in ['_time', '_value', '_field', '_measurement']}
                
                # Always include location tag
                tags['location'] = tags.get('location', 'shroombox')
                # Add event_type tag for state changes
                tags['event_type'] = 'state_change'
                
                # For any record, collect all fields from the same timestamp to create a single point
                point_key = (time, frozenset(tags.items()))
                
                # Find existing point or create new one
                existing_point = next((p for p in heater_points if (p['time'], frozenset(p['tags'].items())) == point_key), None)
                
                if existing_point:
                    # Add this field to existing point
                    existing_point['fields'][field] = value
                else:
                    # Create a new point
                    heater_points.append({
                        'measurement': 'heater',
                        'tags': tags,
                        'fields': {field: value},
                        'time': time
                    })
        
        # Write points if not a dry run
        if not dry_run and write_api and heater_points:
            write_api.write(bucket=bucket, record=heater_points)
            logger.info(f"Migrated {len(heater_points)} heater state data points")
        else:
            logger.info(f"DRY RUN: Would migrate {len(heater_points)} heater state data points")
    
    except Exception as e:
        logger.error(f"Error migrating heater state data: {e}")
    
    # 4. Migrate pid_metrics data
    logger.info("Migrating pid_metrics to device measurements...")
    query = f'''
        from(bucket: "{bucket}")
        {time_filter}
        |> filter(fn: (r) => r["_measurement"] == "pid_metrics")
    '''
    
    try:
        result = query_api.query(query)
        
        humidity_pid_points = []
        temperature_pid_points = []
        co2_pid_points = []
        fan_pid_points = []
        
        for table in result:
            for record in table.records:
                time = record.get_time()
                field = record.get_field()
                value = record.get_value()
                tags = {key: record.values.get(key) for key in record.values if key not in ['_time', '_value', '_field', '_measurement']}
                
                # Always include location tag
                tags['location'] = tags.get('location', 'shroombox')
                # Add event_type tag for PID updates
                tags['event_type'] = 'pid_update'
                
                controller = tags.get('controller', '')
                
                # For any record, collect all fields from the same timestamp to create a single point
                point_key = (time, frozenset(tags.items()))
                
                # Determine which list to use based on controller type
                if controller == 'humidity':
                    points_list = humidity_pid_points
                    measurement = 'humidifier'
                elif controller == 'temperature':
                    points_list = temperature_pid_points
                    measurement = 'heater'
                elif controller == 'co2':
                    points_list = co2_pid_points
                    measurement = 'co2'
                elif controller == 'fan':
                    points_list = fan_pid_points
                    measurement = 'fan'
                else:
                    # Skip unknown controllers
                    continue
                
                # Find existing point or create new one
                existing_point = next((p for p in points_list if (p['time'], frozenset(p['tags'].items())) == point_key), None)
                
                if existing_point:
                    # Add this field to existing point
                    existing_point['fields'][field] = value
                else:
                    # Create a new point
                    points_list.append({
                        'measurement': measurement,
                        'tags': tags,
                        'fields': {field: value},
                        'time': time
                    })
        
        # Write points if not a dry run
        if not dry_run and write_api:
            if humidity_pid_points:
                write_api.write(bucket=bucket, record=humidity_pid_points)
                logger.info(f"Migrated {len(humidity_pid_points)} humidity PID metrics data points")
            
            if temperature_pid_points:
                write_api.write(bucket=bucket, record=temperature_pid_points)
                logger.info(f"Migrated {len(temperature_pid_points)} temperature PID metrics data points")
            
            if co2_pid_points:
                write_api.write(bucket=bucket, record=co2_pid_points)
                logger.info(f"Migrated {len(co2_pid_points)} CO2 PID metrics data points")
            
            if fan_pid_points:
                write_api.write(bucket=bucket, record=fan_pid_points)
                logger.info(f"Migrated {len(fan_pid_points)} fan PID metrics data points")
        else:
            logger.info(f"DRY RUN: Would migrate {len(humidity_pid_points)} humidity, {len(temperature_pid_points)} temperature, {len(co2_pid_points)} CO2, and {len(fan_pid_points)} fan PID metrics data points")
    
    except Exception as e:
        logger.error(f"Error migrating PID metrics data: {e}")
    
    # 5. Migrate burst_cycle data
    logger.info("Migrating burst_cycle to humidifier measurement...")
    query = f'''
        from(bucket: "{bucket}")
        {time_filter}
        |> filter(fn: (r) => r["_measurement"] == "burst_cycle")
    '''
    
    try:
        result = query_api.query(query)
        
        burst_cycle_points = []
        
        for table in result:
            for record in table.records:
                time = record.get_time()
                field = record.get_field()
                value = record.get_value()
                tags = {key: record.values.get(key) for key in record.values if key not in ['_time', '_value', '_field', '_measurement']}
                
                # Always include location tag
                tags['location'] = tags.get('location', 'shroombox')
                # Add event_type tag for burst cycles
                tags['event_type'] = 'burst_cycle'
                
                # For any record, collect all fields from the same timestamp to create a single point
                point_key = (time, frozenset(tags.items()))
                
                # Find existing point or create new one
                existing_point = next((p for p in burst_cycle_points if (p['time'], frozenset(p['tags'].items())) == point_key), None)
                
                if existing_point:
                    # Add this field to existing point
                    existing_point['fields'][field] = value
                else:
                    # Create a new point
                    burst_cycle_points.append({
                        'measurement': 'humidifier',
                        'tags': tags,
                        'fields': {field: value},
                        'time': time
                    })
        
        # Write points if not a dry run
        if not dry_run and write_api and burst_cycle_points:
            write_api.write(bucket=bucket, record=burst_cycle_points)
            logger.info(f"Migrated {len(burst_cycle_points)} burst cycle data points")
        else:
            logger.info(f"DRY RUN: Would migrate {len(burst_cycle_points)} burst cycle data points")
    
    except Exception as e:
        logger.error(f"Error migrating burst cycle data: {e}")
    
    if write_api:
        write_api.close()
    client.close()
    
    logger.info("Migration complete!")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Migrate InfluxDB data to the new device-centered structure')
    parser.add_argument('--start', help='Start time for migration (ISO format, e.g. 2023-04-01T00:00:00)')
    parser.add_argument('--end', help='End time for migration (ISO format, e.g. 2023-04-30T23:59:59)')
    parser.add_argument('--days', type=int, help='Number of days to migrate from now (alternative to start/end)')
    parser.add_argument('--dry-run', action='store_true', help='Only show what would be done without making changes')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    start_time = None
    end_time = None
    
    if args.days:
        start_time = datetime.utcnow() - timedelta(days=args.days)
    elif args.start:
        start_time = datetime.fromisoformat(args.start.replace('Z', '+00:00'))
    
    if args.end:
        end_time = datetime.fromisoformat(args.end.replace('Z', '+00:00'))
    
    logger.info(f"Starting migration from {start_time} to {end_time}" + (" (DRY RUN)" if args.dry_run else ""))
    migrate_data(start_time=start_time, end_time=end_time, dry_run=args.dry_run) 