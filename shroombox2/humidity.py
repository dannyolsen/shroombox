import RPi.GPIO as GPIO
import time
import signal
import sys
import os

# Configuration
PIN = 22                # BOARD pin used to drive pull relay
WAIT_TIME = 1           # [s] Time to wait between each refresh
PWM_FREQ = 25           # [kHz] 25kHz for Noctua PWM control

GPIO.setwarnings(False)
#GPIO.setmode(GPIO.BOARD)
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN, GPIO.OUT, initial=GPIO.LOW)

def on():
    GPIO.output(PIN, GPIO.HIGH)

def off():
    GPIO.output(PIN, GPIO.LOW)