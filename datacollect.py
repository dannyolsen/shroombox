# Module Imports
import mariadb
import sys
from time import sleep, strftime, time
from datetime import datetime


data = []

# Connect to MariaDB Platform
try:
    conn = mariadb.connect(
        user="shroomie",
        password="shroomie",
        host="localhost",
        port=3306,
        database="db_shroomdata"

    )

except mariadb.Error as e:
    print(f"Error connecting to MariaDB Platform: {e}")
    sys.exit(1)

# Get Cursor
cur = conn.cursor()

def save_data(channel, value, unit):
    timestamp_utc = datetime.utcnow()
    timestamp_utc = timestamp_utc.strptime(str(timestamp_utc), "%Y-%m-%d %H:%M:%S.%f").strftime("%Y-%m-%d %H:%M:%S")
    timestamp = strftime("%Y-%m-%d %H:%M:%S")
    #print(timestamp)
 
    query = "INSERT INTO tbl_measurements(channel, value, unit, datetime) VALUES ('{}', {}, '{}','{}')".format(channel, value, unit, str(timestamp_utc))
    #print(query)

    cur.execute(query) 

    conn.commit()
    
    print("{} data saved in database".format(channel))
    
def save_scd_values(temp, rh, co2):
    timestamp_utc = datetime.utcnow()
    timestamp_utc = timestamp_utc.strptime(str(timestamp_utc), "%Y-%m-%d %H:%M:%S.%f").strftime("%Y-%m-%d %H:%M:%S")
    timestamp = strftime("%Y-%m-%d %H:%M:%S")

    query = "INSERT INTO tbl_measurements(channel, value, unit, datetime) VALUES ('temp', {temp}, '°C','{timestamp}'), ('rh', {rh}, '%','{timestamp}'), ('co2', {co2}, 'ppm','{timestamp}') ".format(temp=temp, rh=rh, co2=co2, timestamp=str(timestamp_utc))

    cur.execute(query) 

    conn.commit()
    print("save_scd_values(): temp, rh and co2 saved to database")


def save_setpoints(cakeTmpMax, cakeTmpMin, growTmpMax, growTmpMin, co2Max, co2Min, rhMax, rhMin):
    timestamp_utc = datetime.utcnow()
    timestamp_utc = timestamp_utc.strptime(str(timestamp_utc), "%Y-%m-%d %H:%M:%S.%f").strftime("%Y-%m-%d %H:%M:%S")
    #timestamp = strftime("%Y-%m-%d %H:%M:%S")

    query = "INSERT INTO tbl_measurements(channel, value, unit, datetime) VALUES ('cakeTmpMax', {ctmax}, '°C','{timestamp}'), ('cakeTmpMin', {ctmin}, '°C','{timestamp}'), ('growTmpMax', {gtmax}, '°C','{timestamp}'), ('growTmpMin', {gtmin}, '°C','{timestamp}'), ('co2Max', {co2max}, 'ppm','{timestamp}'), ('co2Min', {co2min}, 'ppm','{timestamp}'), ('rhMax', {rhmax}, '%','{timestamp}'), ('rhMin', {rhmin}, '%','{timestamp}')".format(ctmax=cakeTmpMax, ctmin=cakeTmpMin, gtmax=growTmpMax, gtmin=growTmpMin, co2max=co2Max, co2min=co2Min, rhmax=rhMax, rhmin=rhMin, timestamp=str(timestamp_utc))

    cur.execute(query) 

    conn.commit()
    print("save_scd_values(): temp, rh and co2 saved to database")


#save_scd_values(23.4, 23.5, 554.7)
