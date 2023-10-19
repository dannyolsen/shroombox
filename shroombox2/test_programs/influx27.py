import influxdb_client, os, time
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime

#export INFLUXDB_TOKEN=U2J_NlXaYRTs8w0F0BjBuEwCYVL2k3AD1o0fpN0FVMUE0MzO4fNgXWr11zCsED9JAP6y-bI6HCLw7InzGKu4Rg==

token = os.environ.get("INFLUXDB_TOKEN")
org = "dannyolsen"
url = "http://192.168.87.37:8086"

token = "Egmc4Bxyb3ywJHWw2i-YwkxQT1bp1m8NaJa9SXq9Vf78C9md3b36V8ajX5dSnyhflToMFvizP1mrJMp6tdCukw=="
write_client = influxdb_client.InfluxDBClient(url=url, token=token, org=org)

bucket="test"

write_api = write_client.write_api(write_options=SYNCHRONOUS)

timestamp = datetime.utcnow()
p = []
location = "Acidman"
cabinet = 1
rh  = 90
co2 = 750
temp = 22

p.append(Point("rh_percent").tag(	"location", location).tag("cabinet", cabinet).field("humidity", rh).time(		timestamp))
p.append(Point("co2_ppm").tag(		"location", location).tag("cabinet", cabinet).field("co2", co2).time(			timestamp))
p.append(Point("temp_degrees").tag(	"location", location).tag("cabinet", cabinet).field("temperature", temp).time(	timestamp))

write_api.write(bucket, org, record=p)

write_client.close()