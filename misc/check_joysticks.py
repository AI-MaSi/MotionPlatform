# this script can be used to check channel numbers
import sys
import os
from time import sleep

current_script_path = os.path.abspath(__file__)
parent_directory = os.path.dirname(current_script_path)
grandparent_directory = os.path.dirname(parent_directory)
sys.path.append(grandparent_directory)

import motionplatf_controls

joysticks = motionplatf_controls.DataOutput(simulation_mode=False)




while True:
    values = joysticks.read(combine=True)
    active_channels = [index for index, value in enumerate(values) if abs(value) >= 0.3]
    if len(active_channels) >= 1:
        print(f"Active channel(s): {active_channels}")
    sleep(0.5)