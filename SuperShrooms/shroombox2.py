#!/home/pi/Venv/env_shroombox2/bin python3
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
		- temp offset value - DONE (relative humidity does go a bit to high though
		- make PID's run on specific intervals - like once a second or so...
			- create class or function that triggers true every interval
		- Overvej at putte en vandsensor i humidifier så man kan se om der mangler vand i den
		
"""

#region IMPORTS
import sys, select, os # to quit program on pressing enter
import 	time
import 	threading
from 	datetime 	import datetime, timedelta

import noctua_pwm 	as fan        #python program writte by me
#import neo_single 	as neo		  #not used anymore - will control phillips hue at one point instead
import heater 		as heater
import humidity		as humidity

from scd30_i2c 		import SCD30     #climate measuring device

from simple_pid 	import PID

import picture

#INFLUX27
import influxdb_client, os, time
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

token = os.environ.get("INFLUXDB_TOKEN")
org = "dannyolsen"
url = "http://192.168.87.37:8086"

token = "f5kVhve7HO2yJggJeYueKNoL18a89bRWgV91GbvQ-GGa-k_MCHHSK2WoDALLWEQbBJDAXQIsMCEFa-ox_K4Omg=="
write_client = influxdb_client.InfluxDBClient(url=url, token=token, org=org)

bucket="shroomcabinet"

write_api = write_client.write_api(write_options=SYNCHRONOUS)
#INFLUX27 END


#from picamera 		import PiCamera
from time 			import sleep

import run_every_s_m_h as pic_interval

from gpiozero import CPUTemperature
#endregion

### CLASSES ###
class setpoints_colonisation:
    temp_min = 27.0
    temp_max = temp_min + 0.1
    co2_max = 1000
    rh_max = 10
    rh_min = rh_max - 2	

class grow_setpoint:
	temp_min = 22.0
	temp_max = temp_min + 0.1
	co2_max = 700
	rh_max = 92
	rh_min = rh_max - 2
        
class cake_setpoint:
	temp_min = 27.0
	temp_max = temp_min + 0.1
	co2_max = 500
	rh_max = 92
	rh_min = rh_max - 2

class program_settings:
	program_running			= None			#so we know what mode we are in - cake or grow

#program_settings.cpu_temp.pid_setpoint	
	
### INIT SETUP VARS ###
scd30 = SCD30()
scd30.set_measurement_interval(14)   ######DEN SKAL NOK VÆRE 2 FOR AT PID FUNGERER
scd30.start_periodic_measurement()
temp_offset = 2
scd30.set_temperature_offset(temp_offset)
time.sleep(2)

scd30.get_data_ready()
m = scd30.read_measurement()

print(f"CO2: {m[0]:.2f}ppm, temp: {m[1]:.2f}'C, rh: {m[2]:.2f}%")
co2 = float(f"{m[0]:.1f}")
temp = float(f"{m[1]:.2f}")
rh = float(f"{m[2]:.2f}")

fan_percentage = 0
fan_percentage_old = 0
heater_percentage = 0
heater_percentage_old = 0

time_runfan_stop = datetime.now()
run_fan_seconds = 120
fan_time_set = False

savedata_interval = 60 #seconds
time_zero = datetime.now()
save_data = True

#PID for CO2 fan
pid = PID(-1, -0.0001, -0.0, setpoint=grow_setpoint.co2_max)
pid.output_limits 	= (0, 100)    # Output value will be between 0 and 10

#PID for CPU fan
pid_cpu = PID(-10, -3, 0.05, setpoint=30)
pid_cpu.output_limits 	= (0, 100)    # Output value will be between 0 and 10

#camera = PiCamera()		#this can only be set once otherwise the program will not function
#NEO DATA
light_status = {
	"status": "",       #on or off
	"rgb" : []			#[255,255,255]
}

### FUNCTIONS ###
def co2_control(setpoint_max):
	global fan_percentage_old
	global save_data
	
	print("pid setpoint is: {}".format(str(setpoint_max)))
	
	v 	= co2		#ppm level in shroombox so the pid can figure out how much air to fan
	print("from co2_control() ppm is : {}".format(co2))
	
	fan_percentage = float(pid(co2))
	fan.setFanSpeed(fan_percentage)	#setting new fan speed from calculated pid
	print("fanspeed has been set to : {}".format(fan_percentage))

	if save_data == True:# or fan_percentage != fan_percentage_old:	#save data if it has changed since last time
		timestamp = datetime.utcnow()
		p = []
		cabinet = 1
		location = "Acidman"

		p.append(Point("airfan_percent").tag("location", location).tag("cabinet", cabinet).field("airfan", fan_percentage).time(timestamp))
		
		write_api.write(bucket=bucket, org="dannyolsen", record=p)

		humidifier_percentage_old = humidifier_percentage #will only log everytime the percentage changes
		fan_percentage_old = fan_percentage
	# 	save_data = True

def temp_control(temp, setpoint_max, setpoint_min):
	global heater_percentage_old
	global heater_percentage
	global save_data
	
	if temp>setpoint_max:
		heater.off() #stopped
		heater_percentage = 0.0
			
	elif temp<=setpoint_min:
		heater.on() #started
		heater_percentage = 100.0

	if save_data == True or heater_percentage != heater_percentage_old:
		timestamp = datetime.utcnow()
		p = []
		cabinet = 1
		location = "Acidman"

		p.append(Point("airheater").tag("location", location).tag("cabinet", cabinet).field("heater", float(heater_percentage)).time(timestamp))
		
		write_api.write(bucket=bucket, org="dannyolsen", record=p)
		
		heater_percentage_old = heater_percentage

def rh_control(rh): 
	global humidifier_percentage
	global save_data
	global humidifier_percentage_old
	
	if rh>grow_setpoint.rh_max:
		humidity.off()
		humidifier_percentage = 0

	elif rh<=grow_setpoint.rh_min:
		humidity.on()
		humidifier_percentage = 100

	if save_data == True or humidifier_percentage != humidifier_percentage_old:
		timestamp = datetime.utcnow()
		p = []
		cabinet = 1
		location = "Acidman"

		p.append(Point("humidifier").tag("location", location).tag("cabinet", cabinet).field("humidity", humidifier_percentage).time(timestamp))
		
		write_api.write(bucket=bucket, org="dannyolsen", record=p)

		humidifier_percentage_old = humidifier_percentage #will only log everytime the percentage changes
			
def light_control(t_start, t_end):
	global light_brightness_old
	#specify time start and time end like "06:00" and "19:00"
	time_now = datetime.now().strftime("%H:%M")

	time_now 	= datetime.strptime(time_now, "%H:%M")
	time_start 	= datetime.strptime(t_start, "%H:%M")
	time_end 	= datetime.strptime(t_end, "%H:%M")
	
	if  time_now >= time_start and time_now <= time_end and neo.light_status["state"] != "on": #blue lights if withing time period
		print("blue lights on")
		neo.on_blue() #lights on
	
	elif (time_now > time_end or time_now < time_start) and neo.light_status["state"] != "off":  #lights off when outside time period
		print("lights off")
		neo.off() #lights off

	if save_data == True or neo.light_status["brightness"] != light_brightness_old:
		timestamp = datetime.utcnow()
		cabinet = 1
		location = "Acidman"
		
		write_api.write(bucket=bucket, org="dannyolsen", record=Point("lights").tag("location", location).tag("cabinet", cabinet).field("brightness", neo.light_status["brightness"]).time(timestamp))

		light_status_old = neo.light_status["brightness"] #will only log everytime it changes		
def save_scd30_data():
	influx.write_ver18("co2",["device","sdc30"],field=['ppm',co2])
	influx.write_ver18("humidity",["device","sdc30"],field=['%',rh])
	influx.write_ver18("temperature",["device","sdc30"],field=['°C',temp])
	#influx.write_ver18("temperature_offset",["device","sdc30"],field=['°C',temp_offset])

def take_pic(folder):
	time = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
	filepath = folder+'{}_{}.jpg'.format(program_settings.program_running, time)
	picture.take(filepath)
	

def cpu_temp_control():
	cpu = CPUTemperature()
	print("cpu temp is : {}".format(str(cpu.temperature)))
	
	fan_speed = float(pid_cpu(cpu.temperature))
	fan.fan_cpu.start(fan_speed)		#setting fan speed on cpu
	
	#fan.setFanSpeed(fan_speed)		#setting new fan speed from calculated pid
	print("CPU fanspeed has been set to : {}".format(fan_speed))

	"""
	if save_data == True or fan_percentage != fan_percentage_zero:	#save data if it has changed since last time
		influx.write_ver18("fan_percentage",["device","noctua_fan"],field=['%',fan_percentage])
		fan_percentage_zero = fan_percentage
		save_data = True
	"""
	
def quit_if_enter_is_pressed():
	if sys.stdin in select.select([sys.stdin], [], [], 0)[0]: #
		exit()

#---- MAIN ----
fanspeed = 0

#User chooses a program to run
print("To QUIT program while it is running, just press enter...")
print("What's you plan?")
print("1 : I'm making af Pf-tek cake")
print("2 : I'm growing shroomies")
print("3 : I'm colonzing rye in glasses")
program_number = int(input("Choose a program: "))

if program_number == 1:
	program_settings.program_running = "Cake"

if program_number == 2:
	program_settings.program_running = "Grow"

if program_number == 3:
	program_settings.program_running = "Colonisation"
	
sleep(1) #to prevent program from exiting on enter pressed
fan.setFanSpeed(0)	#Setting initial fan speed
humidifier_percentage		= 0
humidifier_percentage_zero 	= 0
humidifier_percentage_old 	= 0
light_brightness_old		= 0 

while True:
        #try:
			quit_if_enter_is_pressed()
			#cpu_temp_control()
				
			if scd30.get_data_ready():		#get clima data
				if (datetime.now() - time_zero).total_seconds() > savedata_interval:
					save_data = True #should be TRUE!!!!

				try:
					m = scd30.read_measurement()

					os.system('clear')
					print(f"CO2: {m[0]:.2f}ppm, temp: {m[1]:.2f}'C, rh: {m[2]:.2f}%")
					co2 = float(f"{m[0]:.1f}")
					temp = float(f"{m[1]:.2f}")
					rh = float(f"{m[2]:.2f}")

					#print("Temp offset")
					#print(scd30.get_temperature_offset())
				
				except:
					timestamp = datetime.utcnow()
					cabinet = 1
					location = "Acidman"
					write_api.write(bucket=bucket, org="dannyolsen", record=Point("sdc_error")
					 	.tag("location", location)
						.tag("cabinet", cabinet)
						.field("sdc_error", 1)
						.time(timestamp))
						
					print("Exception has made - co2, temp and rh set to None...")
					co2 = None
					temp = None
					rh = None

				finally:
					pass

				#run the different control functions here -fx. light control, co2, heat and so on
				if program_number == 1:  #CAKE
					temp_control(temp, cake_setpoint.temp_max, cake_setpoint.temp_min)
					co2_control(cake_setpoint.co2_max)
					temp_control(temp, cake_setpoint.temp_max, cake_setpoint.temp_min)
					neo.off() 			#lights off during cake program
					rh_control(rh)		#this could be controlled with the fan in Cake program

				elif program_number == 2:  #GROW
					co2_control(grow_setpoint.co2_max)
					temp_control(temp, grow_setpoint.temp_max, grow_setpoint.temp_min)
					rh_control(rh)	#could be controlled with fan while prioritising co2
					light_control(t_start="11:00",t_end="23:00")

				elif program_number == 3:  #COLONIZATION
					temp_control(temp, setpoints_colonisation.temp_max, setpoints_colonisation.temp_min)
					neo.off() 			#lights off during cake program
					humidity.off()
					fan.setFanSpeed(0)		#setting new fan speed from calculated pid

				else:
					pass

				#Saving program specific data
				if save_data == True:
					timestamp = datetime.utcnow()
					p = []
					cabinet = 1
					location = "Acidman"

					p.append(Point("rh_percent").tag(	"location", location).tag("cabinet", cabinet).field("humidity", rh).time(		timestamp))
					p.append(Point("co2_ppm").tag(		"location", location).tag("cabinet", cabinet).field("co2", co2).time(			timestamp))
					p.append(Point("temp_degrees").tag(	"location", location).tag("cabinet", cabinet).field("temperature", temp).time(	timestamp))
					
					write_api.write(bucket=bucket, org="dannyolsen", record=p)
				
			else:
				time.sleep(0.2)
				pass

			if save_data == True:
				time_zero = datetime.now()
				save_data = False
		
			if pic_interval.pic_timelapse("h") == True:
				print("taking picture")
				take_pic(folder = '/home/pi/Github/shroombox/shroombox2/timelapse_pics/')
		

        #except:
        #        print("main program failed, trying to run code again...")
        #        pass
