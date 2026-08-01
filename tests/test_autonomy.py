"""Hardware-free checks for autonomous obstacle avoidance."""

import unittest

from autonomy import AutonomyController, BACKUP, CRUISE, SENSOR_WAIT, TURN


class FakeRandom:
    def choice(self, values):
        return values[0]

    def uniform(self, low, high):
        return low


class AutonomyTests(unittest.TestCase):
    def setUp(self):
        self.controller = AutonomyController(rng=FakeRandom())
        self.controller.start()

    def test_cruise_is_lively_and_only_slows_near_an_obstacle(self):
        self.assertEqual(self.controller.step(900, True, 0.0), (0.7, 0.7))
        self.assertEqual(self.controller.state, CRUISE)
        self.assertEqual(self.controller.step(400, True, 0.1), (0.45, 0.45))

    def test_close_obstacle_stops_backs_up_and_turns(self):
        self.assertEqual(self.controller.step(200, True, 0.0), (0.0, 0.0))
        self.assertEqual(self.controller.state, BACKUP)
        self.assertEqual(self.controller.step(200, True, 0.1), (-0.55, -0.55))
        self.assertEqual(self.controller.step(200, True, 0.7), (-0.65, 0.65))
        self.assertEqual(self.controller.state, TURN)
        self.assertEqual(self.controller.step(700, True, 1.4), (0.7, 0.7))

    def test_missing_reading_always_stops_motion(self):
        self.controller.step(900, True, 0.0)
        self.assertEqual(self.controller.step(None, False, 0.1), (0.0, 0.0))
        self.assertEqual(self.controller.state, SENSOR_WAIT)
        self.assertEqual(self.controller.step(900, True, 0.2), (0.7, 0.7))

    def test_repeated_obstacles_escalate_recovery(self):
        for now in (0.0, 2.0, 4.0):
            self.controller.state = CRUISE
            self.controller.step(100, True, now)
        self.assertEqual(self.controller.recovery_level, 2)
        self.assertGreater(self.controller._until, 5.0)

    def test_collision_forces_escalated_backup(self):
        self.controller.step(900, True, 0.0)
        self.controller.trigger_collision(1.0)
        self.assertEqual(self.controller.state, BACKUP)
        self.assertGreaterEqual(self.controller.recovery_level, 1)
        self.assertEqual(self.controller.step(900, True, 1.1), (-0.55, -0.55))


if __name__ == "__main__":
    unittest.main()
