"""Temporary live MSA311 readout; press Ctrl+C to stop."""

import time

from motion_sensor import MotionSensor


sensor = MotionSensor(enabled=True)
if not sensor.ready:
    raise SystemExit("MSA311 did not initialize")

print("MSA311 connected. Double-tap it or gently move the robot.")
print("Press Ctrl+C to stop.")

try:
    while True:
        reading = sensor.sample()
        print(
            f"xyz={reading['acceleration_m_s2']} "
            f"dynamic={reading['dynamic_acceleration_g']:.2f} g "
            f"tilt={reading['tilt_degrees']:.1f} deg "
            f"double_tap={reading['double_tap']}"
        )
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\nStopping sensor.")
finally:
    sensor.close()
