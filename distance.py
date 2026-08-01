"""Non-blocking VL53L1X distance readings for the hardware daemon."""

from __future__ import annotations

import threading
import time

from i2c_bus import I2C_LOCK


class DistanceSensor:
    STALE_S = 0.35

    def __init__(
        self,
        enabled: bool = False,
        *,
        address: int = 0x29,
        device=None,
        i2c=None,
        clock=time.monotonic,
    ):
        self._clock = clock
        self._lock = threading.Lock()
        self._device = device
        self._i2c = i2c
        self._owns_i2c = False
        self._distance_mm = None
        self._measured_at = None
        self.ready = device is not None

        if not enabled or self.ready:
            if self.ready:
                self._start_device()
            return
        try:
            import adafruit_vl53l1x
            import board

            with I2C_LOCK:
                self._i2c = board.I2C()
                self._owns_i2c = True
                self._device = adafruit_vl53l1x.VL53L1X(self._i2c, address=address)
                self._start_device()
            self.ready = True
        except Exception as error:
            print(f"VL53L1X unavailable: {error}", flush=True)
            self._cleanup_i2c()

    def _start_device(self) -> None:
        # Long mode keeps open indoor space measurable; short mode can report
        # no valid range beyond roughly 1.36 m, which would correctly but
        # unnecessarily trip the daemon's stale-reading safety stop.
        self._device.distance_mode = 2
        self._device.timing_budget = 100
        self._device.start_ranging()

    def sample(self, now: float | None = None) -> dict:
        now = self._clock() if now is None else now
        with self._lock:
            if self.ready:
                try:
                    with I2C_LOCK:
                        if self._device.data_ready:
                            distance_cm = self._device.distance
                            self._device.clear_interrupt()
                            if distance_cm is not None:
                                self._distance_mm = int(round(float(distance_cm) * 10.0))
                                self._measured_at = now
                except Exception as error:
                    print(f"VL53L1X read failed: {error}", flush=True)

            age = None if self._measured_at is None else max(0.0, now - self._measured_at)
            return {
                "distance_ready": self.ready,
                "distance_mm": self._distance_mm,
                "distance_age_s": None if age is None else round(age, 3),
                "distance_fresh": age is not None and age <= self.STALE_S,
            }

    def close(self) -> None:
        with self._lock:
            if self._device is not None:
                try:
                    with I2C_LOCK:
                        self._device.stop_ranging()
                except Exception as error:
                    print(f"VL53L1X cleanup failed: {error}", flush=True)
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
