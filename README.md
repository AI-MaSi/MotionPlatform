# MotionPlatform

![cockpit](https://github.com/user-attachments/assets/13221f70-b78a-456f-b9c6-6b03398ee156)

This repository contains various scripts to use the Motion Platform system to control the Excavator.

## Joystick Control

`main.py` reads the physical NiDAQ joystick and an optional Xbox-compatible USB gamepad, then merges both inputs before sending the UDP control packet. The larger absolute axis value wins per axis, and button states are ORed together.

Typical dry-run test:

```powershell
python main.py --dry --rate 100
```

Typical robot connection:

```powershell
python main.py --ip 192.168.0.132:8080 --rate 100
```

The NiDAQ and gamepad paths have both been tested to poll well at 100 Hz on Windows with `timeBeginPeriod(1)` enabled by `main.py`. The NiDAQ reader uses a 500 Hz continuous hardware-timed analog task and drains available samples on each poll so the newest sample is used without overflowing the DAQmx buffer.

The gamepad is event-driven in a background thread. A physically connected but idle controller may show as disconnected until it sends an input event; this is acceptable for normal use because `read()` returns neutral values while disconnected.

## NiDAQ to vJoy

`joystick.bat` starts a NiDAQ-to-vJoy bridge from this repo. This requires vJoy and `pyvjoy` to be installed, with vJoy device 1 enabled and configured with the needed axes/buttons. The bridge maps AI0-AI7 to vJoy axes `X`, `Y`, `Z`, `RX`, `RY`, `RZ`, `SL0`, and `SL1`, and maps DI0-DI11 to vJoy buttons 1-12.

Default rate is 100 Hz:

```powershell
.\joystick.bat
```

Override the rate or vJoy device ID if needed:

```powershell
.\joystick.bat --rate 50 --device 1
```
