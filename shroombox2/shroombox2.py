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

"""
Tasks that need completion:
	- logging in influxdb
		- fan activity 		- DONE
		- heatpad activity 	- DONE
		- temp offset value
		
"""

#IMPORTS
import time
import threading
from datetime import datetime, timedelta

import noctua_pwm as fan        #python program writte by me
import influx
import neo_single as neo
import heater as heater

from scd30_i2c import SCD30     #climate measuring device

scd30 = SCD30()
scd30.set_measurement_interval(2)
scd30.start_periodic_measurement()
temp_offset = 0
scd30.set_temperature_offset(temp_offset)
time.sleep(2)
scd30.get_data_ready()
m = scd30.read_measurement()

print(f"CO2: {m[0]:.2f}ppm, temp: {m[1]:.2f}'C, rh: {m[2]:.2f}%")
co2 = float(f"{m[0]:.1f}")
temp = float(f"{m[1]:.2f}")
rh = float(f"{m[2]:.2f}")

fan_percentage = 0
fan_percentage_zero = 0
heater_percentage_zero = 0

time_runfan_stop = datetime.now()
run_fan_seconds = 120
fan_time_set = False

savedata_interval = 10 #seconds
time_zero = datetime.now()
save_data = True

class grow_setpoint:
        temp_max = 24
        temp_min = 23
        co2_max = 1200 	#5000
        co2_min = 1000	#4500
        rh_max = 92
        rh_min = 85
        
class cake_setpoint:
        temp_max = 26.5
        temp_min = 25.5

class neo_data:
		pass

def co2_control(ppm):
        #relay_no = 3 #this is actually number four when you look at the physical device
        global fan_percentage_zero
        global save_data
        #global time_runfan_start
        global time_runfan_stop
        global fan_time_set

        if ppm<=grow_setpoint.co2_min:
            if datetime.now() > time_runfan_stop:
                fan_percentage = 0
                fan.setFanSpeed(fan_percentage)
                fan_time_set = False
                
            else:
                fan_percentage = 10
                
            if (save_data == True or fan_percentage != fan_percentage_zero):
                influx.write_ver18("fan_percentage",["device","noctua_fan"],field=['%',fan_percentage])
                fan_percentage_zero = fan_percentage
                save_data = True
            else:
                pass
                
        elif ppm>grow_setpoint.co2_max:
            fan_percentage = 30
            
            if fan_time_set == False:
                #time_runfan_start = datetime.now().strftime("%H:%M:%S")
                fan.setFanSpeed(fan_percentage)
                
                time_runfan_stop = datetime.now() + timedelta(seconds = run_fan_seconds)
                fan_time_set = True
            else:
                pass
                
            if save_data == True or fan_percentage != fan_percentage_zero:
                influx.write_ver18("fan_percentage",["device","noctua_fan"],field=['%',fan_percentage])
                fan_percentage_zero = fan_percentage
                save_data = True
                
def temp_control(temp, setpoint_max, setpoint_min):
	#aquarium water heater is connected to relay number one (11 / 14)
	global heater_percentage_zero
	global save_data
	
	if temp>setpoint_max:
		heater.off() #stopped
		heater_percentage = 0

		"""
		#TEST FAN FOR HUMIDITY - NOT PART OF FINAL PROGRAM
		fan_percentage = 50
		fan.setFanSpeed(fan_percentage)
		#TEST END
		"""

		if save_data == True or heater_percentage != heater_percentage_zero:
			#influx.write_ver18("heater",["device","heater"],field=['percentage',heater_percentage])
			influx.write_points_ver18(["heater,mode=off percentage={}".format(int(heater_percentage)),])
			print("heater on saved in database")
			#######influx.write_ver18("fan_percentage",["device","noctua_fan"],field=['%',fan_percentage]) #FAN TEST - DELETE WHEN DONE

			heater_percentage_zero = heater_percentage
			
	elif temp<=setpoint_min:
		heater.on() #started
		heater_percentage = 100
		influx.write_ver18("heater",["device","heater"],field=['percentage',heater_percentage])

		"""
		#TEST FAN FOR HUMIDITY - NOT PART OF FINAL PROGRAM----
		fan_percentage = 0
		fan.setFanSpeed(fan_percentage)
		#TEST END
		"""

		if save_data == True or heater_percentage != heater_percentage_zero:
			#influx.write_ver18("heater",["device","heater"],field=['percentage',heater_percentage])
			influx.write_points_ver18(["heater,mode=on percentage={}".format(int(heater_percentage)),])
			print("heater on saved in database")
			########influx.write_ver18("fan_percentage",["device","noctua_fan"],field=['%',fan_percentage]) #FAN TEST - DELETE WHEN DONE

			heater_percentage_zero = heater_percentage

def rh_control(rh): #NOT USED IN SHROOMBOX 2.0
	global humidifier_percentage_zero
	global save_data
	
	if rh>grow_setpoint.rh_max:
		#tb.writeMR_DO4(modbus_adr = 3, relay_no = 0, state = 0) #stopped
		humidifier_percentage = 0

		if save_data == True or humidifier_percentage != humidifier_percentage_zero:
			#dc.save_data('humidifier', humidifier_percentage, '%')
			humidifier_percentage_zero = humidifier_percentage

	elif rh<=grow_setpoint.rh_min:
		#tb.writeMR_DO4(modbus_adr = 3, relay_no = 0, state = 1) #started
		humidifier_percentage = 100

		if save_data == True or humidifier_percentage != humidifier_percentage_zero:
			#dc.save_data('humidifier', humidifier_percentage, '%')
			humidifier_percentage_zero = humidifier_percentage
			#threading.Thread(target=rh_shot).start() #activating the humidity device for x seconds

def light_control():
	time = datetime.now().strftime("%H:%M")
	
	if  time >= "06:00" and time < "18:00" :
		neo.on() #lights on
		neo_data.lights = "on"
	
	else:
		neo.off() #lights off
		neo_data.lights = "off"
	
	print("lights are : {}".format(neo_data.lights))
		

def save_scd30_data():
	influx.write_ver18("co2",["device","sdc30"],field=['ppm',co2])
	influx.write_ver18("humidity",["device","sdc30"],field=['%',rh])
	influx.write_ver18("temperature",["device","sdc30"],field=['°C',temp])
	#influx.write_ver18("temperature_offset",["device","sdc30"],field=['°C',temp_offset])
	#influx.write_points_ver18(["temperature,type=offset,device=scd30 degrees={}".format(temp_offset),]) #NOT SURE IF THIS WORKS - CHECK IT

#---- MAIN ----

#User chooses a program to run
print("What's you plan?")
print("1 : I'm making af Pf-tek cake")
print("2 : I'm growing shroomies")
program_number = int(input("Choose a program: "))

while True:
        #try:
			if scd30.get_data_ready():
				if (datetime.now() - time_zero).total_seconds() > savedata_interval:
					save_data = True #should be TRUE!!!!

				m = scd30.read_measurement()
				
				print(f"CO2: {m[0]:.2f}ppm, temp: {m[1]:.2f}'C, rh: {m[2]:.2f}%")
				co2 = float(f"{m[0]:.1f}")
				temp = float(f"{m[1]:.2f}")
				rh = float(f"{m[2]:.2f}")

				print("Temp offset")
				print(scd30.get_temperature_offset())

				#run the different control functions here -fx. light control, co2, heat and so on
				if program_number == 1:  #CAKE
					temp_control(temp, cake_setpoint.temp_max, cake_setpoint.temp_min)
					co2_control(co2)
					#rh_control(rh)

					if save_data == True:
						#dc.save_data('PrgCake', 1, 'n/a')
						#dc.save_data('PrgGrow', 0, 'n/a')
						#dc.save_setpoints(cake_setpoint.temp_max, cake_setpoint.temp_min, grow_setpoint.temp_max, grow_setpoint.temp_min, grow_setpoint.co2_max, grow_setpoint.co2_min, grow_setpoint.rh_max, grow_setpoint.rh_min)
						pass

				elif program_number == 2:  #GROW
					co2_control(co2)
					temp_control(temp, grow_setpoint.temp_max, grow_setpoint.temp_min)
					#rh_control(rh)
					light_control()

					#Saving program specific data
					if save_data == True:
						influx.write_points_ver18([
							"program,mode=cake PrgCake={}".format(int(0)),
							"program,mode=grow PrgGrow={}".format(int(1)),
							"temperature,setpoint=max,program=cake °C={}".format(cake_setpoint.temp_max),
							"temperature,setpoint=min,program=cake °C={}".format(cake_setpoint.temp_min),
							"temperature,setpoint=max,program=grow °C={}".format(grow_setpoint.temp_min),
							"temperature,setpoint=min,program=grow °C={}".format(grow_setpoint.temp_min),
							"co2,setpoint=min,program=grow ppm={}".format(grow_setpoint.co2_min),
							"co2,setpoint=max,program=grow ppm={}".format(grow_setpoint.co2_max),
							"humidity,setpoint=min,program=grow rh={}".format(grow_setpoint.rh_min),
							"humidity,setpoint=max,program=grow rh={}".format(grow_setpoint.rh_max),
						])
				else:
					pass
				
				#Saving data that needs recording nomatter what program is running - climate data from scd30 sensor
				if save_data == True:
					save_scd30_data()
				time.sleep(2)
			else:
				time.sleep(0.2)
				pass

			if save_data == True:
				time_zero = datetime.now()
				save_data = False
        #except:
        #        print("main program failed, trying to run code again...")
        #        pass
