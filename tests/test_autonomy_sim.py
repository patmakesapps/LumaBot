"""Headless escape regression: the production controller in simulated rooms.

Drives AutonomyController through the shared 2D world model (27-degree
sensor cone, 10 Hz refresh, noise, grazing dropout, slight motor asymmetry)
and requires it to escape trap geometries within a time budget.
"""

import pathlib
import random
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "simulation"))

from autonomy import AutonomyController
from world import World, room_walls

DT = 0.01
TIME_LIMIT_S = 60.0


def base_room():
    return [
        (-1000, -800, 1000, -800),
        (1000, -800, 1000, 800),
        (1000, 800, -1000, 800),
        (-1000, 800, -1000, -800),
    ]


def deep_trap_walls():
    walls = base_room()
    walls.append((300, -120, 900, -120))
    walls.append((900, -120, 900, 120))
    walls.append((900, 120, 300, 120))
    return walls


def run_escape(seed, walls, start, escaped):
    controller = AutonomyController(rng=random.Random(seed))
    controller.start()
    world = World(
        walls=walls, x=start[0], y=start[1], theta=start[2],
        rng=random.Random(seed + 1000),
    )
    prev_collided = False
    while world.time < TIME_LIMIT_S:
        reading = world.distance_mm()
        left, right = controller.step(reading, True, world.time)
        world.step(left, right, DT)
        if world.collided and not prev_collided:
            controller.trigger_collision(world.time)
        prev_collided = world.collided
        if escaped(world):
            return world.time
    return None


class EscapeRegressionTests(unittest.TestCase):
    def assert_escapes(self, walls, start, escaped, seeds=range(5)):
        for seed in seeds:
            escaped_at = run_escape(seed, walls, start, escaped)
            self.assertIsNotNone(
                escaped_at,
                f"seed {seed}: still trapped after {TIME_LIMIT_S:.0f}s",
            )

    def test_escapes_the_shallow_u_trap(self):
        self.assert_escapes(
            room_walls(), (350.0, -100.0, 0.0), lambda w: w.x < 250.0
        )

    def test_escapes_the_deep_narrow_trap(self):
        self.assert_escapes(
            deep_trap_walls(), (400.0, 0.0, 0.0), lambda w: w.x < 250.0
        )


if __name__ == "__main__":
    unittest.main()
