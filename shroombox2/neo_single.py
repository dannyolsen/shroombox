#!/home/pi/Venv/env_shroombox2/bin python3
# -*- coding: utf-8 -*-

import board
import neopixel
pixels = neopixel.NeoPixel(board.D12, 119) #D21 er GPIO21 dvs. ben 40 på raspberry (24 er antal dioder som er i neopixel ringen) - ændret til D12

#pixels[0] = (255, 0, 255)
#pixels[3] = (0, 0, 255)
#pixels[5] = (255, 0, 0)

#pixels[10] = (0, 255, 0)

#DICTS
light_status = {                       #current status of the light
    "state" : "",	                #are the lights on or off	
    "rgb" : [0,0,0],                      #[255,255,255]
    "brightness" : "1.0"
    }

#FUNCTIONS
def on_blue():
    light_status["state"]           = "on"
    light_status["rgb"]             = [0,0,255]
    light_status["brightness"]      = 1.0
    pixels.fill((light_status["rgb"]))
    #pixels.brightness = light_status["brightness"]
    pixels.show()

def off():
    light_status["state"]           = "off"
    light_status["rgb"]             = [0,0,0]
    light_status["brightness"]      = 0.0
    pixels.fill((light_status["rgb"]))
    #pixels.brightness = light_status["brightness"]
    pixels.show()
    
def on_white():
    light_status["state"]   = "on"
    light_status["rgb"] = [255,255,255]
    pixels.fill((light_status["rgb"]))
    pixels.show()

if __name__ == "__main__":
    on_white()
    print(light_status)
    off()
    print(light_status)
