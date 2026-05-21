"""
Main robot control — NiDAQ joystick version.

Reads joystick axes and buttons from NiDAQ, sends over UDP to robot.

UDP output (10 signed bytes):
    [0] button_0      (0 or 127)   ← DI9  (left top red button)
    [1] button_1      (0 or 127)   ← DI0  (right rocker U/D)
    [2] button_2      (0 or 127)   ← DI1
    [3] button_3      (0 or 127)   ← DI3  (unknown — needs mapping)
    [4] LeftPaddle    (-128..127)  ← AI7
    [5] RightPaddle   (-128..127)  ← AI6
    [6] LeftJoyY      (-128..127)  ← AI4  (left_ud)
    [7] LeftJoyX      (-128..127)  ← AI3  (left_lr)
    [8] RightJoyY     (-128..127)  ← AI1  (right_ud, inverted)
    [9] RightJoyX     (-128..127)  ← AI0  (right_lr)

Usage:
    python main.py
"""

from modules.NiDAQ_controller import NiDAQJoysticks, OutputFormat
from modules.udp_socket import UDPSocket
import time


TX_RATE_HZ = 100
TX_PERIOD = 1.0 / TX_RATE_HZ

joy = NiDAQJoysticks(output_format=OutputFormat.INT8, deadzone=1.5, padding=2.5)
client = UDPSocket(local_id=1, max_age_seconds=0.5)
client.setup(host="192.168.0.132", port=8080, num_inputs=0, num_outputs=10, is_server=False)

if client.handshake(timeout=30.0):

    next_time = time.monotonic()
    while True:
        data = joy.read()

        right_lr = data.ai[0]
        right_ud = -data.ai[1]
        right_rocker = data.ai[2]
        left_lr = data.ai[3]
        left_ud = data.ai[4]
        left_rocker = data.ai[5]
        right_paddle = data.ai[6]
        left_paddle = data.ai[7]

        button_0 = data.di[9]   # left top red button
        button_1 = data.di[0]   # right rocker U/D
        button_2 = data.di[1]
        button_3 = data.di[3]   # figure out what this button is haha

        success = client.send([button_0, button_1, button_2, button_3,
                     left_paddle, right_paddle,
                     left_ud, left_lr,
                     right_ud, right_lr
                     ])

        if not success:
            break

        next_time += TX_PERIOD
        sleep_for = next_time - time.monotonic()
        if sleep_for > 0:
            time.sleep(sleep_for)
        else:
            next_time = time.monotonic()
