# Autonomous driving

The hardware daemon owns autonomous driving so obstacle safety does not depend
on Wi-Fi, an LLM response, or LumaKit remaining connected.

## Controls

- Double-tap the MSA311 to start autonomous driving.
- Double-tap firmly again, call `POST /stop`, issue a manual drive command, or
  use LumaKit's STOP action to cancel it.
- LumaKit can start autonomy with its owner-only, approval-gated
  `lumabot_start_autonomy` tool.

Autonomy starts only when the motors, VL53L1X, MSA311, battery, and tilt checks
are ready. A missing or stale distance reading always produces zero motor
output. Service shutdown and control-loop errors always coast both motors.
The VL53L1X uses long-distance mode with a 100 ms timing budget so open indoor
space remains measurable while the stale-reading safety stop stays active.

## Driving behavior

- Clear floor: 70% forward throttle.
- 230–500 mm obstacle distance: 45% forward approach.
- 230 mm or nearer: coast immediately, reverse at 55%, then turn at 65%.
- Repeated obstacles within ten seconds increase reverse and turn time.
- A turn does not return to cruise until the sensor sees at least 520 mm of
  clearance.

## Corner escape (sweep-and-commit)

When the robot keeps hitting obstacles (a third recovery inside ten seconds,
or an escalated collision), it stops guessing and scans instead:

1. **Sweep**: pivot in place at 55% for four seconds while recording the
   distance profile — the robot uses its own rotation as a poor man's lidar.
2. **Score**: find the direction with the most *sustained* clearance using a
   0.25 s sliding window. Readings at 3900 mm or more are treated as the
   daemon's synthetic "no target" value and scored as barely-clear rather
   than open floor, so a glass door or dark sofa cannot lure the robot.
3. **Commit**: rotate back to the best direction (time-symmetric backtrack at
   the same pivot speed, so no heading sensor is needed) and drive out. The
   aimed exit trusts the sweep: if the chosen direction reads under 520 mm
   the robot still creeps toward it at approach speed, because in tight
   pockets the best available exit is often below the open-floor threshold.

The controller also keeps a short episode memory. It integrates commanded
wheel differential into a rough heading estimate (`TURN_RATE_RAD_S`, worth
calibrating with a timed pivot on hardware), and directions whose aimed
escape immediately led to another recovery are penalized for 30 seconds so
the robot stops re-trying the deepest-looking dead end. Five seconds of free
cruising clears the memory. If an episode drags past six recoveries, every
third recovery falls back to an old-style random turn so the robot never
mills in place indefinitely; `episode_recoveries` exposes how stuck it is,
which is the intended trigger for asking LumaKit's camera brain for help.

Escape behavior is regression-tested headlessly in `tests/test_autonomy_sim.py`
against `simulation/world.py`, which models the VL53L1X's 27-degree cone,
10 Hz refresh, gaussian noise, grazing-angle dropout, and slight motor
asymmetry. Watch it live with `python simulation/sim_autonomy.py`.

A single forward-facing distance sensor cannot see behind or beside the robot.
The first physical test must therefore use a clear floor with a reachable STOP
control and no stairs, table edges, pets, feet, or fragile objects nearby.

## MSA311 safety and gestures

- Three consecutive readings at 55 degrees or more stop motion and show a
  yellow warning.
- A forward impact of at least 1.0 g of dynamic acceleration coasts the motors,
  records the collision, pulses orange for three seconds, and triggers a more
  assertive autonomous recovery.
- A gentle idle jolt of 0.3–1.0 g produces the pink pet response.
- Double-tap detection uses the MSA311 hardware with a 700 ms tap window and a
  threshold of 25. Tune the threshold only after observing real chassis taps.

## NeoSlider modes

Safety has priority over personality:

1. critical/low battery red;
2. collision orange;
3. tilt/safety warning yellow;
4. double-tap acknowledgement green flashes;
5. LumaKit thinking purple;
6. pet response pink;
7. autonomous driving cyan;
8. startup pulse or healthy battery green.
