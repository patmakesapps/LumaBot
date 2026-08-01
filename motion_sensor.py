"""MSA311 gesture, tilt, and impact measurements for LumaBot."""

from __future__ import annotations

import math
import threading

from i2c_bus import I2C_LOCK


STANDARD_GRAVITY = 9.806


class MotionSensor:
    GRAVITY_ALPHA = 0.95

    def __init__(self, enabled: bool = False, *, device=None, i2c=None):
        self._lock = threading.Lock()
        self._device = device
        self._i2c = i2c
        self._owns_i2c = False
        self._gravity = None
        self._reference = None
        self.ready = device is not None

        if not enabled or self.ready:
            if self.ready:
                self._enable_double_tap()
            return
        try:
            import adafruit_msa3xx
            import board

            with I2C_LOCK:
                self._i2c = board.I2C()
                self._owns_i2c = True
                self._device = adafruit_msa3xx.MSA311(self._i2c)
                self._device.enable_tap_detection(
                    tap_count=2,
                    threshold=25,
                    double_tap_window=adafruit_msa3xx.TapDuration.DURATION_700_MS,
                )
            self.ready = True
        except Exception as error:
            print(f"MSA311 unavailable: {error}", flush=True)
            self._cleanup_i2c()

    def _enable_double_tap(self) -> None:
        with I2C_LOCK:
            self._device.enable_tap_detection(
                tap_count=2,
                threshold=25,
                double_tap_window=7,
            )

    def sample(self) -> dict:
        with self._lock:
            if not self.ready:
                return self._empty_reading()
            try:
                with I2C_LOCK:
                    acceleration = tuple(float(value) for value in self._device.acceleration)
                    double_tap = bool(self._device.tapped)
            except Exception as error:
                print(f"MSA311 read failed: {error}", flush=True)
                return self._empty_reading()

            if self._gravity is None:
                self._gravity = acceleration
                self._reference = acceleration
            dynamic = tuple(
                current - gravity
                for current, gravity in zip(acceleration, self._gravity)
            )
            self._gravity = tuple(
                self.GRAVITY_ALPHA * gravity
                + (1.0 - self.GRAVITY_ALPHA) * current
                for current, gravity in zip(acceleration, self._gravity)
            )
            magnitude_g = self._magnitude(acceleration) / STANDARD_GRAVITY
            dynamic_g = self._magnitude(dynamic) / STANDARD_GRAVITY
            tilt_degrees = self._angle_degrees(acceleration, self._reference)
            return {
                "motion_ready": True,
                "acceleration_m_s2": tuple(round(value, 3) for value in acceleration),
                "acceleration_g": round(magnitude_g, 3),
                "dynamic_acceleration_g": round(dynamic_g, 3),
                "tilt_degrees": round(tilt_degrees, 1),
                "double_tap": double_tap,
            }

    @staticmethod
    def _magnitude(vector) -> float:
        return math.sqrt(sum(value * value for value in vector))

    @classmethod
    def _angle_degrees(cls, first, second) -> float:
        denominator = cls._magnitude(first) * cls._magnitude(second)
        if denominator == 0:
            return 0.0
        cosine = sum(a * b for a, b in zip(first, second)) / denominator
        return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))

    @staticmethod
    def _empty_reading() -> dict:
        return {
            "motion_ready": False,
            "acceleration_m_s2": None,
            "acceleration_g": None,
            "dynamic_acceleration_g": None,
            "tilt_degrees": None,
            "double_tap": False,
        }

    def close(self) -> None:
        with self._lock:
            self.ready = False
            self._cleanup_i2c()

    def _cleanup_i2c(self) -> None:
        if self._owns_i2c and self._i2c is not None:
            try:
                with I2C_LOCK:
                    self._i2c.deinit()
            except Exception:
                pass
        self._i2c = None
        self._owns_i2c = False
