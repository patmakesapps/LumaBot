"""Shared status reported by the LumaBot hardware daemon."""

from dataclasses import asdict, dataclass


@dataclass
class RobotStatus:
    distance_mm: int | None = None
    brain_state: str = "idle"
    left: float = 0.0
    right: float = 0.0
    mode: str = "idle"
    battery_pct: float | None = None
    battery_voltage_v: float | None = None
    battery_ready: bool = False
    indicator_ready: bool = False
    indicator_mode: str = "disabled"
    camera_ready: bool = False
    motors_ready: bool = False

    def snapshot(self) -> dict:
        return asdict(self)
