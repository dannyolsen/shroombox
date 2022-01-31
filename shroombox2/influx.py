from influxdb_client import InfluxDBClient, Point

username = 'grafana'
password = 'dao4572201026'

database = 'db_shroombox2'
retention_policy = 'autogen'

bucket = f'{database}/{retention_policy}'

client = InfluxDBClient(url='http://localhost:8086', token=f'{username}:{password}', org='-')

def write_ver18(measurement,tag,field):
    #example: measurement="mem",tag=["host", "host1"],field=["used_percent", 25.43234543]
    
    with client.write_api() as write_api:
            #print('*** Write Points ***')
            point = Point(measurement).tag(tag[0], tag[1]).field(field[0],field[1])
            #print(point.to_line_protocol())
            write_api.write(bucket=bucket, record=point)

def write_points_ver18(string_of_points):
    #example: measurement="mem",tag=["host", "host1"],field=["used_percent", 25.43234543]
    
    with client.write_api() as write_api:
            #print('*** Write Points ***')
            #point = point_array
            #print(point.to_line_protocol())
            write_api.write(bucket=bucket, record=string_of_points)
