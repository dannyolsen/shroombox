import RPi.GPIO as GPIO
import time
import signal
import sys
import os

# Configuration
FAN_PIN = 18            # BCM18/BOARD12 pin used to drive PWM fan
WAIT_TIME = 1           # [s] Time to wait between each refresh
PWM_FREQ = 25           # [kHz] 25kHz for Noctua PWM control

# Set fan speed
def setFanSpeed(speed):
    fan.start(speed)
    time.sleep(10)
    return()


    # Setup GPIO pin
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(FAN_PIN, GPIO.OUT, initial=GPIO.LOW)
fan = GPIO.PWM(FAN_PIN,PWM_FREQ)

setFanSpeed(20)