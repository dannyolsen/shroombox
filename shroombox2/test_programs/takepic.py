#!/home/pi/Venv/env_shroombox2/bin python3
# -*- coding: utf-8 -*-

import neo_single as neo
from picamera import PiCamera
from time import sleep

def take_pic():
	neo.on()
	camera = PiCamera()
	#camera.start_preview()
	sleep(1)
	camera.capture('/tmp/picture.jpg')
	#camera.stop_preview()
	neo.off()

if __name__ == "__main__": 
	take_pic()
