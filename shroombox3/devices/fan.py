"""
Noctua PWM Fan Controller for Raspberry Pi
Controls a PWM-capable fan connected to a GPIO pin.
"""

import RPi.GPIO as GPIO
from time import sleep
import os
from typing import Optional, Union

from devices.base import Device
from utils.singleton import singleton

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

@singleton
class NoctuaFan(Device):
    """
    Controller for Noctua PWM fan connected to Raspberry Pi GPIO.
    
    This class implements the Device interface and provides methods
    to control a PWM-capable fan.
    """
    
    def __init__(self):
        """Initialize the fan controller."""
        self._initialized = False
        self._current_speed = 0
        self.PWM_PIN = FAN_PIN
        self.pwm = None
        self.initialize()
    
    def initialize(self) -> bool:
        """
        Initialize the fan hardware.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        if not self._initialized:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                GPIO.setup(self.PWM_PIN, GPIO.OUT)
                self.pwm = GPIO.PWM(self.PWM_PIN, PWM_FREQ)
                self.pwm.start(0)
                self._current_speed = 0
                self._initialized = True
                return True
            except Exception as e:
                print(f"Failed to initialize fan: {e}")
                return False
        return True
    
    def set_speed(self, speed_percent: float) -> None:
        """
        Set fan speed as percentage.
        
        Args:
            speed_percent: Fan speed percentage (0-100)
        """
        if self.is_initialized:
            speed = max(0, min(100, speed_percent))  # Clamp between 0-100
            self.pwm.ChangeDutyCycle(speed)
            self._current_speed = speed
    
    def get_speed(self) -> float:
        """
        Get current fan speed as percentage.
        
        Returns:
            float: Current fan speed (0-100)
        """
        return self._current_speed
    
    def get_cpu_temp(self) -> Optional[float]:
        """
        Get CPU temperature.
        
        Returns:
            Optional[float]: CPU temperature in Celsius, or None if unavailable
        """
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = float(f.read()) / 1000.0
            return temp
        except:
            return None
    
    def auto_control(self) -> float:
        """
        Automatic control based on CPU temperature.
        
        Returns:
            float: The new fan speed that was set
        """
        temp = self.get_cpu_temp()
        if temp is None:
            return self._current_speed
        
        if temp > 80:
            self.set_speed(100)
            return 100
        elif temp > 70:
            self.set_speed(80)
            return 80
        elif temp > 60:
            self.set_speed(60)
            return 60
        else:
            self.set_speed(40)
            return 40
    
    def cleanup(self) -> None:
        """Clean up resources before shutdown."""
        if self.is_initialized:
            try:
                print("\n=== Fan Cleanup ===")
                print("Setting fan speed to 0%...")
                self.set_speed(0)
                
                # Complete shutdown
                print("Stopping PWM...")
                self.pwm.stop()
                
                # Force pin LOW
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.PWM_PIN, GPIO.OUT, initial=GPIO.LOW)
                GPIO.output(self.PWM_PIN, GPIO.LOW)
                
                self._initialized = False
                print("Fan cleanup completed")
                print("===================")
            except Exception as e:
                print(f"Failed to clean up fan: {e}")
    
    @property
    def is_initialized(self) -> bool:
        """
        Check if the fan is initialized.
        
        Returns:
            bool: True if the fan is initialized, False otherwise
        """
        return self._initialized
    
    @property
    def name(self) -> str:
        """
        Get the device name.
        
        Returns:
            str: The name of the device
        """
        return "Noctua PWM Fan"


# Create global instance for backward compatibility
fan = NoctuaFan()
setFanSpeed = fan.set_speed  # Legacy support 