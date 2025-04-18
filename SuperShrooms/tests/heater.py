import RPi.GPIO as GPIO
import time
import signal
import sys
import os
from time import sleep

# Configuration
PIN = 22              # BOARD pin used to drive pull relay
WAIT_TIME = 1           # [s] Time to wait between each refresh
PWM_FREQ = 25           # [kHz] 25kHz for Noctua PWM control

GPIO.setwarnings(False)
#GPIO.setmode(GPIO.BOARD)
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN, GPIO.OUT, initial=GPIO.HIGH)

def on():
    GPIO.output(PIN, GPIO.LOW)

def off():
    GPIO.output(PIN, GPIO.HIGH)
    
if __name__ == "__main__":
    off()