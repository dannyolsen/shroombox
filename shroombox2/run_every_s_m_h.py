#This program will return True when time interval has been reached. Otherwise it will return False
#Program can run intervals every 1 second, every 1 minuet or every 1 hour

from datetime import datetime, timedelta

parameter_now 		= datetime.now()	#just setting a random time time - could be anything
parameter_last_run 	= datetime.now()	#just setting a random time time - could be anything

def pic_timelapse(interval): #parameter can be "s","m","h" - seconds, minutes, hours
	global parameter_now
	global parameter_last_run
	
	if interval == "s":
		timestring = "%S"
	elif interval == "m":
		timestring = "%M"
	elif interval == "h":
		timestring = "%H"
		
	parameter_now = datetime.now().strftime(timestring)
	
	if parameter_now != parameter_last_run:
		#parameter_now = datetime.now().strftime(timestring)
		parameter_last_run = parameter_now
		
		#print("parameter now : " + str(parameter_now))
		
		return True
	
	else:
		return False
	
if __name__ == "__main__": 
	while True :
		if pic_timelapse("s") == True:
			print("timelapse ran")



		


