import RPi.GPIO as GPIO

# Set the GPIO mode to BCM or BOARD
GPIO.setmode(GPIO.BCM)

# Set the GPIO pin 22 as an output pin
GPIO.setup(22, GPIO.OUT)

# Set the GPIO pin 22 to a high state (1)
GPIO.output(22, GPIO.LOW)

# Cleanup GPIO settings when done
GPIO.cleanup()