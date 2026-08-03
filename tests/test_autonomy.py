"""Hardware-free checks for autonomous obstacle avoidance."""

import unittest

from autonomy import AutonomyController, BACKUP, CRUISE, SENSOR_WAIT, SWEEP, TURN


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
        self.assertEqual(self.controller.state, BACKUP)

    def test_collision_forces_escalated_backup(self):
        self.controller.step(900, True, 0.0)
        self.controller.trigger_collision(1.0)
        self.assertEqual(self.controller.state, BACKUP)
        self.assertGreaterEqual(self.controller.recovery_level, 1)
        self.assertEqual(self.controller.step(900, True, 1.1), (-0.55, -0.55))

    def test_third_recovery_triggers_sweep_instead_of_random_turn(self):
        for now in (0.0, 2.0, 4.0):
            self.controller.state = CRUISE
            self.controller.step(100, True, now)
        self.assertEqual(self.controller.recovery_level, 2)
        out = self.controller.step(600, True, 4.4)
        self.assertEqual(self.controller.state, SWEEP)
        self.assertEqual(out, (-0.55, 0.55))
        self.assertEqual(len(self.controller._sweep_samples), 1)

    def test_sweep_prefers_sustained_opening_over_phantom_spike(self):
        c = self.controller
        for i in range(400):
            t = i * 0.01
            if 0.8 <= t <= 1.2:
                d = 1400          # a real, sustained opening
            elif 2.0 <= t <= 2.03:
                d = 4000          # brief "no target" phantom from distance.py
            else:
                d = 200
            c._sweep_samples.append((t, d, 0.0))
        offset = c._best_opening_offset()
        self.assertGreaterEqual(offset, 0.85)
        self.assertLessEqual(offset, 1.15)

    def test_sweep_aims_back_toward_best_window(self):
        c = self.controller
        c.state = SWEEP
        c._turn_dir = 1
        c._sweep_started = 0.0
        c._until = c.SWEEP_DURATION_S
        for i in range(400):
            t = i * 0.01
            d = 1200 if 2.8 <= t <= 3.2 else 200
            c._sweep_samples.append((t, d, 0.0))
        out = c.step(200, True, c.SWEEP_DURATION_S)
        self.assertEqual(c.state, TURN)
        self.assertTrue(c._aimed_turn)
        self.assertEqual(c._turn_dir, -1)
        self.assertEqual(out, (-0.55, 0.55))
        backtrack = c._until - c.SWEEP_DURATION_S
        self.assertGreaterEqual(backtrack, 0.8)
        self.assertLessEqual(backtrack, 1.2)

    def test_aimed_turn_trusts_the_sweep_and_creeps_out(self):
        c = self.controller
        c.step(900, True, 0.0)
        c.state = TURN
        c._aimed_turn = True
        c._turn_dir = 1
        c._until = 1.0
        c._turn_hard_deadline = 2.5
        self.assertEqual(c.step(400, True, 1.1), (0.7, 0.7))
        self.assertEqual(c.state, CRUISE)
        self.assertIsNotNone(c._last_aim)
        self.assertEqual(c.step(400, True, 1.2), (0.45, 0.45))

    def test_recently_failed_heading_is_penalized_in_scoring(self):
        c = self.controller
        c._failed_aims = [(0.0, 1.0)]
        for i in range(400):
            t = i * 0.01
            heading = 2.0 * t
            if 0.3 <= t <= 0.7:
                d = 1500          # deepest, but its heading just failed
            elif 2.8 <= t <= 3.2:
                d = 800           # smaller but unblamed opening
            else:
                d = 200
            c._sweep_samples.append((t, d, heading))
        offset = c._best_opening_offset()
        self.assertGreaterEqual(offset, 2.8)
        self.assertLessEqual(offset, 3.2)

    def test_free_cruising_clears_episode_memory(self):
        c = self.controller
        c.step(900, True, 0.0)
        c._failed_aims = [(0.0, 1.0)]
        c.episode_recoveries = 4
        c.step(900, True, 5.1)
        self.assertEqual(c._failed_aims, [])
        self.assertEqual(c.episode_recoveries, 0)


if __name__ == "__main__":
    unittest.main()
