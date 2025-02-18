#!//usr/bin/python3
from picamera2 import Picamera2
import neo_single as neo
from time import sleep
from libcamera import Transform

picam2 = Picamera2()
config = picam2.create_still_configuration(transform=Transform(hflip=1, vflip=1))
picam2.configure(config)
picam2.set_controls({"ExposureTime": 60000})

def take(filepath):
    neo.on_white() #lights on
    sleep(1)

    picam2.start()

    np_array = picam2.capture_array()
    #print(np_array)
    picam2.capture_file(filepath)
    picam2.stop()

    neo.off()

if __name__ == "__main__":
    while True:
        neo.on_white()
        sleep(1)
        take('/home/pi/Github/shroombox/shroombox2/timelapse_pics/demo.jpg')
        sleep(5)
        neo.off()
        sleep(2)

    
