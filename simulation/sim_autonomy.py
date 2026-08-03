# sim_autonomy.py — watch the production AutonomyController drive the room.
#
# Unlike sim.py (which runs the legacy tutorial Brain), this drives the real
# autonomy.py controller through the shared world model: 27-degree sensor
# cone, 10 Hz refresh, noise, grazing dropout, slight motor asymmetry.
# The robot starts inside the U-trap so you can watch a sweep escape.
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import math
import turtle

from world import World
from autonomy import AutonomyController

SCALE = 0.25

screen = turtle.Screen()
screen.setup(700, 550)
screen.title("lumabot sim — production autonomy")
screen.tracer(0)

world = World(x=350.0, y=-100.0, theta=0.0)   # inside the U-trap, facing in

pen = turtle.Turtle(); pen.hideturtle(); pen.penup()
for (x1, y1, x2, y2) in world.walls:
    pen.goto(x1 * SCALE, y1 * SCALE); pen.pendown()
    pen.goto(x2 * SCALE, y2 * SCALE); pen.penup()

bot = turtle.Turtle()
bot.shape("turtle")

controller = AutonomyController()
controller.start()

dt = 0.01
prev_collided = False
for i in range(12000):                        # 120 simulated seconds
    reading = world.distance_mm()
    left, right = controller.step(reading, True, world.time)
    world.step(left, right, dt)
    if world.collided and not prev_collided:
        controller.trigger_collision(world.time)
    prev_collided = world.collided
    if i % 5 == 0:
        bot.goto(world.x * SCALE, world.y * SCALE)
        bot.setheading(math.degrees(world.theta))
        screen.title(
            f"lumabot sim   {controller.state}   sensor: {reading} mm"
        )
        screen.update()

turtle.done()
