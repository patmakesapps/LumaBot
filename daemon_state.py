"""Shared status reported by the LumaBot hardware daemon."""

from dataclasses import asdict, dataclass


@dataclass
class RobotStatus:
    distance_mm: int | None = None
    distance_age_s: float | None = None
    distance_ready: bool = False
    distance_fresh: bool = False
    motion_ready: bool = False
    acceleration_m_s2: tuple[float, float, float] | None = None
    dynamic_acceleration_g: float | None = None
    tilt_degrees: float | None = None
    brain_state: str = "idle"
    left: float = 0.0
    right: float = 0.0
    mode: str = "idle"
    autonomous: bool = False
    autonomy_source: str | None = None
    autonomy_blocked_reason: str | None = None
    obstacle_safety_active: bool = False
    collision_count: int = 0
    last_collision_at: str | None = None
    last_collision_g: float | None = None
    last_gesture: str | None = None
    battery_pct: float | None = None
    battery_voltage_v: float | None = None
    battery_ready: bool = False
    indicator_ready: bool = False
    indicator_mode: str = "disabled"
    camera_ready: bool = False
    motors_ready: bool = False

    def snapshot(self) -> dict:
        return asdict(self)
