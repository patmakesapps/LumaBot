"""Hardware-free checks for the LumaBot control boundary."""

from pathlib import Path
import unittest

from daemon import CONTROL_INTERVAL_S, AutonomyUnavailable, LumaBotDaemon, ObstacleSafetyError


class FakeMotors:
    ready = True

    def __init__(self):
        self.left = self.right = 0.0

    def set_motors(self, left, right):
        self.left, self.right = left, right

    def coast(self):
        self.left = self.right = 0.0


class FakeBattery:
    def __init__(self, percent=75.0, voltage=3.9):
        self.percent = percent
        self.voltage = voltage

    def read(self):
        return {"battery_pct": self.percent, "battery_voltage_v": self.voltage}


class FakeCamera:
    ready = True

    def capture(self):
        return Path("/tmp/visitor-lx1-test.jpg")


class FakeDistance:
    ready = True

    def __init__(self, distance_mm=900, fresh=True):
        self.distance_mm = distance_mm
        self.fresh = fresh
        self.closed = False

    def sample(self, now=None):
        return {
            "distance_ready": self.ready,
            "distance_mm": self.distance_mm,
            "distance_age_s": 0.0 if self.fresh else 1.0,
            "distance_fresh": self.fresh,
        }

    def close(self):
        self.closed = True


class FakeMotion:
    ready = True

    def __init__(self):
        self.double_tap = False
        self.dynamic_g = 0.0
        self.tilt = 0.0
        self.closed = False

    def sample(self):
        return {
            "motion_ready": self.ready,
            "acceleration_m_s2": (0.0, 0.0, 9.806),
            "acceleration_g": 1.0,
            "dynamic_acceleration_g": self.dynamic_g,
            "tilt_degrees": self.tilt,
            "double_tap": self.double_tap,
        }

    def close(self):
        self.closed = True


class FakeIndicator:
    def __init__(self):
        self.battery_pct = None
        self.battery_voltage_v = None
        self.activities = []
        self.autonomous = []
        self.events = []
        self.closed = False

    def update_battery(self, percent, voltage_v=None):
        self.battery_pct = percent
        self.battery_voltage_v = voltage_v

    def get_status(self):
        return {"indicator_ready": True, "indicator_mode": "battery"}

    def set_activity(self, lease_id, active, ttl_s):
        self.activities.append((lease_id, active, ttl_s))
        return {"indicator_ready": True, "indicator_mode": "thinking"}

    def set_autonomous(self, active):
        self.autonomous.append(active)
        return self.get_status()

    def signal_event(self, event, duration_s):
        self.events.append((event, duration_s))
        return self.get_status()

    def close(self):
        self.closed = True


class DaemonTests(unittest.TestCase):
    def test_control_loop_can_observe_short_tap_interrupt(self):
        self.assertLessEqual(CONTROL_INTERVAL_S, 0.0125)

    def setUp(self):
        self.motors = FakeMotors()
        self.indicator = FakeIndicator()
        self.distance = FakeDistance()
        self.motion = FakeMotion()
        self.battery = FakeBattery()
        self.camera = FakeCamera()
        self.daemon = LumaBotDaemon(
            self.motors,
            self.battery,
            self.indicator,
            camera=self.camera,
            distance=self.distance,
            motion=self.motion,
            gestures_enabled=True,
            control_autostart=False,
            clock=lambda: 0.0,
        )

    def tearDown(self):
        self.daemon.close()

    def test_drive_and_stop(self):
        result = self.daemon.drive("forward", 0.3, 1.0)
        self.assertEqual((self.motors.left, self.motors.right), (0.3, 0.3))
        self.assertTrue(result["watchdog_active"])
        self.assertTrue(result["obstacle_safety_active"])

        status = self.daemon.stop()
        self.assertEqual(status["mode"], "idle")
        self.assertEqual((self.motors.left, self.motors.right), (0.0, 0.0))

    def test_status_reads_battery(self):
        status = self.daemon.get_status()
        self.assertEqual(status["battery_pct"], 75.0)
        self.assertEqual(status["battery_voltage_v"], 3.9)
        self.assertTrue(status["battery_ready"])
        self.assertEqual(self.indicator.battery_pct, 75.0)
        self.assertEqual(self.indicator.battery_voltage_v, 3.9)
        self.assertTrue(status["indicator_ready"])
        self.assertTrue(status["camera_ready"])

    def test_camera_capture_is_forwarded(self):
        result = self.daemon.capture_photo()
        self.assertEqual(result["filename"], "visitor-lx1-test.jpg")

    def test_indicator_activity_is_forwarded(self):
        result = self.daemon.set_indicator_activity("run-a", True, 10)
        self.assertEqual(self.indicator.activities, [("run-a", True, 10)])
        self.assertEqual(result["indicator_mode"], "thinking")

    def test_double_tap_toggles_autonomy(self):
        self.motion.double_tap = True
        self.daemon._control_tick(2.0)
        self.assertTrue(self.daemon.autonomy.active)
        self.assertEqual((self.motors.left, self.motors.right), (0.0, 0.0))

        self.motion.double_tap = False
        self.daemon._control_tick(2.1)
        self.assertEqual((self.motors.left, self.motors.right), (0.7, 0.7))

        self.motion.dynamic_g = 1.6
        self.daemon._control_tick(3.3)
        self.motion.dynamic_g = 0.0
        self.daemon._control_tick(3.4)
        self.motion.dynamic_g = 1.6
        self.daemon._control_tick(3.6)
        self.assertFalse(self.daemon.autonomy.active)
        self.assertEqual(self.daemon.status.last_stop_reason, "double_tap")

    def test_acceleration_peaks_are_a_double_tap_fallback(self):
        self.motion.dynamic_g = 0.5
        self.daemon._control_tick(2.0)
        self.motion.dynamic_g = 0.0
        self.daemon._control_tick(2.1)
        self.motion.dynamic_g = 0.5
        self.daemon._control_tick(2.3)

        self.assertTrue(self.daemon.autonomy.active)
        self.assertEqual(self.daemon.status.last_gesture, "double_tap")

    def test_tap_tilt_spike_does_not_block_autonomy(self):
        self.motion.double_tap = True
        self.motion.tilt = 70.0
        self.daemon._control_tick(2.0)

        self.assertTrue(self.daemon.autonomy.active)

    def test_sustained_hardware_tap_is_only_one_gesture(self):
        self.motion.double_tap = True
        self.daemon._control_tick(2.0)
        self.daemon._control_tick(3.3)

        self.assertTrue(self.daemon.autonomy.active)

    def test_motor_vibration_does_not_stop_autonomy(self):
        self.motion.double_tap = True
        self.daemon._control_tick(2.0)
        self.motion.double_tap = False
        self.daemon._control_tick(2.1)
        self.motion.double_tap = True
        self.motion.dynamic_g = 0.5
        self.daemon._control_tick(3.3)

        self.assertTrue(self.daemon.autonomy.active)

    def test_manual_drive_cancels_autonomy(self):
        self.daemon.start_autonomy()
        self.daemon.drive("left", 0.3, 1.0)
        self.assertFalse(self.daemon.autonomy.active)
        self.assertEqual((self.motors.left, self.motors.right), (-0.3, 0.3))

    def test_stale_distance_blocks_autonomy_and_forward_drive(self):
        self.distance.fresh = False
        with self.assertRaises(AutonomyUnavailable):
            self.daemon.start_autonomy()
        with self.assertRaises(ObstacleSafetyError):
            self.daemon.drive("forward", 0.3, 1.0)

    def test_close_obstacle_blocks_manual_forward_drive(self):
        self.distance.distance_mm = 200
        with self.assertRaises(ObstacleSafetyError):
            self.daemon.drive("forward", 0.3, 1.0)

    def test_true_low_battery_blocks_autonomy(self):
        self.battery.percent = 15.0
        self.battery.voltage = 3.55
        with self.assertRaises(AutonomyUnavailable):
            self.daemon.start_autonomy()

    def test_lost_battery_reading_stops_active_autonomy(self):
        self.daemon.start_autonomy()
        self.battery.percent = None
        self.battery.voltage = None
        self.daemon._control_tick(0.1)
        self.assertFalse(self.daemon.autonomy.active)
        self.assertEqual((self.motors.left, self.motors.right), (0.0, 0.0))
        self.assertIn("battery status", self.daemon.status.autonomy_blocked_reason)

    def test_stale_distance_coasts_active_autonomy(self):
        self.daemon.start_autonomy()
        self.daemon._control_tick(0.1)
        self.assertEqual((self.motors.left, self.motors.right), (0.7, 0.7))
        self.distance.fresh = False
        self.daemon._control_tick(0.2)
        self.assertEqual((self.motors.left, self.motors.right), (0.0, 0.0))
        self.assertTrue(self.daemon.autonomy.active)

    def test_collision_coasts_then_enters_recovery(self):
        self.daemon.start_autonomy()
        self.daemon._control_tick(0.1)
        self.assertEqual((self.motors.left, self.motors.right), (0.7, 0.7))

        self.motion.dynamic_g = 1.2
        self.daemon._control_tick(0.2)
        self.assertEqual((self.motors.left, self.motors.right), (0.0, 0.0))
        self.assertEqual(self.daemon.status.collision_count, 1)
        self.assertEqual(self.indicator.events[-1], ("collision", 3.0))

        self.motion.dynamic_g = 0.0
        self.daemon._control_tick(0.3)
        self.assertEqual((self.motors.left, self.motors.right), (-0.55, -0.55))

    def test_tilt_stops_motion_after_three_samples(self):
        self.daemon.start_autonomy()
        self.daemon._control_tick(0.1)
        self.motion.tilt = 60.0
        for now in (0.2, 0.25, 0.3):
            self.daemon._control_tick(now)
        self.assertFalse(self.daemon.autonomy.active)
        self.assertEqual((self.motors.left, self.motors.right), (0.0, 0.0))
        self.assertEqual(self.indicator.events[-1], ("tilt", 3.0))


if __name__ == "__main__":
    unittest.main()
