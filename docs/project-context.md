# LumaBot Project Context

Updated July 14, 2026.

## Prototype status — July 30, 2026

- The current repository is <https://github.com/patmakesapps/LumaBot>.
- The Waveshare board was replaced by an Adafruit Motor Bonnet at `0x60`.
- Motor 1 is the left wheel (software-inverted); motor 4 is the right wheel.
- Bench tests confirmed semantic forward motion on both wheels.
- `lumabot.service` runs `server.py` automatically on `127.0.0.1:8971`.
- Its `/drive` endpoint uses leases of at most three seconds and always coasts
  the motors when a lease expires, the service stops, or an error occurs.
- The X1200 fuel gauge at `0x36` reports percentage and voltage through
  `/status`.
- LumaKit calls this local API through LLM-selected structured tools. It can
  schedule a single movement or an ordered sequence without parsing phrases.
- The camera and VL53L1X are not currently connected. Obstacle safety is
  therefore explicitly reported as inactive; all movement testing is on a
  raised-wheel bench.

## Goal

Build a small entertainment-focused differential-drive desk companion that:

- drives with two independently controlled wheels;
- avoids obstacles;
- supports microphone and speaker voice interaction;
- uses a forward-facing Pi NoIR camera;
- eventually has a servo-driven tilt head;
- connects to the LumaKit agent framework; and
- uses cloud LLM APIs over Wi-Fi rather than a local LLM.

The prototype must require no soldering.

## Repositories and Hosts

- Robot: <https://github.com/patmakesapps/LumaBotics>
- Windows checkout: `C:\LumaBot`
- Agent framework: <https://github.com/patmakesapps/LumaKit>
- LumaKit is updated and installed on the Pi 5 in Pat's home folder.
- LumaKit integration is deferred until the physical robot works.

## Current Codebase

- `brain.py`: hardware-independent, reactive, pose-blind three-state controller
  (`cruise`, `backup`, and `turn`). It uses non-blocking deadlines, emits
  normalized left/right speeds from -1 to 1, and randomizes turn direction and
  duration.
- `robot.py`: real 20 Hz sense-decide-act loop using `time.monotonic()`.
  `read_sensor()` and `set_motors()` are the unimplemented hardware seams.
- `simulation/sim.py`: Turtle simulation with differential-drive physics,
  furniture, walls, and a U-shaped trap.
- `simulation/sensor.py`: ray-cast simulated distance sensor with self-tests.
- `docs/notes.txt`: simulation tuning notes.

Completed learning chunks: differential-drive physics, ray-cast sensing, the
brain/state machine and full simulation, simulation/hardware separation, and
Git repository setup/refactoring.

## Hardware

Already owned:

- Raspberry Pi 5, Pi NoIR camera, and Pi 5-compatible 22-pin camera ribbon.
- Pi fans/heatsinks, USB-C supply, and microSD card.
- Pi configured on the network.

Ordered:

- Three Acxico N20 3-6 V gear motors with wired leads, 3 mm D-shafts, and
  approximately 104 RPM. Use two; keep one spare.
- 65 mm K346 rubber wheels with 3 mm D-holes, expected July 28-August 4.
- MECCANIXITY N20 brackets with screws.
- Four MARRTEUM ball-bearing casters. Use one rear caster; keep three spares.
- Waveshare PCA9685 + TB6612FNG I2C Motor Driver HAT with two DC outputs.
- Pi 5 WM8960 Audio HAT with dual MEMS microphones and two included 8 ohm,
  5 W speakers. The HAT supplies approximately 1 W per channel.
- CQRobot VL53L1X time-of-flight sensor.
- Geekworm X1200 UPS HAT and two Samsung 35E flat-top unprotected 18650 cells.
- Extra-tall 2x20 stacking headers and female-to-female/male-to-female Dupont
  jumpers.
- Four SG90 servos.
- 4xAA 6 V battery holders with covers, bare leads, and switches.
- Four alkaline AA cells are required for motor testing.

Do not suggest additional purchases until testing demonstrates a need.

## Electrical Architecture

### X1200

- Mount below the Pi using pogo pins.
- The two 18650 cells are parallel, not a 7.4 V series pack.
- It supplies approximately 5.1 V/5 A to the Pi.
- Power and charge only through the X1200 USB-C port.
- Never power the Pi USB-C port while the X1200 is installed.
- Expected battery-gauge I2C address: `0x36`.

### Motor Driver HAT

- Mount separately on the chassis; do not stack it on the Pi.
- Official VIN range is 6-12 V. For the prototype, use four alkaline AA cells
  in series for 6 V.
- Battery red connects to VIN positive. Battery black connects to VIN
  negative/GND.
- Connect the Pi to the powered HAT using only GND, SDA, and SCL.
- Never connect the Motor HAT 5 V pin to the Pi. Its regulator could backfeed
  the independently powered Pi/X1200.
- Channel A drives the left motor; channel B drives the right motor.
- Verify the PCA9685 IN1/IN2 channel mapping from the physical board and
  official example before implementing it.
- Correct reversed wheels with software inversion flags instead of repeatedly
  changing motor wiring.
- No servo channels are exposed, so motor PWM can run independently, potentially
  near 1 kHz.

### Servo

- Drive the SG90 signal from an unused Pi GPIO.
- Do not use GPIO18-GPIO21; the WM8960 uses them for I2S.
- Servo red connects to regulated 5 V, brown to ground, and orange/yellow to the
  selected GPIO signal.
- All power-system grounds must be common.
- The Motor HAT 5 V output may power the servo from the AA pack, but verify the
  physical header before wiring.
- Male-to-female jumpers can break the SG90 female connector into separate
  signal, power, and ground connections.

### Expected I2C Addresses

- `0x1A`: WM8960 audio codec.
- `0x29`: VL53L1X sensor.
- `0x36`: X1200 battery gauge.
- `0x40`: Motor HAT PCA9685.
- `0x70`: possible PCA9685 all-call address.

I2C fan-out remains a physical question. Inspect whether the extra-tall header
leaves usable pins around or above the WM8960. Do not buy a splitter
preemptively. Removing the audio HAT during initial driving tests is acceptable.

## Mechanical Architecture

- Use two driven wheels and one rear caster. Three contact points prevent
  rocking and keep both drive wheels loaded; do not install all four casters.
- Wait for the actual motors, brackets, wheels, caster, and electronics before
  finalizing mounting holes.
- First print a simple functional flat chassis, approximately 140 x 110 mm,
  before designing the polished shell.
- Add adjustable/slotted bracket holes, zip-tie slots, ventilation, and one
  X1200 USB-C charging cutout.
- Keep the batteries and heavy electronics low and centered.
- Do not purchase a generic robot chassis.
- Fix the camera forward for v1 at approximately 10-15 degrees downward.
- Install the camera ribbon before the audio HAT obstructs access.
- Later add tilt only. Avoid pan because repeated ribbon twisting is undesirable.

## Bring-Up Order

1. Verify Raspberry Pi OS, kernel, SSH, and I2C. Record `uname -a`. Test the
   camera before installing HATs.
2. Install the X1200 below the Pi, carefully seat its pogo pins, insert correctly
   oriented cells, power through X1200 USB-C, confirm a stable boot, and look for
   I2C address `0x36`.
3. Check fan/heatsink and WM8960 clearance. Install the audio HAT with the tall
   header, look for `0x1A`, install the kernel-appropriate driver, then test
   speakers, microphones, and first TTS output.
4. Connect the VL53L1X, remove its protective film, look for `0x29`, and
   implement `read_sensor()` as a small guided chunk.
5. Connect Motor HAT GND/SDA/SCL with motors and AA power disconnected. Verify
   I2C detection.
6. Connect the AA holder to VIN without connecting HAT 5 V to the Pi. Keep
   wheels off the ground, test one motor at a time, verify channel mapping,
   direction, and emergency stop behavior, then implement `set_motors()` as a
   small guided chunk.
7. Connect and test one SG90 using GPIO signal, regulated 5 V, and common ground.
8. Print the measured basic chassis and test driving, turning, and avoidance.
9. Wrap proven speak/listen/move/measure capabilities as LumaKit agent tools.

The immediate next stage is the main hardware delivery around July 19, followed
by audio/X1200/camera bring-up one component at a time. Wheels arrive later, so
motor bench testing can happen first. Always resume from Pat's reported state.

## Known Gotchas

- The WM8960 driver may require kernel-specific fixes.
- A basic USB audio dongle cannot drive the included unpowered 8 ohm speakers;
  fallback audio would require amplification or a powered USB speaker/speakerphone.
- Start voice interaction half-duplex: stop listening during TTS playback.
- N20 leads are thin; strain-relieve them without stressing motor tabs.
- One forward VL53L1X can miss corners and side obstacles; this is accepted for
  v1.
- The NoIR camera has unusual daylight colors and needs infrared illumination
  to see in darkness.
- Dupont wiring is suitable for prototyping, not a commercial product.
- Measure Pi temperature under load.

Library
/
LumaBot_Project_Main_Summary_Updated_2026-07-20.txt


LumaBot Project — Fully Updated Context

Current as of July 20, 2026

I also updated the saved project memory with tonight’s final readings and stopping point.

1. Working style

Pat is a software developer and Blender user building his first physical robot.

For future sessions:

Work in small, testable chunks of roughly 10–20 lines.
Explain every line of code and every hardware connection.
Pat runs and tests each step before continuing.
Do not dump a finished program all at once.
Do not recommend additional purchases unless testing proves they are needed.
Resume from the exact physical and software state Pat reports.
2. Project goal

Build a small, entertainment-focused differential-drive desk companion robot that:

Drives using two independently controlled wheels.
Avoids obstacles.
Supports microphone and speaker voice interaction.
Uses a forward-facing Raspberry Pi NoIR camera.
Eventually uses a servo-driven tilt head.
Connects to Pat’s LumaKit agent framework after the physical robot is working.
Uses cloud LLM APIs over Wi-Fi rather than running an LLM locally.
Requires no soldering during the prototype stage.
3. Repositories
Robot repository
https://github.com/patmakesapps/LumaBotics
Windows location
C:\LumaBot
Agent framework
https://github.com/patmakesapps/LumaKit

LumaKit is already installed on the Raspberry Pi, but integration is deliberately deferred until the robot’s physical systems work.

4. Current codebase
LumaBotics/
├── brain.py
├── robot.py
├── docs/
│   └── notes.txt
└── simulation/
    ├── sim.py
    └── sensor.py
brain.py

Hardware-independent three-state robot controller:

cruise
backup
turn

Current behavior:

Non-blocking deadline pattern.
No sleep() calls inside the controller.
Reactive and pose-blind.
Produces normalized left/right motor speeds from -1.0 to 1.0.
Randomizes turn direction.
Randomizes turn duration.
robot.py

Real hardware loop running at approximately 20 Hz:

sense → decide → act

Uses:

time.monotonic()

Current unfinished hardware seams:

read_sensor()
set_motors()

Both currently raise:

NotImplementedError
simulation/sim.py

Turtle-based simulation containing:

Differential-drive physics.
Furniture.
Walls.
U-shaped obstacle trap.
Simulated robot movement.
simulation/sensor.py

Contains:

Ray-cast simulated distance sensor.
Sensor self-tests.
5. Completed learning and software work
Differential-drive physics.
Ray-cast distance sensing.
Robot state-machine design.
Full simulated obstacle avoidance.
Separation of simulation and real hardware code.
Repository setup.
Git refactoring.
Hardware-independent robot brain.
Non-blocking control patterns.
6. Full parts list
Main computer and camera
Raspberry Pi 5.
Raspberry Pi NoIR camera.
Raspberry Pi 5-compatible 22-pin camera ribbon.
Raspberry Pi fan/heatsink setup.
Raspberry Pi USB-C power supply.
microSD card.
Pi already configured on the network and accessible through SSH.
Motors and movement
3× Acxico N20 gear motors
3–6 V.
Wired leads.
3 mm D-shaft.
Approximately 104 RPM.
Two for the robot.
One spare.
65 mm K346 rubber wheels
3 mm D-shaped holes.
MECCANIXITY N20 motor brackets
Includes mounting screws.
MARRTEUM ball-bearing casters
Four-pack.
Use only one rear caster initially.
Remaining three are spares.
Motor control
Waveshare Motor Driver HAT
PCA9685 PWM controller.
TB6612FNG motor driver.
I²C controlled.
Two DC motor outputs.
Audio
WM8960 Audio HAT for Raspberry Pi 5
Dual MEMS microphones.
Two included 8 Ω, 5 W speakers.
HAT amplifier output is approximately 1 W per channel.
Distance sensing
CQRobot VL53L1X time-of-flight sensor
Battery and power
Geekworm X1200 UPS HAT
2× Samsung 35E 18650 cells
Flat top.
Unprotected.
Raspberry Pi/X1200 USB-C charger.
Wiring and headers
Extra-tall 2×20 stacking headers.
Female-to-female Dupont jumper wires.
Male-to-female Dupont jumper wires.
Servo hardware
4× SG90 micro servos
Motor battery supply
4×AA battery holders.
Covers.
Bare leads.
Integrated switches.
Four alkaline AA batteries for prototype motor testing.
Fabrication
3D printer arriving July 20, 2026.
Filament and related printer supplies were selected separately.
Final robot chassis will be designed after measuring the physical components.
7. Electrical architecture
X1200 UPS

The X1200:

Mounts beneath the Raspberry Pi 5.
Uses pogo pins to contact pads beneath the Pi.
Holds two 18650 cells.
Powers the Pi at approximately 5.1 V.
Supports up to approximately 5 A output.
Must be charged and powered through the X1200 USB-C input.
The Pi’s own USB-C port must not be powered while the X1200 is installed.
Exposes its fuel gauge over I²C at address 0x36. Geekworm documents the X1200 as a bottom-mounted Pi 5 UPS with a 5.1 V / 5 A output and an I²C fuel-gauge system.

The two installed cells operate as one parallel battery pack in this project architecture, so the measured pack voltage is similar to a single 18650 cell rather than a two-cell series voltage.

Motor Driver HAT

The Motor Driver HAT will be mounted separately on the chassis rather than stacked directly on the Pi.

Prototype wiring:

Pi GND  → Motor HAT GND
Pi SDA  → Motor HAT SDA
Pi SCL  → Motor HAT SCL

Do not connect:

Motor HAT 5V → Pi 5V

Reason: the Pi and Motor HAT have independent power systems, and connecting their regulated 5 V rails could cause backfeeding.

Motor power:

4× alkaline AA cells ≈ 6 V

Battery-holder wiring:

Red   → VIN+
Black → VIN-/GND

Planned motor mapping:

Channel A → left motor
Channel B → right motor

Exact PCA9685 PWM-channel-to-TB6612 input mapping must be verified against the physical board and official example before implementing set_motors().

Reversed motor direction should be corrected through software inversion flags rather than repeatedly swapping wires.

SG90 servo

The Motor Driver HAT does not expose convenient servo sockets.

Planned servo wiring:

Brown          → Ground
Red            → Regulated 5 V
Orange/Yellow  → Raspberry Pi GPIO signal

Avoid GPIO18 through GPIO21 because they are expected to be used by the WM8960 Audio HAT for I²S.

All electrical systems must share a common ground when connected.

8. Expected I²C devices
0x1A → WM8960 audio codec
0x29 → VL53L1X distance sensor
0x36 → X1200 battery fuel gauge
0x40 → Motor HAT PCA9685
0x70 → Possible PCA9685 all-call address

Current confirmed devices:

0x29 → VL53L1X distance sensor
0x36 → X1200 battery fuel gauge
9. Mechanical architecture

Initial configuration:

Two driven wheels.
One rear caster.
Three ground-contact points total.

Do not install all four casters. Three points prevent rocking and help keep both powered wheels in contact with the ground.

Initial chassis:

Simple flat functional test chassis.
Approximate starting size: 140 × 110 mm.
Final dimensions depend on physical measurements.

Planned features:

Adjustable or slotted motor-bracket holes.
Zip-tie slots.
Ventilation.
X1200 USB-C charging cutout.
Low, centered battery and electronics placement.
No generic purchased robot chassis.

Camera:

Fixed forward-facing for version 1.
Approximately 10–15° downward tilt.
Install the camera ribbon before upper HATs make access difficult.
Later create a tilt-only camera/head mechanism.
Avoid pan because repeatedly twisting the camera ribbon could damage it.
10. Hardware progress completed tonight
Raspberry Pi preparation
Removed the Pi 5 from its original case.
Removed the old black underside standoffs.
Removed the ElectroCookie right-angle GPIO attachment.
X1200 battery installation
Installed both Samsung 35E 18650 batteries.
Confirmed correct polarity.
Mounted the X1200 beneath the Raspberry Pi.
Initial failure

The first mounting orientation was incorrect.

Observed behavior:

X1200 charging LEDs worked.
Battery LEDs worked.
5V0 appeared briefly.
PI5 remained off.
Power shut down after approximately three seconds.

Geekworm documents that the X1200 shuts itself down after roughly three seconds when it does not correctly detect the Pi through the pogo-pin interface.

Pi isolation test
Disconnected the X1200.
Confirmed the Raspberry Pi still booted normally by itself.
This showed the Pi had not been damaged.
Orientation correction
Identified that the X1200 was installed in the wrong orientation.
Rotated the board.
Realigned:
Mounting holes.
Pogo pins.
Ports.
Buttons.
Successfully booted the Raspberry Pi from the X1200.
Charger verification

Confirmed:

Charger → X1200 USB-C

Not:

Charger → Raspberry Pi USB-C
11. I²C troubleshooting completed

Initially:

sudo i2cdetect -y 1

failed because:

/dev/i2c-1

did not exist.

I²C was then enabled with:

dtparam=i2c_arm=on

Verified state:

i2c-1 exists
GPIO2 = SDA1
GPIO3 = SCL1

However, the initial scans were still empty.

The following tests all initially failed to find the X1200:

sudo i2cdetect -y 1
sudo i2cdetect -y -r 1
sudo i2ctransfer -y 1 w1@0x36 0x02 r2

The direct read returned:

Remote I/O error

This proved:

Pi I²C was enabled.
The bus existed.
GPIO2 and GPIO3 were configured correctly.
Nothing was acknowledging at 0x36.

The physical stack was then shut down, realigned and remounted.

Final scan:

sudo i2cdetect -y 1

returned:

30: -- -- -- -- -- -- 36 -- -- -- -- -- -- -- -- --

This confirms that the earlier failure was caused by pogo-pin alignment/contact. Geekworm specifically identifies pogo-pin contact beneath physical GPIO pins 3 and 5 as the likely cause when 0x36 is missing.

12. Raspberry Pi true-shutdown configuration

Originally, running:

sudo poweroff

halted Linux but left the Pi/X1200 stack electrically powered by the batteries.

The Raspberry Pi EEPROM was updated with:

POWER_OFF_ON_HALT=1
WAKE_ON_GPIO=0

The EEPROM update completed with:

VERIFY: SUCCESS
UPDATE SUCCESSFUL

After rebooting, sudo poweroff now:

Disconnects SSH.
Stops the Pi fan.
Turns off the Pi LEDs.
Cuts power from the X1200.
Allows the boards to be handled safely.

Geekworm’s documentation specifically recommends enabling POWER_OFF_ON_HALT=1 for full power-off behavior with the X1200.

13. Final successful battery readings
Voltage register

Command:

sudo i2ctransfer -y 1 w1@0x36 0x02 r2

Result:

0xc5 0x70

Calculation:

Combined value: 0xC570
12-bit reading: 0xC570 >> 4 = 3159
3159 × 1.25 mV = 3948.75 mV

Final battery voltage:

approximately 3.95 V

The MAX17040’s VCELL register is located at 0x02–0x03, and its single-cell voltage resolution is 1.25 mV.

State-of-charge register

Command:

sudo i2ctransfer -y 1 w1@0x36 0x04 r2

Result:

0x19 0xad

Calculation:

Integer portion: 0x19 = 25
Fractional portion: 0xAD / 256 ≈ 0.676

Final reported battery level:

approximately 25.7%

The MAX17040 SOC register uses the high byte as the whole percentage and the low byte as fractional resolution in units of 1/256%.

Because the batteries and gauge were recently installed and power-cycled, the reported percentage may settle as the fuel-gauge model observes charging and discharging. The chip initially estimates SOC from cell voltage and converges over time.

14. Current confirmed system state
Working
Raspberry Pi boots from X1200 battery power.
Raspberry Pi boots while X1200 wall power is connected.
Charger is connected to the correct X1200 USB-C port.
Both Samsung 35E cells are installed correctly.
X1200 pogo-pin alignment is correct.
I²C bus 1 is active.
X1200 appears at 0x36.
Battery voltage and state of charge can be read.
Full software-controlled power-off works.
The Raspberry Pi itself is healthy.
SSH works.
Existing robot simulation and state-machine code remain intact.
The Raspberry Pi NoIR camera is connected to the final Pi/X1200 stack.
rpicam-hello --list-cameras detects the camera as imx708_noir with a maximum resolution of 4608 × 2592.
rpicam-still successfully captured noir-test.jpg.
The CQRobot VL53L1X distance sensor is physically connected to the Raspberry Pi.
The Raspberry Pi successfully powers up with the final corrected distance-sensor wiring.
A final sudo i2cdetect -y 1 scan confirmed both active I²C devices simultaneously:
0x29 → VL53L1X distance sensor
0x36 → X1200 battery fuel gauge
A project virtual environment now exists at ~/LumaBotics/repo/.venv.
The adafruit-circuitpython-vl53l1x package version 1.2.9 and required Blinka dependencies installed successfully.
sensor_test.py produced the first live distance measurements.
A controlled hand test stabilized around 20 cm, with readings gradually changing from approximately 24.0 cm to 19.3 cm as the hand moved closer.
None readings occur when the sensor does not receive a valid reflection and are handled as no reading.
robot.py now initializes the real VL53L1X, starts continuous ranging, converts centimeters to millimeters, applies a bounded wait for fresh data, handles None safely and stops ranging cleanly on exit.
The existing Brain now receives real distance measurements through the full sense → decide → motor-command-preview loop.
Observed state transitions matched the intended logic: cruise, hard stop, backup, turn and return to cruise.
set_motors() remains intentionally disabled with pass, so no physical motor command has been sent yet.

Final confirmed VL53L1X prototype wiring
Sensor VCC, red/orange wire → Raspberry Pi physical pin 1, 3.3 V.
Sensor SDA, green/teal wire → Raspberry Pi physical pin 3, GPIO2/SDA1.
Sensor SCL, blue/purple wire → Raspberry Pi physical pin 5, GPIO3/SCL1.
Physical pin 7 is intentionally left empty.
Sensor GND, black wire → Raspberry Pi physical pin 9, GND.
Sensor SHUT, yellow wire → disconnected for the first test.
Sensor INT, tan/brown wire → disconnected for the first test.
All four connected wires are on the odd-numbered GPIO row closest to the large black heatsink.
Viewed from the right end of the header, the order is red, green, blue, empty, black on pins 1, 3, 5, 7 and 9.

Important wiring lesson
An earlier photo angle caused the ground connection to be misidentified and the black lead was briefly placed on the wrong pin. The Pi did not boot normally in that configuration. The sensor leads were removed, the Pi was tested by itself, and it booted normally, confirming that the Pi was not damaged. The sensor was then rewired correctly using physical pin 9 for ground.

Still to verify or implement
Motor Driver HAT I²C-only connection and address detection.
Confirm 0x40 and possibly 0x70 while leaving Motor HAT 5 V and VIN disconnected.
Verify the physical Motor HAT PCA9685-to-TB6612 channel mapping.
Connect and test the N20 motors one at a time with wheels off the ground.
Implement emergency-stop behavior and set_motors().
WM8960 Audio HAT.
Speakers.
Microphones.
Wheels.
Rear caster.
SG90 servo.
Printed chassis.
LumaKit integration.

15. Updated bring-up order
Completed
Stage 0 — Pi foundation
Raspberry Pi OS, network and SSH configured.
I²C enabled.
Pi boots normally.

Stage 1 — X1200 power subsystem
Batteries installed.
Correct board orientation and pogo-pin alignment.
Stable battery-powered boot.
Charger connected correctly.
0x36 detected.
Voltage read successfully.
Battery percentage read successfully.
Full shutdown configured.

Stage 2A — Pi NoIR camera
Camera ribbon connected before installing upper HATs.
IMX708 NoIR detected successfully.
Full-resolution still image captured successfully.
Camera is considered brought up for the prototype stage.
A printed camera case and final cable routing can wait until the robot dimensions are established.

Stage 3A — VL53L1X physical connection
Sensor pin labels and cable colors identified.
VCC, SDA, SCL and GND connected correctly.
SHUT and INT left disconnected.
Pi booted successfully with the sensor connected.

Stage 3B — VL53L1X software verification
Final I²C scan confirmed 0x29 and 0x36 simultaneously.
Project .venv created and the Adafruit VL53L1X library installed.
First live distance readings completed successfully.
Controlled hand test produced stable readings around 20 cm.
read_sensor() implemented in robot.py with centimeter-to-millimeter conversion and None handling.
Real sensor data successfully connected to the existing sense → decide → act-command-preview loop.
Brain transitions through cruise, backup and turn were verified without energizing any motors.

Next
Stage 4 — Motor HAT logic
Power the Pi down before changing wiring.
Connect only GND, SDA and SCL between the Pi and Motor HAT.
Leave Motor HAT 5 V and motor battery VIN disconnected.
Boot the Pi and run sudo i2cdetect -y 1.
Confirm 0x29, 0x36 and 0x40; 0x70 may also appear.
Verify the physical board’s PCA9685-to-TB6612 channel mapping before writing set_motors().

Stage 2B — Audio bring-up
Check WM8960 physical clearance with the X1200 stack.
Install the WM8960 using the tall header.
Scan for 0x1A.
Install the correct WM8960 driver for the current kernel.
Test speaker output.
Test microphone input.
Produce the robot’s first TTS output.

Stage 5 — Motors
Connect the 4×AA battery holder to Motor HAT VIN.
Keep wheels off the ground.
Test one motor at a time.
Verify direction and channel mapping.
Implement emergency-stop behavior.
Implement set_motors().

Stage 6 — Servo
Test one SG90.
Use an external regulated 5 V supply and common ground.
Use a GPIO that does not conflict with the WM8960 I²S pins.

Stage 7 — Chassis
Measure the physical electronics, motors, wheels, brackets and caster with calipers.
Model the flat functional chassis.
Print a functional prototype.
Mount motors, wheels, electronics and one rear caster.
Perform first driving tests.

Stage 8 — Agent integration
Wrap the functioning capabilities as LumaKit tools:
speak
listen
move
stop
measure_distance
capture_image
read_battery

16. GPIO safety reference for this build
Do not change GPIO jumper wiring while the Pi is running.
Use physical pin numbers rather than guessing from wire position or color.
For the VL53L1X prototype connection, use 3.3 V on physical pin 1, never the adjacent 5 V pin 2.
The I²C data and clock pins are physical pins 3 and 5.
Ground is physical pin 9 in the final wiring layout used tonight.
Leave physical pin 7 empty so the ground connection is visually separated from SCL.
Keep SHUT and INT disconnected until software requires them.

17. Next-session starting point
The X1200 power subsystem, Pi NoIR camera and VL53L1X distance-sensing subsystem are fully brought up for the prototype stage.
The final I²C scan shows 0x29 and 0x36 simultaneously.
Live distance measurements are stable and robot.py now feeds real millimeter readings into Brain.
The complete sense → decide → motor-command-preview path is verified.
Physical motor output remains disabled because set_motors() still contains pass.

Start with the Motor Driver HAT logic test:

1. Shut down the Raspberry Pi completely.
2. Connect only Pi GND → Motor HAT GND, Pi SDA → Motor HAT SDA and Pi SCL → Motor HAT SCL.
3. Do not connect Motor HAT 5 V to Pi 5 V.
4. Leave the 4×AA motor battery and Motor HAT VIN disconnected.
5. Boot the Pi and run sudo i2cdetect -y 1.
6. Confirm 0x29, 0x36 and 0x40; 0x70 may also appear.
7. Do not connect motors or implement set_motors() until the Motor HAT address and channel mapping are verified.

Camera-case and chassis design can continue after the relevant physical components are measured.
