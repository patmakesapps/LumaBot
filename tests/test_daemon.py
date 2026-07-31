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


class DaemonTests(unittest.TestCase):
    def setUp(self):
        self.motors = FakeMotors()
        self.daemon = LumaBotDaemon(self.motors, FakeBattery())

    def tearDown(self):
        self.daemon.stop()

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


if __name__ == "__main__":
    unittest.main()
