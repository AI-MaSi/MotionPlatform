"""
NiDAQ to vJoy bridge.

Requires vJoy and pyvjoy. Maps AI0-AI7 to vJoy axes and DI0-DI11 to
vJoy buttons 1-12.
"""

import argparse
import ctypes
from pathlib import Path
import sys
import time

import pyvjoy
from pyvjoy import _sdk

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from modules.NiDAQ_controller import NiDAQJoysticks, OutputFormat


VJOY_DEVICE_ID = 1
VJOY_AXIS_MIN = 0
VJOY_AXIS_MAX = 0x8000
VJOY_AXIS_CENTER = (VJOY_AXIS_MIN + VJOY_AXIS_MAX) // 2

AXES = [
    ("wAxisX", pyvjoy.HID_USAGE_X),
    ("wAxisY", pyvjoy.HID_USAGE_Y),
    ("wAxisZ", pyvjoy.HID_USAGE_Z),
    ("wAxisXRot", pyvjoy.HID_USAGE_RX),
    ("wAxisYRot", pyvjoy.HID_USAGE_RY),
    ("wAxisZRot", pyvjoy.HID_USAGE_RZ),
    ("wSlider", pyvjoy.HID_USAGE_SL0),
    ("wDial", pyvjoy.HID_USAGE_SL1),
]


def _axis_to_vjoy(value):
    value = max(-128, min(127, int(value)))
    normalized = (value + 128) / 255.0
    return int(round(VJOY_AXIS_MIN + normalized * (VJOY_AXIS_MAX - VJOY_AXIS_MIN)))


def _button_mask(values):
    mask = 0
    for index, value in enumerate(values[:12]):
        if value > 0:
            mask |= 1 << index
    return mask


def _update_vjoy(device, data):
    report = _sdk.CreateDataStructure(device.rID)
    for (axis_name, _), value in zip(AXES, data.ai):
        setattr(report, axis_name, _axis_to_vjoy(value))
    report.lButtons = _button_mask(data.di)
    if _sdk.UpdateVJD(device.rID, report):
        return

    for (_, axis_id), value in zip(AXES, data.ai):
        device.set_axis(axis_id, _axis_to_vjoy(value))
    for button in range(1, 13):
        device.set_button(button, 1 if data.di[button - 1] > 0 else 0)


def _reset_vjoy(device):
    report = _sdk.CreateDataStructure(device.rID)
    for axis_name, _ in AXES:
        setattr(report, axis_name, VJOY_AXIS_CENTER)
    report.lButtons = 0
    if _sdk.UpdateVJD(device.rID, report):
        return

    for _, axis_id in AXES:
        device.set_axis(axis_id, VJOY_AXIS_CENTER)
    for button in range(1, 13):
        device.set_button(button, 0)


def _test_axes(device):
    from collections import namedtuple

    data_type = namedtuple("JoystickData", ["ai", "di"])
    neutral = [0] * 8
    buttons = [0] * 12
    print("Stepping vJoy axes through min/center/max. Watch vJoy Monitor for X/Y/Z/RX/RY/RZ/SL0/SL1.")
    for index, (axis_name, _) in enumerate(AXES):
        print(f"Testing axis {index}: {axis_name}")
        values = neutral.copy()
        for value in (-128, 0, 127, 0):
            values[index] = value
            _update_vjoy(device, data_type(ai=values, di=buttons))
            time.sleep(0.75)
    _reset_vjoy(device)


def main():
    parser = argparse.ArgumentParser(description="Map NiDAQ joystick inputs to vJoy")
    parser.add_argument("--rate", type=int, default=100, help="poll rate in Hz (default: 100)")
    parser.add_argument("--device", type=int, default=VJOY_DEVICE_ID, help="vJoy device ID (default: 1)")
    parser.add_argument("--test-axes", action="store_true", help="step each vJoy axis through min/center/max without reading NiDAQ")
    args = parser.parse_args()

    if args.rate <= 0:
        parser.error("--rate must be positive")

    winmm = None
    if sys.platform == "win32":
        winmm = ctypes.WinDLL("winmm")
        winmm.timeBeginPeriod(1)

    joy = None
    vjoy = None
    try:
        print(f"Opening vJoy device {args.device}...")
        vjoy = pyvjoy.VJoyDevice(args.device)
        _reset_vjoy(vjoy)
        if args.test_axes:
            _test_axes(vjoy)
            return

        print("Initializing NiDAQ joystick...")
        joy = NiDAQJoysticks(
            output_format=OutputFormat.INT8,
            deadzone=1.5,
            padding=2.5,
            sample_rate=args.rate,
        )

        print(f"NiDAQ to vJoy at {args.rate} Hz - Ctrl+C to stop")
        while True:
            data = joy.read()

            _update_vjoy(vjoy, data)
    except KeyboardInterrupt:
        pass
    finally:
        if vjoy:
            _reset_vjoy(vjoy)
        if joy:
            joy.close()
        if winmm:
            winmm.timeEndPeriod(1)
        print("\nStopped")


if __name__ == "__main__":
    main()
