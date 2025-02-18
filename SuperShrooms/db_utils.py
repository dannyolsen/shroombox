from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime
from typing import Dict, Any, Optional

class InfluxDBWriter:
    def __init__(self, url: str, token: str, org: str, bucket: str):
        """Initialize InfluxDB client connection.
        
        Args:
            url: InfluxDB server URL
            token: Authentication token
            org: Organization name
            bucket: Bucket name to write to
        """
        self.client = InfluxDBClient(url=url, token=token, org=org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.bucket = bucket
        self.org = org

    def write_measurement(self, 
                         measurement: str, 
                         fields: Dict[str, Any], 
                         tags: Optional[Dict[str, str]] = None,
                         timestamp: Optional[datetime] = None) -> None:
        """Write a measurement to InfluxDB.
        
        Args:
            measurement: Name of the measurement
            fields: Dictionary of field names and values to write
            tags: Optional dictionary of tags to associate with the measurement
            timestamp: Optional timestamp for the measurement. If None, current time is used.
        """
        point = Point(measurement)
        
        # Add all fields
        for field_name, value in fields.items():
            point.field(field_name, value)
        
        # Add optional tags
        if tags:
            for tag_name, tag_value in tags.items():
                point.tag(tag_name, tag_value)
        
        # Add timestamp if provided
        if timestamp:
            point.time(timestamp)
            
        self.write_api.write(bucket=self.bucket, org=self.org, record=point)

    def close(self):
        """Close the InfluxDB client connection."""
        self.client.close()

# Usage example:
"""
# Initialize the writer
db_writer = InfluxDBWriter(
    url="http://localhost:8086",
    token="your-token",
    org="your-org",
    bucket="your-bucket"
)

# Write a measurement
db_writer.write_measurement(
    measurement="temperature",
    fields={"value": 25.6, "humidity": 65.4},
    tags={"location": "grow_room", "sensor": "dht22"}
)

# Don't forget to close the connection when done
db_writer.close()
"""
