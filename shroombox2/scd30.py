# -*- coding: utf-8 -*-

from scd30_i2c import SCD30
import time
import threading
from time import sleep

from datetime import datetime, timedelta

scd30 = SCD30()

scd30.set_measurement_interval(2)
scd30.start_periodic_measurement()

time.sleep(2)

# scd30.get_data_ready()

# m = scd30.read_measurement()
# print(m)

# print(f"CO2: {m[0]:.2f}ppm, temp: {m[1]:.2f}'C, rh: {m[2]:.2f}%")
# co2 = float(f"{m[0]:.1f}")
# temp = float(f"{m[1]:.2f}")
# rh = float(f"{m[2]:.2f}")

#def calibrate_co2():
#    scd30.forced_recalibration

if __name__ == "__main__":                  #just for testing purposes
    scd30.set_temperature_offset(0)
    while True:
        if scd30.get_data_ready():
            m = scd30.read_measurement()
            print(f"CO2: {m[0]:.2f}ppm, temp: {m[1]:.2f}'C, rh: {m[2]:.2f}%")

    