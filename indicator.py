"""NeoSlider status lighting for battery level and LumaKit activity."""

import math
import threading
import time

from i2c_bus import I2C_LOCK


OFF = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
PURPLE = (160, 0, 255)
CYAN = (0, 180, 255)
ORANGE = (255, 80, 0)
YELLOW = (255, 210, 0)
PINK = (255, 40, 140)
LOW_BATTERY_PCT = 15.0
CRITICAL_BATTERY_PCT = 5.0
LOW_BATTERY_V = 3.55
CRITICAL_BATTERY_V = 3.4


def battery_color(percent: float) -> tuple[int, int, int]:
    """Return red at 15% and below; otherwise use a steady green."""
    percent = max(0.0, min(100.0, float(percent)))
    return RED if percent <= LOW_BATTERY_PCT else GREEN


def scale_color(color: tuple[int, int, int], level: float) -> tuple[int, int, int]:
    return tuple(round(channel * level) for channel in color)


class NeoSliderPixels:
    """Small adapter around the NeoSlider's four Seesaw NeoPixels."""

    def __init__(self, address: int = 0x30, brightness: float = 0.25):
        import board
        from adafruit_seesaw import neopixel
        from adafruit_seesaw.seesaw import Seesaw

        self._i2c = board.I2C()
        try:
            with I2C_LOCK:
                seesaw = Seesaw(self._i2c, address)
                self._pixels = neopixel.NeoPixel(
                    seesaw,
                    14,
                    4,
                    pixel_order=neopixel.GRB,
                )
                self._pixels.brightness = brightness
        except Exception:
            self._i2c.deinit()
            raise

    def fill(self, color: tuple[int, int, int]) -> None:
        with I2C_LOCK:
            self._pixels.fill(color)

    def close(self) -> None:
        self.fill(OFF)
        with I2C_LOCK:
            self._i2c.deinit()


class IndicatorController:
    """Own the battery display and renewable LumaKit activity leases."""

    BATTERY_POLL_S = 10.0
    FRAME_S = 0.05
    INIT_ATTEMPTS = 3
    INIT_RETRY_S = 0.25
    STARTUP_PULSE_S = 8.0
    LEASE_MIN_S = 1.0
    LEASE_MAX_S = 30.0

    def __init__(
        self,
        battery,
        *,
        enabled: bool = False,
        pixels=None,
        clock=time.monotonic,
        autostart: bool = True,
        startup_pulse_s: float = STARTUP_PULSE_S,
    ):
        self._battery = battery
        self._clock = clock
        self._enabled = enabled
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread = None
        self._pixels = None
        self._battery_pct = None
        self._battery_voltage_v = None
        self._startup_until = self._clock() + max(0.0, float(startup_pulse_s))
        self._leases: dict[str, float] = {}
        self._events: dict[str, tuple[float, float]] = {}
        self._autonomous = False
        self.ready = False

        if not enabled:
            return
        if pixels is not None:
            self._pixels = pixels
            self.ready = True
        else:
            for attempt in range(1, self.INIT_ATTEMPTS + 1):
                try:
                    self._pixels = NeoSliderPixels()
                    self.ready = True
                    break
                except Exception as error:
                    if attempt == self.INIT_ATTEMPTS:
                        print(f"NeoSlider indicator unavailable: {error}", flush=True)
                    else:
                        time.sleep(self.INIT_RETRY_S)
        if not self.ready:
            return
        if autostart:
            self._thread = threading.Thread(
                target=self._run,
                name="lumabot-indicator",
                daemon=True,
            )
            self._thread.start()

    def update_battery(self, percent, voltage_v=None) -> None:
        if isinstance(percent, bool) or not isinstance(percent, (int, float)):
            return
        with self._lock:
            self._battery_pct = max(0.0, min(100.0, float(percent)))
            if not isinstance(voltage_v, bool) and isinstance(voltage_v, (int, float)):
                self._battery_voltage_v = float(voltage_v)

    def refresh_battery(self) -> None:
        try:
            reading = self._battery.read()
        except Exception:
            return
        self.update_battery(
            reading.get("battery_pct"),
            reading.get("battery_voltage_v"),
        )

    def set_activity(
        self,
        lease_id: str,
        active: bool,
        ttl_s: float = 10.0,
    ) -> dict:
        if not isinstance(lease_id, str) or not lease_id.strip() or len(lease_id) > 128:
            raise ValueError("lease_id must be a non-empty string up to 128 characters")
        if not isinstance(active, bool):
            raise ValueError("active must be true or false")
        if isinstance(ttl_s, bool):
            raise ValueError("ttl_s must be a number")
        ttl_s = float(ttl_s)
        if not self.LEASE_MIN_S <= ttl_s <= self.LEASE_MAX_S:
            raise ValueError("ttl_s must be between 1 and 30 seconds")

        with self._lock:
            if active:
                self._leases[lease_id] = self._clock() + ttl_s
            else:
                self._leases.pop(lease_id, None)
        return self.get_status()

    def set_autonomous(self, active: bool) -> dict:
        if not isinstance(active, bool):
            raise ValueError("active must be true or false")
        with self._lock:
            self._autonomous = active
        return self.get_status()

    def signal_event(self, event: str, duration_s: float) -> dict:
        if event not in {"acknowledgement", "collision", "pet", "tilt"}:
            raise ValueError("unknown indicator event")
        duration_s = float(duration_s)
        if not 0.1 <= duration_s <= 10.0:
            raise ValueError("duration_s must be between 0.1 and 10 seconds")
        now = self._clock()
        with self._lock:
            self._events[event] = (now, now + duration_s)
        return self.get_status()

    def get_status(self) -> dict:
        now = self._clock()
        with self._lock:
            mode = self._mode_unlocked(now)
            return {
                "indicator_ready": self.ready,
                "indicator_mode": mode,
            }

    def _mode_unlocked(self, now: float) -> str:
        self._leases = {
            lease_id: deadline
            for lease_id, deadline in self._leases.items()
            if deadline > now
        }
        self._events = {
            event: timing
            for event, timing in self._events.items()
            if timing[1] > now
        }
        if not self.ready:
            return "unavailable" if self._enabled else "disabled"
        voltage = self._battery_voltage_v
        critical_voltage = voltage is None or voltage <= CRITICAL_BATTERY_V
        low_voltage = voltage is None or voltage <= LOW_BATTERY_V
        if (
            self._battery_pct is not None
            and self._battery_pct <= CRITICAL_BATTERY_PCT
            and critical_voltage
        ):
            return "critical_battery"
        if (
            self._battery_pct is not None
            and self._battery_pct <= LOW_BATTERY_PCT
            and low_voltage
        ):
            return "low_battery"
        if "collision" in self._events:
            return "collision"
        if "tilt" in self._events:
            return "tilt"
        if "acknowledgement" in self._events:
            return "acknowledgement"
        if self._leases:
            return "thinking"
        if "pet" in self._events:
            return "pet"
        if self._autonomous:
            return "autonomous"
        if now < self._startup_until:
            return "startup"
        if self._battery_pct is not None:
            return "battery"
        return "unavailable"

    def render_frame(self, now: float | None = None) -> tuple[int, int, int]:
        now = self._clock() if now is None else now
        with self._lock:
            mode = self._mode_unlocked(now)
            event_started = self._events.get(mode, (now, now))[0]

        if mode == "critical_battery":
            color = RED if now % 1.0 < 0.5 else OFF
        elif mode == "low_battery":
            color = RED
        elif mode == "thinking":
            wave = (math.sin((2.0 * math.pi * now / 1.5) - math.pi / 2.0) + 1.0) / 2.0
            color = scale_color(PURPLE, 0.2 + 0.8 * wave)
        elif mode == "collision":
            wave = (math.sin((2.0 * math.pi * now / 0.8) - math.pi / 2.0) + 1.0) / 2.0
            color = scale_color(ORANGE, 0.2 + 0.8 * wave)
        elif mode == "tilt":
            color = YELLOW if now % 0.4 < 0.2 else OFF
        elif mode == "acknowledgement":
            elapsed = now - event_started
            color = GREEN if elapsed < 0.15 or 0.3 <= elapsed < 0.45 else OFF
        elif mode == "pet":
            wave = (math.sin((2.0 * math.pi * now / 1.0) - math.pi / 2.0) + 1.0) / 2.0
            color = scale_color(PINK, 0.2 + 0.8 * wave)
        elif mode == "autonomous":
            wave = (math.sin((2.0 * math.pi * now / 1.8) - math.pi / 2.0) + 1.0) / 2.0
            color = scale_color(CYAN, 0.35 + 0.65 * wave)
        elif mode == "startup":
            wave = (math.sin((2.0 * math.pi * now / 1.5) - math.pi / 2.0) + 1.0) / 2.0
            color = scale_color(GREEN, 0.2 + 0.8 * wave)
        elif mode == "battery":
            color = GREEN
        else:
            return OFF

        try:
            self._pixels.fill(color)
        except Exception as error:
            with self._lock:
                self.ready = False
            print(f"NeoSlider indicator stopped: {error}", flush=True)
            return OFF
        return color

    def _run(self) -> None:
        next_battery_poll = 0.0
        while not self._stop_event.is_set():
            now = self._clock()
            if now >= next_battery_poll:
                self.refresh_battery()
                next_battery_poll = now + self.BATTERY_POLL_S
            self.render_frame(now)
            self._stop_event.wait(self.FRAME_S)

    def close(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self._pixels is not None:
            try:
                self._pixels.close()
            except Exception as error:
                print(f"NeoSlider cleanup failed: {error}")
        with self._lock:
            self.ready = False
            self._leases.clear()
            self._events.clear()
            self._autonomous = False
