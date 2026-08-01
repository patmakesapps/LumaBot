import time

import board
from rainbowio import colorwheel
from adafruit_seesaw import neopixel
from adafruit_seesaw.analoginput import AnalogInput
from adafruit_seesaw.seesaw import Seesaw


i2c = board.I2C()
neoslider = Seesaw(i2c, 0x30)
potentiometer = AnalogInput(neoslider, 18)
pixels = neopixel.NeoPixel(neoslider, 14, 4, pixel_order=neopixel.GRB)
pixels.brightness = 0.25

print("NeoSlider connected. Move the slider to change color.")
print("Press Ctrl+C to stop and turn the LEDs off.")

try:
    pixels.fill((0, 0, 0))
    for index, color in enumerate(((255, 0, 0), (255, 120, 0), (0, 255, 0), (0, 0, 255))):
        pixels[index] = color
        time.sleep(0.25)

    while True:
        value = potentiometer.value
        color = colorwheel(int(value / 1023 * 255))
        pixels.fill(color)
        print(f"\rSlider: {value:4d}/1023  Color: #{color:06X}", end="", flush=True)
        time.sleep(0.05)
except KeyboardInterrupt:
    print("\nStopping NeoSlider.")
finally:
    pixels.fill((0, 0, 0))
    i2c.deinit()
