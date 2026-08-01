import time

import board
import adafruit_vl53l1x


i2c = board.I2C()
sensor = adafruit_vl53l1x.VL53L1X(i2c, address=0x29)

# Short-distance mode with a 100 ms measurement budget.
sensor.distance_mode = 1
sensor.timing_budget = 100

print("VL53L1X connected.")
print("Place an object in front of the sensor.")
print("Press Ctrl+C to stop.")

sensor.start_ranging()

try:
    while True:
        if sensor.data_ready:
            distance_cm = sensor.distance
            print(f"Distance: {distance_cm} cm")
            sensor.clear_interrupt()

        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nStopping sensor.")

finally:
    sensor.stop_ranging()
    i2c.deinit()
