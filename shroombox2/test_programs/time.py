from gpiozero import CPUTemperature

cpu = CPUTemperature()
print(cpu.temperature)


"""class fan:
	def __init__(self, fan_pin):
		self.pin 		= fan_pin
		self.wait_time 	= 1
		pwm_freq 		= 25
    
	def setFanSpeed(self):
		print("fan started")
		print(self.pin)
        
fan_cpu = fan(1)

fan_cpu.setFanSpeed()
   """     

