"""Fail-safe autonomous obstacle avoidance for LumaBot."""

from __future__ import annotations

import math
import random


IDLE = "idle"
SENSOR_WAIT = "sensor_wait"
CRUISE = "cruise"
BACKUP = "backup"
TURN = "turn"
SWEEP = "sweep"


class AutonomyController:
    CRUISE_SPEED = 0.70
    APPROACH_SPEED = 0.45
    BACKUP_SPEED = 0.55
    TURN_SPEED = 0.65
    STOP_DISTANCE_MM = 230
    APPROACH_DISTANCE_MM = 500
    CLEAR_DISTANCE_MM = 520
    STUCK_WINDOW_S = 10.0
    SWEEP_RECOVERY_LEVEL = 2
    SWEEP_SPEED = 0.55
    SWEEP_DURATION_S = 4.0
    SWEEP_WINDOW_S = 0.25
    SWEEP_CAP_MM = 1500
    SWEEP_SUSPECT_MM = 3900
    # Rotation rate per unit of throttle differential (right - left), from the
    # N20 free-run estimate: 2 * 234 mm/s / 120 mm track = 3.9 rad/s at full
    # differential. Calibrate on hardware by timing a full pivot.
    TURN_RATE_RAD_S = 1.95
    AIM_BLAME_S = 8.0
    AIM_MEMORY_S = 30.0
    AIM_FAIL_ARC_RAD = 0.7
    AIM_FAIL_PENALTY = 0.4
    SWEEP_BACKUP_S = 0.35
    FREE_CRUISE_RESET_S = 5.0
    BOLD_AFTER_RECOVERIES = 6

    def __init__(self, rng=None):
        self._rng = rng or random.Random()
        self.active = False
        self.state = IDLE
        self._until = 0.0
        self._turn_hard_deadline = 0.0
        self._turn_dir = 1
        self._aimed_turn = False
        self._sweep_started = 0.0
        self._sweep_samples: list[tuple[float, int, float]] = []
        self._avoidance_times: list[float] = []
        self._heading = 0.0
        self._last_now: float | None = None
        self._last_cmd = (0.0, 0.0)
        self._last_aim: tuple[float, float] | None = None
        self._failed_aims: list[tuple[float, float]] = []
        self._cruise_entered_at = 0.0
        self.episode_recoveries = 0
        self.recovery_level = 0

    def start(self) -> None:
        self.active = True
        self.state = SENSOR_WAIT
        self._avoidance_times.clear()
        self._sweep_samples.clear()
        self._failed_aims.clear()
        self._aimed_turn = False
        self._last_aim = None
        self._heading = 0.0
        self._last_now = None
        self._last_cmd = (0.0, 0.0)
        self.episode_recoveries = 0
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
        if self._last_now is not None:
            dt = now - self._last_now
            if 0.0 < dt <= 0.5:
                differential = self._last_cmd[1] - self._last_cmd[0]
                self._heading += differential * self.TURN_RATE_RAD_S * dt
        self._last_now = now
        command = self._decide(distance_mm, distance_fresh, now)
        self._last_cmd = command
        return command

    def _decide(
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
            self._cruise_entered_at = now

        if self.state == CRUISE:
            if now - self._cruise_entered_at >= self.FREE_CRUISE_RESET_S and (
                self._failed_aims or self.episode_recoveries
            ):
                self._failed_aims.clear()
                self.episode_recoveries = 0
            if distance_mm <= self.STOP_DISTANCE_MM:
                self._begin_recovery(now)
                return (0.0, 0.0)
            if distance_mm <= self.APPROACH_DISTANCE_MM:
                return (self.APPROACH_SPEED, self.APPROACH_SPEED)
            return (self.CRUISE_SPEED, self.CRUISE_SPEED)

        if self.state == BACKUP:
            if now < self._until:
                return (-self.BACKUP_SPEED, -self.BACKUP_SPEED)
            want_sweep = (
                self.recovery_level >= self.SWEEP_RECOVERY_LEVEL or self._failed_aims
            )
            bold = (
                self.episode_recoveries >= self.BOLD_AFTER_RECOVERIES
                and self.episode_recoveries % 3 == 0
            )
            if want_sweep and not bold:
                self._begin_sweep(now)
            else:
                self._begin_turn(now)

        if self.state == SWEEP:
            if now < self._until:
                self._sweep_samples.append(
                    (now - self._sweep_started, distance_mm, self._heading)
                )
                return (
                    self.SWEEP_SPEED * self._turn_dir,
                    -self.SWEEP_SPEED * self._turn_dir,
                )
            self._aim_at_best_opening(now)

        if self.state == TURN:
            if now >= self._until and (
                self._aimed_turn or distance_mm >= self.CLEAR_DISTANCE_MM
            ):
                if self._aimed_turn:
                    self._last_aim = (now, self._heading)
                self.state = CRUISE
                self._cruise_entered_at = now
                self._aimed_turn = False
                return (self.CRUISE_SPEED, self.CRUISE_SPEED)
            if now >= self._turn_hard_deadline:
                self._begin_recovery(now, force_escalation=True)
                return (-self.BACKUP_SPEED, -self.BACKUP_SPEED)
            speed = self.SWEEP_SPEED if self._aimed_turn else self.TURN_SPEED
            return (speed * self._turn_dir, -speed * self._turn_dir)

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
        self._failed_aims = [
            (at, heading)
            for at, heading in self._failed_aims
            if now - at <= self.AIM_MEMORY_S
        ]
        if self._last_aim and now - self._last_aim[0] <= self.AIM_BLAME_S:
            self._failed_aims.append((now, self._last_aim[1]))
        self._last_aim = None
        self.episode_recoveries += 1
        inferred_level = min(3, max(0, len(self._avoidance_times) - 1))
        self.recovery_level = max(
            inferred_level,
            min(3, self.recovery_level + 1) if force_escalation else 0,
        )
        self.state = BACKUP
        self._aimed_turn = False
        will_sweep = (
            self.recovery_level >= self.SWEEP_RECOVERY_LEVEL or self._failed_aims
        )
        if will_sweep and not force_escalation:
            self._until = now + self.SWEEP_BACKUP_S
        else:
            self._until = now + 0.65 + 0.2 * self.recovery_level

    def _begin_turn(self, now: float) -> None:
        self.state = TURN
        self._aimed_turn = False
        self._turn_dir = self._rng.choice((-1, 1))
        turn_duration = self._rng.uniform(0.65, 1.15) + 0.25 * self.recovery_level
        self._until = now + turn_duration
        self._turn_hard_deadline = self._until + 1.5

    def _begin_sweep(self, now: float) -> None:
        self.state = SWEEP
        self._turn_dir = self._rng.choice((-1, 1))
        self._sweep_started = now
        self._sweep_samples = []
        self._until = now + self.SWEEP_DURATION_S

    def _aim_at_best_opening(self, now: float) -> None:
        self.state = TURN
        self._aimed_turn = True
        self._turn_dir = -self._turn_dir
        self._until = now + max(0.0, self.SWEEP_DURATION_S - self._best_opening_offset())
        self._turn_hard_deadline = self._until + 1.5

    def _score_sample(self, distance_mm: int) -> int:
        if distance_mm >= self.SWEEP_SUSPECT_MM:
            return self.CLEAR_DISTANCE_MM
        return min(distance_mm, self.SWEEP_CAP_MM)

    def _heading_recently_failed(self, heading: float) -> bool:
        for _, failed in self._failed_aims:
            diff = (heading - failed + math.pi) % (2 * math.pi) - math.pi
            if abs(diff) <= self.AIM_FAIL_ARC_RAD:
                return True
        return False

    def _best_opening_offset(self) -> float:
        samples = self._sweep_samples
        if not samples:
            return self.SWEEP_DURATION_S
        scores = [self._score_sample(d) for _, d, _ in samples]
        best_offset = samples[-1][0]
        best_score = -1
        for start in range(len(samples)):
            t0 = samples[start][0]
            end = start
            while (
                end + 1 < len(samples)
                and samples[end + 1][0] - t0 <= self.SWEEP_WINDOW_S
            ):
                end += 1
            if samples[end][0] - t0 < self.SWEEP_WINDOW_S * 0.8:
                break
            score = min(scores[start : end + 1])
            mid = start + (end - start) // 2
            if self._heading_recently_failed(samples[mid][2]):
                score = int(score * self.AIM_FAIL_PENALTY)
            if score >= best_score:
                best_score = score
                best_offset = t0 + (samples[end][0] - t0) / 2
        return best_offset
