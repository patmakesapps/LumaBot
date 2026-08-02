"""Hardware-free checks for the VL53L1X and MSA311 adapters."""

import unittest

from distance import DistanceSensor
from motion_sensor import MotionSensor


class FakeDistanceDevice:
    def __init__(self):
        self.data_ready = True
        self.distance = 42.3
        self.range_status = 9
        self.started = False
        self.stopped = False
        self.cleared = 0

    def start_ranging(self):
        self.started = True

    def stop_ranging(self):
        self.stopped = True

    def clear_interrupt(self):
        self.cleared += 1

    def _read_register(self, register):
        self.assert_range_status_register = register
        return bytes((self.range_status,))


class FakeMotionDevice:
    def __init__(self):
        self.acceleration = (0.0, 0.0, 9.806)
        self.tapped = False
        self.tap_settings = None

    def enable_tap_detection(self, **settings):
        self.tap_settings = settings


class SensorTests(unittest.TestCase):
    def test_distance_is_converted_and_becomes_stale(self):
        device = FakeDistanceDevice()
        sensor = DistanceSensor(device=device, clock=lambda: 0.0)

        reading = sensor.sample(1.0)
        self.assertTrue(device.started)
        self.assertEqual(device.distance_mode, 2)
        self.assertEqual(device.timing_budget, 100)
        self.assertEqual(reading["distance_mm"], 423)
        self.assertTrue(reading["distance_fresh"])

        device.data_ready = False
        reading = sensor.sample(1.5)
        self.assertEqual(reading["distance_mm"], 423)
        self.assertFalse(reading["distance_fresh"])
        sensor.close()
        self.assertTrue(device.stopped)

    def test_no_target_is_fresh_clear_space(self):
        device = FakeDistanceDevice()
        device.distance = None
        device.range_status = 4
        reading = DistanceSensor(device=device).sample(1.0)

        self.assertEqual(reading["distance_mm"], 4000)
        self.assertTrue(reading["distance_fresh"])

    def test_motion_reports_double_tap_impact_and_tilt(self):
        device = FakeMotionDevice()
        sensor = MotionSensor(device=device)
        first = sensor.sample()

        self.assertTrue(first["motion_ready"])
        self.assertEqual(first["tilt_degrees"], 0.0)
        self.assertEqual(device.tap_settings["tap_count"], 2)
        self.assertEqual(device.tap_settings["threshold"], 8)

        device.acceleration = (9.806, 0.0, 0.0)
        device.tapped = True
        second = sensor.sample()
        self.assertTrue(second["double_tap"])
        self.assertAlmostEqual(second["tilt_degrees"], 90.0, delta=0.1)
        self.assertGreater(second["dynamic_acceleration_g"], 1.3)

    def test_disabled_sensors_are_safe(self):
        self.assertFalse(DistanceSensor().sample()["distance_ready"])
        self.assertFalse(MotionSensor().sample()["motion_ready"])


if __name__ == "__main__":
    unittest.main()
