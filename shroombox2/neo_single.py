import board
import neopixel
pixels = neopixel.NeoPixel(board.D21, 24) #D21 er GPIO21 dvs. ben 40 på raspberry (24 er antal dioder som er i neopixel ringen)

#pixels[0] = (255, 0, 255)
#pixels[3] = (0, 0, 255)
#pixels[5] = (255, 0, 0)

#pixels[10] = (0, 255, 0)

def on():
    pixels.fill((0, 0, 255))
    pixels.show()

def off():
    pixels.fill((0, 0, 0))
    pixels.show() 

if __name__ == "__main__":
    print("Trying to turn on leds")
    on()