"""Fail-safe autonomous obstacle avoidance for LumaBot."""

from __future__ import annotations

import random


IDLE = "idle"
SENSOR_WAIT = "sensor_wait"
CRUISE = "cruise"
BACKUP = "backup"
TURN = "turn"


class AutonomyController:
    CRUISE_SPEED = 0.70
    APPROACH_SPEED = 0.45
    BACKUP_SPEED = 0.55
    TURN_SPEED = 0.65
    STOP_DISTANCE_MM = 230
    APPROACH_DISTANCE_MM = 500
    CLEAR_DISTANCE_MM = 520
    STUCK_WINDOW_S = 10.0

    def __init__(self, rng=None):
        self._rng = rng or random.Random()
        self.active = False
        self.state = IDLE
        self._until = 0.0
        self._turn_hard_deadline = 0.0
        self._turn_dir = 1
        self._last_turn_dir = 1
        self._avoidance_times: list[float] = []
        self.recovery_level = 0

    def start(self) -> None:
        self.active = True
        self.state = SENSOR_WAIT
        self._avoidance_times.clear()
        self.recovery_level = 0

    def stop(self) -> None:
        self.active = False
        self.state = IDLE
        self.recovery_level = 0

    def step(
        self,
        distance_mm: int | None,
        distance_fresh: bool,
        now: float,
    ) -> tuple[float, float]:
        if not self.active:
            self.state = IDLE
            return (0.0, 0.0)
        if not distance_fresh or distance_mm is None:
            self.state = SENSOR_WAIT
            return (0.0, 0.0)
        if self.state in {IDLE, SENSOR_WAIT}:
            self.state = CRUISE

        if self.state == CRUISE:
            if distance_mm <= self.STOP_DISTANCE_MM:
                self._begin_recovery(now)
                return (0.0, 0.0)
            if distance_mm <= self.APPROACH_DISTANCE_MM:
                return (self.APPROACH_SPEED, self.APPROACH_SPEED)
            return (self.CRUISE_SPEED, self.CRUISE_SPEED)

        if self.state == BACKUP:
            if now < self._until:
                return (-self.BACKUP_SPEED, -self.BACKUP_SPEED)
            self._begin_turn(now)

        if self.state == TURN:
            if now >= self._until and distance_mm >= self.CLEAR_DISTANCE_MM:
                self.state = CRUISE
                return (self.CRUISE_SPEED, self.CRUISE_SPEED)
            if now >= self._turn_hard_deadline:
                self._begin_recovery(now, force_escalation=True)
                return (-self.BACKUP_SPEED, -self.BACKUP_SPEED)
            return (
                self.TURN_SPEED * self._turn_dir,
                -self.TURN_SPEED * self._turn_dir,
            )

        self.state = SENSOR_WAIT
        return (0.0, 0.0)

    def trigger_collision(self, now: float) -> None:
        if self.active:
            self._begin_recovery(now, force_escalation=True)

    def _begin_recovery(self, now: float, force_escalation: bool = False) -> None:
        self._avoidance_times = [
            occurred_at
            for occurred_at in self._avoidance_times
            if now - occurred_at <= self.STUCK_WINDOW_S
        ]
        self._avoidance_times.append(now)
        inferred_level = min(3, max(0, len(self._avoidance_times) - 1))
        self.recovery_level = max(
            inferred_level,
            min(3, self.recovery_level + 1) if force_escalation else 0,
        )
        self.state = BACKUP
        self._until = now + 0.65 + 0.2 * self.recovery_level

    def _begin_turn(self, now: float) -> None:
        self.state = TURN
        if self.recovery_level >= 2:
            self._turn_dir = -self._last_turn_dir
        else:
            self._turn_dir = self._rng.choice((-1, 1))
        self._last_turn_dir = self._turn_dir
        turn_duration = self._rng.uniform(0.65, 1.15) + 0.25 * self.recovery_level
        self._until = now + turn_duration
        self._turn_hard_deadline = self._until + 1.5
