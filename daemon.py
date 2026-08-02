"""Hardware-independent core for the LumaBot daemon."""

from datetime import datetime, timezone
import os
import threading
import time

from autonomy import AutonomyController
from battery import BatteryGauge
from camera import CameraController
from daemon_state import RobotStatus
from distance import DistanceSensor
from indicator import (
    LOW_BATTERY_PCT,
    LOW_BATTERY_V,
    IndicatorController,
)
from motion_sensor import MotionSensor
from motors import MotorController


DIRECTION_VECTORS = {
    "forward": (1.0, 1.0),
    "backward": (-1.0, -1.0),
    "left": (-1.0, 1.0),
    "right": (1.0, -1.0),
}
MAX_LEASE_S = 3.0
CONTROL_INTERVAL_S = 0.01
BATTERY_POLL_S = 10.0
COLLISION_DYNAMIC_G = 1.0
PET_DYNAMIC_G = 0.3
TAP_DYNAMIC_G = 0.35
STOP_TAP_DYNAMIC_G = 1.5
TAP_RELEASE_G = 0.15
DOUBLE_TAP_MIN_S = 0.10
DOUBLE_TAP_MAX_S = 0.70
TILT_STOP_DEGREES = 55.0
TILT_RESET_DEGREES = 45.0


class AutonomyUnavailable(RuntimeError):
    """Raised when a required autonomous-driving subsystem is unavailable."""


class ObstacleSafetyError(RuntimeError):
    """Raised when a forward command cannot be executed safely."""


class LumaBotDaemon:
    def __init__(
        self,
        motors: MotorController | None = None,
        battery: BatteryGauge | None = None,
        indicator: IndicatorController | None = None,
        *,
        camera: CameraController | None = None,
        distance: DistanceSensor | None = None,
        motion: MotionSensor | None = None,
        autonomy: AutonomyController | None = None,
        gestures_enabled: bool | None = None,
        control_autostart: bool = True,
        clock=time.monotonic,
    ):
        self._clock = clock
        self._started_at = clock()
        # stop() returns a fresh status snapshot while it still owns this lock.
        self._lock = threading.RLock()
        enabled = os.getenv("LUMABOT_MOTORS_ENABLED") == "1"
        self.motors = motors or MotorController(enabled=enabled)
        self.motors.coast()
        battery_enabled = os.getenv("LUMABOT_BATTERY_ENABLED") == "1"
        self.battery = battery or BatteryGauge(enabled=battery_enabled)
        camera_enabled = os.getenv("LUMABOT_CAMERA_ENABLED") == "1"
        self.camera = camera or CameraController(enabled=camera_enabled)
        indicator_enabled = os.getenv("LUMABOT_INDICATOR_ENABLED") == "1"
        self.indicator = indicator or IndicatorController(
            self.battery,
            enabled=indicator_enabled,
        )
        distance_enabled = os.getenv("LUMABOT_DISTANCE_ENABLED") == "1"
        motion_enabled = os.getenv("LUMABOT_MOTION_ENABLED") == "1"
        self.distance = distance or DistanceSensor(enabled=distance_enabled)
        self.motion = motion or MotionSensor(enabled=motion_enabled)
        self.autonomy = autonomy or AutonomyController()
        self._gestures_enabled = (
            os.getenv("LUMABOT_GESTURES_ENABLED") == "1"
            if gestures_enabled is None
            else gestures_enabled
        )
        self.status = RobotStatus(
            motors_ready=self.motors.ready,
            camera_ready=self.camera.ready,
            distance_ready=self.distance.ready,
            motion_ready=self.motion.ready,
        )
        self._stop_timer: threading.Timer | None = None
        self._manual_direction = None
        self._stop_event = threading.Event()
        self._control_thread = None
        self._next_battery_poll = 0.0
        self._tap_cooldown_until = 0.0
        self._tap_started_at = None
        self._tap_active = False
        self._hardware_tap_armed = True
        self._pet_cooldown_until = 0.0
        self._tilt_samples = 0

        if control_autostart and (self.distance.ready or self.motion.ready):
            self._control_thread = threading.Thread(
                target=self._run_control,
                name="lumabot-control",
                daemon=True,
            )
            self._control_thread.start()

    def drive(self, direction: str, speed: float, duration_s: float) -> dict:
        if direction not in DIRECTION_VECTORS:
            raise ValueError("direction must be forward, backward, left, or right")
        speed, duration_s = float(speed), float(duration_s)
        if not 0.1 <= speed <= 1.0:
            raise ValueError("speed must be between 0.1 and 1.0")
        if not 0.1 <= duration_s <= MAX_LEASE_S:
            raise ValueError(f"duration_s must be between 0.1 and {MAX_LEASE_S}")

        distance = self.distance.sample(self._clock())
        if direction == "forward":
            if not distance["distance_fresh"]:
                raise ObstacleSafetyError("forward drive blocked: distance reading is unavailable")
            if distance["distance_mm"] <= AutonomyController.STOP_DISTANCE_MM:
                raise ObstacleSafetyError(
                    f"forward drive blocked: obstacle is {distance['distance_mm']} mm away"
                )

        vector = DIRECTION_VECTORS[direction]
        left, right = vector[0] * speed, vector[1] * speed
        with self._lock:
            self._stop_autonomy_unlocked("manual_override")
            if self._stop_timer:
                self._stop_timer.cancel()
            self.motors.set_motors(left, right)
            self.status.left, self.status.right = left, right
            self.status.mode = "manual"
            self.status.brain_state = "manual"
            self.status.obstacle_safety_active = distance["distance_fresh"]
            self._manual_direction = direction
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
            "obstacle_safety_active": distance["distance_fresh"],
        }

    def stop(self) -> dict:
        with self._lock:
            self._stop_motion_unlocked("stop")
        return self.get_status()

    def start_autonomy(self, source: str = "api") -> dict:
        now = self._clock()
        distance = self.distance.sample(now)
        motion = self.motion.sample()
        battery = self._read_battery()
        with self._lock:
            self._apply_distance_unlocked(distance)
            self._apply_motion_unlocked(motion)
            self._apply_battery_unlocked(battery)
            self._start_autonomy_unlocked(source)
        return self.get_status()

    def get_status(self) -> dict:
        battery = self._read_battery()
        with self._lock:
            self._apply_battery_unlocked(battery)
            indicator = self.indicator.get_status()
            self.status.indicator_ready = indicator["indicator_ready"]
            self.status.indicator_mode = indicator["indicator_mode"]
            snapshot = self.status.snapshot()
        snapshot["uptime_s"] = round(self._clock() - self._started_at, 1)
        return snapshot

    def set_indicator_activity(self, lease_id: str, active: bool, ttl_s: float) -> dict:
        return self.indicator.set_activity(lease_id, active, ttl_s)

    def capture_photo(self) -> dict:
        path = self.camera.capture()
        return {"filename": path.name, "path": str(path)}

    def close(self) -> None:
        self._stop_event.set()
        if self._control_thread and self._control_thread.is_alive():
            self._control_thread.join(timeout=1.0)
        with self._lock:
            self._stop_motion_unlocked("shutdown")
        self.distance.close()
        self.motion.close()
        self.indicator.close()

    def _run_control(self) -> None:
        try:
            while not self._stop_event.is_set():
                now = self._clock()
                try:
                    self._control_tick(now)
                except Exception as error:
                    print(f"LumaBot control tick failed: {error}", flush=True)
                    with self._lock:
                        self._stop_motion_unlocked("control_error")
                        self.indicator.signal_event("tilt", 3.0)
                self._stop_event.wait(CONTROL_INTERVAL_S)
        finally:
            with self._lock:
                self._stop_motion_unlocked("control_exit")

    def _control_tick(self, now: float) -> None:
        distance = self.distance.sample(now)
        motion = self.motion.sample()
        battery = self._read_battery() if now >= self._next_battery_poll else None
        if battery is not None:
            self._next_battery_poll = now + BATTERY_POLL_S

        with self._lock:
            self._merge_double_tap_unlocked(motion, now)
            self._apply_distance_unlocked(distance)
            self._apply_motion_unlocked(motion)
            if battery is not None:
                self._apply_battery_unlocked(battery)

            if self._handle_double_tap_unlocked(motion, now):
                return
            if self._handle_tilt_unlocked(motion):
                return
            if self._handle_collision_unlocked(motion, now):
                return
            self._handle_pet_unlocked(motion, now)

            if self.autonomy.active:
                if not self.status.battery_ready:
                    self.status.autonomy_blocked_reason = "battery status became unavailable"
                    self._stop_motion_unlocked("battery_unavailable")
                    return
                if self._battery_is_low_unlocked():
                    self.status.autonomy_blocked_reason = "battery became too low"
                    self._stop_motion_unlocked("low_battery")
                    return
                left, right = self.autonomy.step(
                    distance["distance_mm"],
                    distance["distance_fresh"],
                    now,
                )
                self.status.brain_state = self.autonomy.state
                self.status.mode = "autonomous"
                self.status.obstacle_safety_active = distance["distance_fresh"]
                self._apply_motor_output_unlocked(left, right)
            elif self._manual_direction == "forward" and (
                not distance["distance_fresh"]
                or distance["distance_mm"] <= AutonomyController.STOP_DISTANCE_MM
            ):
                self._stop_motion_unlocked("front_obstacle")

    def _merge_double_tap_unlocked(self, motion: dict, now: float) -> None:
        hardware_tap = motion["double_tap"]
        software_tap = self._detect_double_tap_unlocked(motion, now)
        if self.autonomy.active:
            if hardware_tap:
                self._hardware_tap_armed = False
            motion["double_tap"] = software_tap
            return
        if not hardware_tap:
            self._hardware_tap_armed = True
        accepted_hardware_tap = hardware_tap and self._hardware_tap_armed
        motion["double_tap"] = software_tap or accepted_hardware_tap
        if accepted_hardware_tap:
            self._hardware_tap_armed = False

    def _detect_double_tap_unlocked(self, motion: dict, now: float) -> bool:
        impact = motion["dynamic_acceleration_g"]
        if not isinstance(impact, (int, float)):
            return False
        if impact <= TAP_RELEASE_G:
            self._tap_active = False
            return False
        threshold = STOP_TAP_DYNAMIC_G if self.autonomy.active else TAP_DYNAMIC_G
        if impact < threshold or self._tap_active:
            return False
        self._tap_active = True
        elapsed = None if self._tap_started_at is None else now - self._tap_started_at
        if elapsed is None or not DOUBLE_TAP_MIN_S <= elapsed <= DOUBLE_TAP_MAX_S:
            self._tap_started_at = now
            return False
        self._tap_started_at = None
        return True

    def _handle_double_tap_unlocked(self, motion: dict, now: float) -> bool:
        if (
            not self._gestures_enabled
            or not motion["double_tap"]
            or now < self._tap_cooldown_until
        ):
            return False
        self._tap_cooldown_until = now + 1.2
        self.status.last_gesture = "double_tap"
        if self.autonomy.active:
            self._stop_motion_unlocked("double_tap")
            self.indicator.signal_event("acknowledgement", 0.75)
        else:
            try:
                self._start_autonomy_unlocked("double_tap")
            except AutonomyUnavailable as error:
                self.status.autonomy_blocked_reason = str(error)
                self.indicator.signal_event("tilt", 2.0)
        return True

    def _handle_tilt_unlocked(self, motion: dict) -> bool:
        tilt = motion["tilt_degrees"]
        if not isinstance(tilt, (int, float)):
            self._tilt_samples = 0
            return False
        if tilt >= TILT_STOP_DEGREES:
            self._tilt_samples += 1
        elif tilt <= TILT_RESET_DEGREES:
            self._tilt_samples = 0
        if self._tilt_samples < 3:
            return False
        was_moving = self.status.mode in {"manual", "autonomous"}
        if was_moving:
            self.status.autonomy_blocked_reason = "robot tilted during movement"
            self._stop_motion_unlocked("tilted")
        self.status.last_gesture = "tilt"
        self.indicator.signal_event("tilt", 3.0)
        return was_moving

    def _handle_collision_unlocked(self, motion: dict, now: float) -> bool:
        impact = motion["dynamic_acceleration_g"]
        moving_forward = self.status.left > 0.2 and self.status.right > 0.2
        if (
            not moving_forward
            or motion["double_tap"]
            or not isinstance(impact, (int, float))
            or impact < COLLISION_DYNAMIC_G
        ):
            return False
        self.status.collision_count += 1
        self.status.last_collision_g = round(float(impact), 2)
        self.status.last_collision_at = datetime.now(timezone.utc).isoformat()
        self.indicator.signal_event("collision", 3.0)
        self.motors.coast()
        self.status.left = self.status.right = 0.0
        if self.autonomy.active:
            self.autonomy.trigger_collision(now)
            self.status.brain_state = self.autonomy.state
        else:
            self._stop_motion_unlocked("collision")
        return True

    def _handle_pet_unlocked(self, motion: dict, now: float) -> None:
        impact = motion["dynamic_acceleration_g"]
        if (
            self.status.mode != "idle"
            or motion["double_tap"]
            or now < self._pet_cooldown_until
            or not isinstance(impact, (int, float))
            or not PET_DYNAMIC_G <= impact < COLLISION_DYNAMIC_G
        ):
            return
        self._pet_cooldown_until = now + 2.0
        self.status.last_gesture = "pet"
        self.indicator.signal_event("pet", 1.2)

    def _start_autonomy_unlocked(self, source: str) -> None:
        problem = self._autonomy_problem_unlocked()
        if problem:
            raise AutonomyUnavailable(problem)
        if self._stop_timer:
            self._stop_timer.cancel()
            self._stop_timer = None
        self.motors.coast()
        self._manual_direction = None
        self.autonomy.start()
        self.status.autonomous = True
        self.status.autonomy_source = source
        self.status.autonomy_blocked_reason = None
        self.status.last_stop_reason = None
        self.status.mode = "autonomous"
        self.status.brain_state = self.autonomy.state
        self.status.left = self.status.right = 0.0
        self.indicator.set_autonomous(True)
        self.indicator.signal_event("acknowledgement", 0.75)

    def _autonomy_problem_unlocked(self) -> str | None:
        if not self.motors.ready:
            return "motors are unavailable"
        if not self.status.distance_ready or not self.status.distance_fresh:
            return "fresh distance data is unavailable"
        if not self.status.motion_ready:
            return "MSA311 motion data is unavailable"
        if not self.status.battery_ready:
            return "battery status is unavailable"
        if self._battery_is_low_unlocked():
            return "battery is too low for autonomous driving"
        if self._tilt_samples >= 3:
            return "robot is tilted"
        return None

    def _stop_autonomy_unlocked(self, reason: str) -> None:
        if self.autonomy.active:
            self.autonomy.stop()
        self.status.autonomous = False
        self.status.autonomy_source = None
        self.status.brain_state = "idle"
        self.indicator.set_autonomous(False)

    def _stop_motion_unlocked(self, reason: str) -> None:
        self.status.last_stop_reason = reason
        self.status.last_stop_at = datetime.now(timezone.utc).isoformat()
        if self._stop_timer:
            self._stop_timer.cancel()
            self._stop_timer = None
        self._stop_autonomy_unlocked(reason)
        self._manual_direction = None
        self.motors.coast()
        self.status.left = self.status.right = 0.0
        self.status.mode = "idle"
        self.status.obstacle_safety_active = False

    def _apply_motor_output_unlocked(self, left: float, right: float) -> None:
        if left == 0.0 and right == 0.0:
            self.motors.coast()
        else:
            self.motors.set_motors(left, right)
        self.status.left, self.status.right = left, right

    def _apply_distance_unlocked(self, reading: dict) -> None:
        self.status.distance_ready = reading["distance_ready"]
        self.status.distance_mm = reading["distance_mm"]
        self.status.distance_age_s = reading["distance_age_s"]
        self.status.distance_fresh = reading["distance_fresh"]

    def _apply_motion_unlocked(self, reading: dict) -> None:
        self.status.motion_ready = reading["motion_ready"]
        self.status.acceleration_m_s2 = reading["acceleration_m_s2"]
        self.status.dynamic_acceleration_g = reading["dynamic_acceleration_g"]
        self.status.tilt_degrees = reading["tilt_degrees"]

    def _read_battery(self) -> dict:
        try:
            return self.battery.read()
        except OSError:
            return {"battery_pct": None, "battery_voltage_v": None}

    def _apply_battery_unlocked(self, battery: dict) -> None:
        percent = battery["battery_pct"]
        voltage = battery["battery_voltage_v"]
        self.status.battery_pct = percent
        self.status.battery_voltage_v = voltage
        self.status.battery_ready = percent is not None and voltage is not None
        self.indicator.update_battery(percent, voltage)

    def _battery_is_low_unlocked(self) -> bool:
        percent = self.status.battery_pct
        voltage = self.status.battery_voltage_v
        return (
            isinstance(percent, (int, float))
            and isinstance(voltage, (int, float))
            and percent <= LOW_BATTERY_PCT
            and voltage <= LOW_BATTERY_V
        )
