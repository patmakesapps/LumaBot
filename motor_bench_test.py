"""Briefly verify both mapped wheels on a raised-wheel bench."""

import time

from motors import MotorController


motors = MotorController(enabled=True)

try:
    print("Running both wheels forward at 20% for 0.5 seconds.")
    motors.set_motors(0.2, 0.2)
    time.sleep(0.5)
finally:
    motors.coast()
    print("Both motor channels are coasting.")
