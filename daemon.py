"""Hardware-independent core for the LumaBot daemon."""

import os
import threading
import time

from battery import BatteryGauge
from daemon_state import RobotStatus
from indicator import IndicatorController
from motors import MotorController


DIRECTION_VECTORS = {
    "forward": (1.0, 1.0),
    "backward": (-1.0, -1.0),
    "left": (-1.0, 1.0),
    "right": (1.0, -1.0),
}
MAX_LEASE_S = 3.0


class LumaBotDaemon:
    def __init__(
        self,
        motors: MotorController | None = None,
        battery: BatteryGauge | None = None,
        indicator: IndicatorController | None = None,
    ):
        self._started_at = time.monotonic()
        # stop() returns a fresh status snapshot while it still owns this lock.
        self._lock = threading.RLock()
        enabled = os.getenv("LUMABOT_MOTORS_ENABLED") == "1"
        self.motors = motors or MotorController(enabled=enabled)
        self.motors.coast()
        battery_enabled = os.getenv("LUMABOT_BATTERY_ENABLED") == "1"
        self.battery = battery or BatteryGauge(enabled=battery_enabled)
        indicator_enabled = os.getenv("LUMABOT_INDICATOR_ENABLED") == "1"
        self.indicator = indicator or IndicatorController(
            self.battery,
            enabled=indicator_enabled,
        )
        self.status = RobotStatus(motors_ready=self.motors.ready)
        self._stop_timer: threading.Timer | None = None

    def drive(self, direction: str, speed: float, duration_s: float) -> dict:
        if direction not in DIRECTION_VECTORS:
            raise ValueError("direction must be forward, backward, left, or right")
        speed, duration_s = float(speed), float(duration_s)
        if not 0.1 <= speed <= 1.0:
            raise ValueError("speed must be between 0.1 and 1.0")
        if not 0.1 <= duration_s <= MAX_LEASE_S:
            raise ValueError(f"duration_s must be between 0.1 and {MAX_LEASE_S}")

        vector = DIRECTION_VECTORS[direction]
        left, right = vector[0] * speed, vector[1] * speed
        with self._lock:
            if self._stop_timer:
                self._stop_timer.cancel()
            self.motors.set_motors(left, right)
            self.status.left, self.status.right = left, right
            self.status.mode = "manual"
            self._stop_timer = threading.Timer(duration_s, self.stop)
            self._stop_timer.daemon = True
            self._stop_timer.start()
        return {
            "direction": direction,
            "speed": speed,
            "duration_s": duration_s,
            "left": left,
            "right": right,
            "watchdog_active": True,
            "obstacle_safety_active": False,
        }

    def stop(self) -> dict:
        with self._lock:
            if self._stop_timer:
                self._stop_timer.cancel()
                self._stop_timer = None
            self.motors.coast()
            self.status.left = self.status.right = 0.0
            self.status.mode = "idle"
        return self.get_status()

    def get_status(self) -> dict:
        with self._lock:
            try:
                battery = self.battery.read()
                self.status.battery_pct = battery["battery_pct"]
                self.status.battery_voltage_v = battery["battery_voltage_v"]
                self.status.battery_ready = battery["battery_pct"] is not None
                self.indicator.update_battery(battery["battery_pct"])
            except OSError:
                self.status.battery_pct = None
                self.status.battery_voltage_v = None
                self.status.battery_ready = False
            indicator = self.indicator.get_status()
            self.status.indicator_ready = indicator["indicator_ready"]
            self.status.indicator_mode = indicator["indicator_mode"]
            snapshot = self.status.snapshot()
        snapshot["uptime_s"] = round(time.monotonic() - self._started_at, 1)
        return snapshot

    def set_indicator_activity(self, lease_id: str, active: bool, ttl_s: float) -> dict:
        return self.indicator.set_activity(lease_id, active, ttl_s)

    def close(self) -> None:
        self.stop()
        self.indicator.close()
