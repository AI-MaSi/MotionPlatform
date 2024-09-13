# this script can be used to check channel numbers
# script prints out channel number when used
import sys
import os
from time import sleep

from control_modules.NiDAQ_controller import NiDAQJoysticks

THRESHOLD = 0.2 # Threshold for active channel detection

current_script_path = os.path.abspath(__file__)
parent_directory = os.path.dirname(current_script_path)
grandparent_directory = os.path.dirname(parent_directory)
sys.path.append(grandparent_directory)

joysticks = NiDAQJoysticks(simulation_mode=True)

while True:
    values = joysticks.read()
    active_channels = [f"{index} ({value:.2f})" for index, value in enumerate(values) if abs(value) >= THRESHOLD]
    if active_channels:
        print(f"Active channel(s): {active_channels}")
    sleep(0.1)