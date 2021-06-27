# -*- coding: utf-8 -*-

"""
THIS IS THE MAIN PROGRAM

SHROOM GROWING INFORMATION
https://www.shroomology.org/forums/topic/2098-ideal-ppm-co2-concentration/

This was taken right out of The Mushroom cultivator, by paul stamets. 
Spawn Run: 
	Relative Humidity: 90%. 
	Substrate Temperature: 84 - 86°F / 28.8 - 30°C. Thermal death limits have been established at 106°F / 41.1°C. 
	Duration: 10-14 days. CO2: 5000 - 10,000 ppm. Fresh Air Exchanges: 0 per hour. 
	Type of Casing: After fully run, cover with the standard casing whose preparations described in Chapter VIII. 
	
Layer to a depth of Post Casing/Prepinning: 
	Relative Humidity: 90 %. Substrate Temperature: 84 - 86°F / 28.8 - 30°C. 
	Duration of Case Run: 5-10 days. CO2: 5000-10,000 ppm. Fresh Air Exchanges: 0 per hour. 
	Light: Incubation in total darkness. 

Primordia Formation: 
	Relative Humidity: 95-100%. Air Temperature: 74 - 78°F / 23.3 - 25.5°C. 
	Duration: 6-10 days. CO2: less than 5000 ppm. Fresh Air Exchanges: 1 -3 per hour. (For practical purposes, fanning a terrarium 2-3 times a day is sufficient) 
	Light: Diffuse natural or exposure for 12-16 hours/day of grow-lux type fluorescent light high in blue spectra at the 480 nanometer wavelength. (See Chapters IV and IX). 

Cropping: 
	Relative Humidity: 85-92%. (For cakes: 95-100% ) 
	Air Temperature: 74-78°F / 23.3 - 25.5°C. CO2:less than 5000 ppm. 
	Fresh Air Exchanges: 1 -3 per hour. (For practical purposes, fanning a terrarium 2-3 times a day is sufficient) 
	Flushing Pattern: Every 5-8 days. 
	Harvest Stage: When the cap becomes convex and soon after the partial veil ruptures.
"""

#IMPORTS
import time
import threading
from datetime import datetime, timedelta

import noctua_pwm as fan        #python program writte by me

from scd30_i2c import SCD30     #climate measuring device


scd30 = SCD30()

scd30.set_measurement_interval(5)
scd30.start_periodic_measurement()

time.sleep(2)

scd30.get_data_ready()

m = scd30.read_measurement()

print(f"CO2: {m[0]:.2f}ppm, temp: {m[1]:.2f}'C, rh: {m[2]:.2f}%")
co2 = float(f"{m[0]:.1f}")
temp = float(f"{m[1]:.2f}")
rh = float(f"{m[2]:.2f}")
