from datetime import datetime, timedelta

sec_last_run = 0

def pic_timelapse(interval): #parameter can be "s","m","h" - seconds, minutes, hours
	global parameter_last_run
	global sec_last_run
	
	if interval == "s":
		timestring = "%S"
	elif interval == "m":
		timestring = "%M"
	elif interval == "h":
		timetring = "%H"
		
	now = datetime.now() # current date and time
	sec_now = now.strftime(timestring)
	
	if sec_now != sec_last_run:
		now = datetime.now() # current date and time
		sec = now.strftime(timestring)
		print(sec)
		
		sec_last_run = now.strftime(timestring)

if __name__ == "__main__": 
	while True :
		pic_timelapse("s")

		


