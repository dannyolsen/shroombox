import board
import neopixel
pixels = neopixel.NeoPixel(board.D21, 24)

#pixels[0] = (255, 0, 255)
#pixels[3] = (0, 0, 255)
#pixels[5] = (255, 0, 0)

#pixels[10] = (0, 255, 0)

pixels.fill((0, 255, 0))

pixels.show()
