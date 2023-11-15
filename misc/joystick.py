# use Motion Platform joysticks as a game controller.
# uses vJoy

import sys
import os
from time import sleep

current_script_path = os.path.abspath(__file__)
parent_directory = os.path.dirname(current_script_path)
grandparent_directory = os.path.dirname(parent_directory)
sys.path.append(grandparent_directory)

import motionplatf_controls
import pyvjoy

delay = 0.01

# Initialize MotionPlatform
motionplatf_output = motionplatf_controls.DataOutput(simulation_mode=False, decimals=3)


# Initialize the vJoy device
joystick = pyvjoy.VJoyDevice(1)
print("Virtual joystick Initialized! Jee!")
print("")
print("Please Use ctrl + C to quit this")


pyvjoy_axis = [
    pyvjoy.HID_USAGE_X,
    pyvjoy.HID_USAGE_Y,
    pyvjoy.HID_USAGE_Z,
    pyvjoy.HID_USAGE_RX,
    pyvjoy.HID_USAGE_RY,
    pyvjoy.HID_USAGE_RZ,
    pyvjoy.HID_USAGE_SL0,
    pyvjoy.HID_USAGE_SL1
]

try:
    while True:
        stick_values, button_values = motionplatf_output.read(combine=False)

        # joysticks
        for axis_id, value in zip(pyvjoy_axis, stick_values):
            # linear
            scaled_value = int((value + 1) * (32767 / 2))

            joystick.set_axis(axis_id, scaled_value)


        # buttons
        for button_num, state in enumerate(button_values, start=1):
            joystick.set_button(button_num, int(state))

        sleep(delay)
except KeyboardInterrupt:
    print("Cleaning up the mess...")
except Exception as e:
    print(f"An error occured: {e}")

    # Cleanup
    for i in range(1, 9):
        joystick.set_button(i, 0)
    for axis_id in pyvjoy_axis:
        joystick.set_axis(axis_id, 0x4000)

finally:
    print("Cleanup complete, program can now exit.")
