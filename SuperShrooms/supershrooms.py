### IMPORTS
import asyncio, time, os
import noctua_pwm 	as fan        #python program writte by me
from scd30_i2c 		import SCD30     #climate measuring device
from simple_pid 	import PID
from datetime       import datetime
from tapo           import ApiClient

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
	co2_max = 550
	rh_max = 60
	rh_min = rh_max - 2
        
class cake_setpoint:
	temp_min = 27.0
	temp_max = temp_min + 0.1
	co2_max = 500
	rh_max = 92
	rh_min = rh_max - 2
	

### INIT SETUP VARS ###
scd30 = SCD30()
scd30.set_measurement_interval(2)   ######DEN SKAL NOK VÆRE 2 FOR AT PID FUNGERER
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

humidity_last_called = time.time()

#PID for CO2 fan
pid = PID(-1, -0.01, -0.0, setpoint=grow_setpoint.co2_max)
pid.output_limits 	= (0, 100)    # Output value will be between 0 and 10

#PID for CPU fan
pid_cpu = PID(-10, -3, 0.05, setpoint=30)
pid_cpu.output_limits 	= (0, 100)    # Output value will be between 0 and 10

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

async def humidity_control():
    global humidity_last_called
    global rh

    on_time = 5
    time_function_break = 30
    
    client = ApiClient("dannyolsen1980@gmail.com", "xerted-6wexwu-nyqraD")
    humidifier = await client.p115("192.168.8.158")

    current_time = time.time()
    timedelta = current_time - humidity_last_called
    print("timedelta : " + str(timedelta))

    if rh<grow_setpoint.rh_max and timedelta>time_function_break:
        humidity_last_called = time.time()
        print("humid on - setpoint : " + str(grow_setpoint.rh_max))
        await humidifier.on()
        await asyncio.sleep(on_time)
        print("off")   
        await humidifier.off()   

    elif rh>grow_setpoint.rh_max and timedelta>5:
        print("humid off - setpoint : " + str(grow_setpoint.rh_max))   
        humidity_last_called = time.time()
        await humidifier.off() 

async def main():
    while True: 	
        if scd30.get_data_ready():		#get clima data
            try:
                m = scd30.read_measurement()

                os.system('clear')
                print(f"CO2: {m[0]:.2f}ppm, temp: {m[1]:.2f}'C, rh: {m[2]:.2f}%")
                co2 = float(f"{m[0]:.1f}")
                temp = float(f"{m[1]:.2f}")
                rh = float(f"{m[2]:.2f}")

            except:
                print("Exception has made - co2, temp and rh set to None...")
                co2 = None
                temp = None
                rh = None

            finally:
                pass

            co2_control(grow_setpoint.co2_max)
            asyncio.create_task(humidity_control())
            #temp_control(temp, grow_setpoint.temp_max, grow_setpoint.temp_min)
            #rh_control(rh)	#could be controlled with fan while prioritising co2
            #light_control(t_start="11:00",t_end="23:00")

            #await asyncio.sleep(0)
        await asyncio.sleep(0.2)

asyncio.run(main())
#asyncio.run(humidity_control())
