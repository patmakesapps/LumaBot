# world.py — shared 2D room model for LumaBot simulations and tests.
import math
import random

from sensor import ray_cast

MAXV = 234.0            # wheel surface speed at full throttle, mm/s
TRACK = 120.0           # distance between wheels, mm
SENSOR_PERIOD_S = 0.1   # VL53L1X long-mode timing budget: new reading every 100 ms
NO_TARGET_MM = 4000     # the daemon reports "no target" as a synthetic 4000 mm
CONE_RAD = math.radians(27.0)  # VL53L1X field of view
CONE_RAYS = 7           # rays sampled across the cone; reading = nearest hit
MOTOR_ASYM = 1.03       # left motor runs slightly fast, so timed turns drift


def room_walls():
    """The familiar 2m x 1.6m room from sim.py: furniture plus the U-trap."""
    walls = [
        (-1000, -800, 1000, -800),
        (1000, -800, 1000, 800),
        (1000, 800, -1000, 800),
        (-1000, 800, -1000, -800),
    ]

    def add_box(x, y, w, h):
        walls.append((x, y, x + w, y))
        walls.append((x + w, y, x + w, y + h))
        walls.append((x + w, y + h, x, y + h))
        walls.append((x, y + h, x, y))

    add_box(200, 100, 400, 250)        # couch
    add_box(-700, -500, 300, 200)      # coffee table
    add_box(-100, 400, 150, 300)       # bookshelf
    walls.append((300, -300, 700, -300))   # U-trap, bottom arm
    walls.append((700, -300, 700, 100))    # U-trap, back wall
    walls.append((700, 100, 300, 100))     # U-trap, top arm (mouth opens left)
    return walls


class World:
    """Differential-drive robot with a forward ToF beam that refreshes at 10 Hz.

    The sensor models the VL53L1X's ~27 degree cone as a fan of rays and
    reports the nearest hit, so a gap only reads "clear" when the whole cone
    fits through it — matching how the real part behaves near door frames and
    corners. Rays that strike a wall at a grazing angle can lose their return
    (the daemon then reports a phantom 4000 mm, mirroring distance.py), and
    every reading carries gaussian noise. Walls block translation: a move that
    would cross a wall leaves the robot in place and sets `collided`, which a
    harness can feed to AutonomyController.trigger_collision like the MSA311.
    """

    def __init__(self, walls=None, x=0.0, y=0.0, theta=0.0, rng=None):
        self.walls = room_walls() if walls is None else walls
        self.x, self.y, self.theta = x, y, theta
        self.rng = rng or random.Random(0)
        self.time = 0.0
        self.collided = False
        self._last_sample_at = -SENSOR_PERIOD_S
        self._last_sample = NO_TARGET_MM

    def step(self, left, right, dt):
        vl, vr = left * MAXV * MOTOR_ASYM, right * MAXV
        v = (vl + vr) / 2
        omega = (vr - vl) / TRACK
        self.theta += omega * dt
        nx = self.x + v * math.cos(self.theta) * dt
        ny = self.y + v * math.sin(self.theta) * dt
        self.collided = self._crosses_wall(self.x, self.y, nx, ny)
        if not self.collided:
            self.x, self.y = nx, ny
        self.time += dt

    def distance_mm(self):
        """Forward beam reading, held between 10 Hz refreshes like the daemon sees."""
        if self.time - self._last_sample_at >= SENSOR_PERIOD_S:
            reading = None
            for i in range(CONE_RAYS):
                angle = self.theta + CONE_RAD * (i / (CONE_RAYS - 1) - 0.5)
                best_d, best_wall = None, None
                for wall in self.walls:
                    d = ray_cast(self.x, self.y, angle, wall)
                    if d is not None and (best_d is None or d < best_d):
                        best_d, best_wall = d, wall
                if best_d is None or self._ray_drops_out(angle, best_wall):
                    continue
                if reading is None or best_d < reading:
                    reading = best_d
            if reading is None:
                self._last_sample = NO_TARGET_MM
            else:
                reading += self.rng.gauss(0.0, 15.0 + 0.01 * reading)
                self._last_sample = int(min(max(reading, 20.0), NO_TARGET_MM))
            self._last_sample_at = self.time
        return self._last_sample

    def _ray_drops_out(self, angle, wall):
        """Grazing incidence on a wall often returns no signal on the real part."""
        x1, y1, x2, y2 = wall
        wall_angle = math.atan2(y2 - y1, x2 - x1)
        grazing = abs(math.sin(angle - wall_angle))  # 0 = parallel to the wall
        if grazing < math.sin(math.radians(20)):
            return self.rng.random() < 0.7
        if grazing < math.sin(math.radians(35)):
            return self.rng.random() < 0.3
        return self.rng.random() < 0.02

    def _crosses_wall(self, ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy)
        if length < 1e-6:
            return False
        heading = math.atan2(dy, dx)
        for wall in self.walls:
            t = ray_cast(ax, ay, heading, wall)
            if t is not None and t <= length:
                return True
        return False
