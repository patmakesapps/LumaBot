"""Hardware-free checks for NeoSlider status lighting."""

import unittest
from unittest import mock

from indicator import IndicatorController, OFF, PURPLE, RED, battery_color


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
        )

    def tearDown(self):
        self.indicator.close()

    def test_battery_gradient_reaches_red_at_fifteen_percent(self):
        self.assertEqual(battery_color(100), (0, 255, 0))
        self.assertEqual(battery_color(57.5), (255, 255, 0))
        self.assertEqual(battery_color(15), RED)
        self.assertEqual(battery_color(0), RED)

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
