import RPi.GPIO as GPIO
import time
import signal
import sys
import os

#FUNCTIONS 
def setFanSpeed(speed):
    fan.start(speed)
    time.sleep(10)
    return()
    
# Configuration
FAN_PIN = 13            # 
FAN_PIN_CPU = 18        # BCM18/BOARD12 pin used to drive PWM fan
WAIT_TIME = 1           # [s] Time to wait between each refresh
PWM_FREQ = 25           # [kHz] 25kHz for Noctua PWM control

# Setup GPIO pin
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

#filter fan
GPIO.setup(FAN_PIN, GPIO.OUT, initial=GPIO.LOW)
fan_filter = GPIO.PWM(FAN_PIN,PWM_FREQ)

#cpu fan
GPIO.setup(FAN_PIN_CPU, GPIO.OUT, initial=GPIO.LOW)
fan_cpu = GPIO.PWM(FAN_PIN_CPU,PWM_FREQ)

#setFanSpeed(20)
controlled_system = 0

if __name__ == "__main__":
    pid = PID(1, 0.1, 0.05, setpoint=1)

    # Assume we have a system we want to control in controlled_system
    v = ppm
    print(v)

    while True:
        # Compute new output from the PID according to the systems current value
        control = pid(ppm)
        print(control)
        
        # Feed the PID output to the system and get its current value
        v = controlled_system + 0.0001
