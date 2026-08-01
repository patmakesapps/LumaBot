"""Hardware-free checks for NeoSlider status lighting."""

import unittest
from unittest import mock

from indicator import CYAN, GREEN, ORANGE, IndicatorController, OFF, PURPLE, RED, battery_color


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class FakeBattery:
    def __init__(self, percent=75.0):
        self.percent = percent

    def read(self):
        return {"battery_pct": self.percent, "battery_voltage_v": 3.9}


class FakePixels:
    def __init__(self):
        self.colors = []
        self.closed = False

    def fill(self, color):
        self.colors.append(color)

    def close(self):
        self.closed = True


class IndicatorTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.pixels = FakePixels()
        self.indicator = IndicatorController(
            FakeBattery(),
            enabled=True,
            pixels=self.pixels,
            clock=self.clock,
            autostart=False,
            startup_pulse_s=0,
        )

    def tearDown(self):
        self.indicator.close()

    def test_battery_color_is_green_until_fifteen_percent(self):
        self.assertEqual(battery_color(100), GREEN)
        self.assertEqual(battery_color(20), GREEN)
        self.assertEqual(battery_color(15.01), GREEN)
        self.assertEqual(battery_color(15), RED)
        self.assertEqual(battery_color(0), RED)

    def test_voltage_prevents_premature_red_warning(self):
        self.indicator.update_battery(10, 3.61)
        self.assertEqual(self.indicator.get_status()["indicator_mode"], "battery")
        color = self.indicator.render_frame(0.0)
        self.assertEqual(color, GREEN)

        self.indicator.update_battery(15, 3.55)
        self.assertEqual(self.indicator.get_status()["indicator_mode"], "low_battery")
        self.indicator.update_battery(5, 3.45)
        self.assertEqual(self.indicator.get_status()["indicator_mode"], "low_battery")
        self.indicator.update_battery(5, 3.4)
        self.assertEqual(self.indicator.get_status()["indicator_mode"], "critical_battery")

    def test_startup_pulses_green_then_becomes_steady(self):
        indicator = IndicatorController(
            FakeBattery(),
            enabled=True,
            pixels=FakePixels(),
            clock=self.clock,
            autostart=False,
            startup_pulse_s=8,
        )
        indicator.update_battery(75, 3.9)

        self.assertEqual(indicator.get_status()["indicator_mode"], "startup")
        self.assertNotEqual(indicator.render_frame(0.0), GREEN)
        self.assertEqual(indicator.render_frame(0.75), GREEN)
        self.clock.now = 8
        self.assertEqual(indicator.get_status()["indicator_mode"], "battery")
        self.assertEqual(indicator.render_frame(), GREEN)
        indicator.close()

    def test_low_and_critical_battery_override_thinking(self):
        self.indicator.update_battery(75)
        self.indicator.set_activity("run-a", True)
        self.assertEqual(self.indicator.get_status()["indicator_mode"], "thinking")
        self.assertNotEqual(self.indicator.render_frame(0.0), PURPLE)
        self.assertEqual(self.indicator.render_frame(0.75), PURPLE)

        self.indicator.update_battery(15)
        self.assertEqual(self.indicator.get_status()["indicator_mode"], "low_battery")
        self.assertEqual(self.indicator.render_frame(0.0), RED)

        self.indicator.update_battery(5)
        self.assertEqual(self.indicator.get_status()["indicator_mode"], "critical_battery")
        self.assertEqual(self.indicator.render_frame(0.0), RED)
        self.assertEqual(self.indicator.render_frame(0.75), OFF)

    def test_leases_are_independent_and_expire(self):
        self.indicator.update_battery(75)
        self.indicator.set_activity("run-a", True, 5)
        self.indicator.set_activity("run-b", True, 10)
        self.clock.now = 6
        self.assertEqual(self.indicator.get_status()["indicator_mode"], "thinking")
        self.indicator.set_activity("run-b", False)
        self.assertEqual(self.indicator.get_status()["indicator_mode"], "battery")

    def test_autonomous_and_transient_event_colors(self):
        self.indicator.update_battery(75, 3.9)
        self.indicator.set_autonomous(True)
        self.assertEqual(self.indicator.get_status()["indicator_mode"], "autonomous")
        self.assertEqual(self.indicator.render_frame(0.9), CYAN)

        self.indicator.signal_event("collision", 3.0)
        self.assertEqual(self.indicator.get_status()["indicator_mode"], "collision")
        self.assertEqual(self.indicator.render_frame(0.4), ORANGE)
        self.clock.now = 3.1
        self.assertEqual(self.indicator.get_status()["indicator_mode"], "autonomous")

    def test_low_battery_overrides_collision_and_autonomy(self):
        self.indicator.update_battery(75, 3.9)
        self.indicator.set_autonomous(True)
        self.indicator.signal_event("collision", 3.0)
        self.indicator.update_battery(15, 3.55)
        self.assertEqual(self.indicator.get_status()["indicator_mode"], "low_battery")

    def test_close_releases_pixels(self):
        self.indicator.close()
        self.assertTrue(self.pixels.closed)
        self.assertFalse(self.indicator.ready)

    def test_transient_initialization_error_is_retried(self):
        recovered_pixels = FakePixels()
        with mock.patch(
            "indicator.NeoSliderPixels",
            side_effect=[OSError("transient"), recovered_pixels],
        ) as pixels_type, mock.patch("indicator.time.sleep") as sleep:
            indicator = IndicatorController(
                FakeBattery(),
                enabled=True,
                autostart=False,
            )

        self.assertTrue(indicator.ready)
        self.assertEqual(pixels_type.call_count, 2)
        sleep.assert_called_once_with(IndicatorController.INIT_RETRY_S)
        indicator.close()


if __name__ == "__main__":
    unittest.main()
