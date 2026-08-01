"""Hardware-free checks for the LumaBot control boundary."""

import unittest

from daemon import LumaBotDaemon


class FakeMotors:
    ready = True

    def __init__(self):
        self.left = self.right = 0.0

    def set_motors(self, left, right):
        self.left, self.right = left, right

    def coast(self):
        self.left = self.right = 0.0


class FakeBattery:
    def read(self):
        return {"battery_pct": 75.0, "battery_voltage_v": 3.9}


class FakeIndicator:
    def __init__(self):
        self.battery_pct = None
        self.activities = []
        self.closed = False

    def update_battery(self, percent):
        self.battery_pct = percent

    def get_status(self):
        return {"indicator_ready": True, "indicator_mode": "battery"}

    def set_activity(self, lease_id, active, ttl_s):
        self.activities.append((lease_id, active, ttl_s))
        return {"indicator_ready": True, "indicator_mode": "thinking"}

    def close(self):
        self.closed = True


class DaemonTests(unittest.TestCase):
    def setUp(self):
        self.motors = FakeMotors()
        self.indicator = FakeIndicator()
        self.daemon = LumaBotDaemon(self.motors, FakeBattery(), self.indicator)

    def tearDown(self):
        self.daemon.close()

    def test_drive_and_stop(self):
        result = self.daemon.drive("forward", 0.3, 1.0)
        self.assertEqual((self.motors.left, self.motors.right), (0.3, 0.3))
        self.assertTrue(result["watchdog_active"])

        status = self.daemon.stop()
        self.assertEqual(status["mode"], "idle")
        self.assertEqual((self.motors.left, self.motors.right), (0.0, 0.0))

    def test_status_reads_battery(self):
        status = self.daemon.get_status()
        self.assertEqual(status["battery_pct"], 75.0)
        self.assertEqual(status["battery_voltage_v"], 3.9)
        self.assertTrue(status["battery_ready"])
        self.assertEqual(self.indicator.battery_pct, 75.0)
        self.assertTrue(status["indicator_ready"])

    def test_indicator_activity_is_forwarded(self):
        result = self.daemon.set_indicator_activity("run-a", True, 10)
        self.assertEqual(self.indicator.activities, [("run-a", True, 10)])
        self.assertEqual(result["indicator_mode"], "thinking")


if __name__ == "__main__":
    unittest.main()
