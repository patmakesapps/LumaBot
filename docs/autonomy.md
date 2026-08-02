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
