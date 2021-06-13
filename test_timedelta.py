from datetime import datetime
from datetime import timedelta
from time import sleep


time = datetime.now()

time = time.strftime("%H:%M")

if time > "01:10":
	print("time is later than 01:15")

else:
	print("time is not later than 01:15")
