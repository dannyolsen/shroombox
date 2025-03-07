"""
Noctua PWM Fan Controller for Raspberry Pi
Controls a PWM-capable fan connected to a GPIO pin.
"""

import RPi.GPIO as GPIO
from time import sleep
import os
from typing import Optional, Union

# GPIO Configuration
FAN_PIN: int = 13        # BCM pin used to drive PWM fan
PWM_FREQ: int = 25000    # 25kHz for Noctua PWM control

# Temperature thresholds (°C)
MIN_TEMP: float = 40.0
MAX_TEMP: float = 70.0

# Fan speed limits (%)
FAN_OFF: int = 0
FAN_LOW: int = 40
FAN_HIGH: int = 100
FAN_MAX: int = 100

class NoctuaFan:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NoctuaFan, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not NoctuaFan._initialized:
            self.PWM_PIN = 13
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(self.PWM_PIN, GPIO.OUT)
            self.pwm = GPIO.PWM(self.PWM_PIN, 25000)
            self.pwm.start(0)
            NoctuaFan._initialized = True
    
    def set_speed(self, speed_percent):
        """Set fan speed as percentage (0-100)"""
        if NoctuaFan._initialized:  # Only change speed if initialized
            speed = max(0, min(100, speed_percent))  # Clamp between 0-100
            self.pwm.ChangeDutyCycle(speed)
        
    def emergency_stop(self):
        """Emergency stop - called on program exit"""
        if NoctuaFan._initialized:
            try:
                print("\n=== Fan Emergency Stop ===")
                print("Setting fan speed to 0%...")
                self.set_speed(0)
                
                # Complete shutdown
                print("Forcing pin LOW...")
                self.pwm.stop()
                
                # Don't cleanup, just force pin LOW
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.PWM_PIN, GPIO.OUT, initial=GPIO.LOW)
                GPIO.output(self.PWM_PIN, GPIO.LOW)
                
                NoctuaFan._initialized = False
                NoctuaFan._instance = None
                print("Fan emergency stop completed")
                print("=========================")
            except Exception as e:
                print(f"Failed to stop fan: {e}")

    def get_cpu_temp(self):
        """Get CPU temperature"""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = float(f.read()) / 1000.0
            return temp
        except:
            return None

    def auto_control(self):
        """Automatic control based on CPU temperature"""
        temp = self.get_cpu_temp()
        if temp is None:
            return
        
        if temp > 80:
            self.set_speed(100)
        elif temp > 70:
            self.set_speed(80)
        elif temp > 60:
            self.set_speed(60)
        else:
            self.set_speed(40)

# Create global instance for backward compatibility
fan = NoctuaFan()
setFanSpeed = fan.set_speed  # Legacy support

if __name__ == "__main__":
    try:
        # Test fan speeds
        print("Testing fan speeds...")
        test_speeds = [25, 50, 75, 100]
        
        for speed in test_speeds:
            print(f"Setting fan to {speed}%")
            fan.set_speed(speed)
            sleep(3)
        
        print("Testing auto control...")
        for _ in range(5):
            temp = fan.get_cpu_temp()
            print(f"CPU Temperature: {temp}°C")
            fan.auto_control()
            sleep(2)
            
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    finally:
        print("Cleaning up...")
        fan.emergency_stop()