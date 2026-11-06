# MotionPlatform

![cockpit](https://github.com/user-attachments/assets/13221f70-b78a-456f-b9c6-6b03398ee156)

This repository contains various scripts to use the Motion Platform system to control the Excavator.

## Video / joystick datasets

`record_dataset.py` records **30 FPS video and 60 Hz NI-DAQ axes**, using the
existing `modules/NiDAQ_controller.py`. It only reads inputs; it sends no robot commands.
Stop other NI-DAQ readers before running it.

```powershell
python -m pip install -r requirements-collection.txt
python record_dataset.py --view --pose front
```

If using the environment prepared here:

```powershell
.\.venv-collection\Scripts\python.exe record_dataset.py --view --pose front
```

The camera preview stays live while paused. **DI3 toggles recording/pause** (release
then press; 50 ms debounce). **Ctrl+C saves and exits.** Starts paused. Use
`--button-active-low` if DI3 reads zero when pressed. `--view` is optional.
For another camera pose, restart with e.g. `--pose side`.

Each run creates a unique folder under `datasets/`:

- `video.avi`: 640×480 MJPEG at 30 FPS; recorded sections concatenated.
- `frames.csv`: exact video frame index, section number, delivery and write timestamps.
- `axes.csv`: every hardware sample, raw volts, normalized axes without deadzone,
  digital buttons, and read timing. Axes continue logging during pauses.
- `labels.csv`: axes interpolated per frame; `valid=0` means unavailable sample coverage.
- `metadata.json` and `timing.json`: settings, cadence, queue/encoding delays, errors.

All timestamps use the same monotonic clock in nanoseconds. Use `frames.csv` to
recover elapsed time across pauses; AVI playback omits pauses. The recorder stops
on queue overflow instead of silently dropping video frames. `timing.json` flags
inadequate camera cadence. Actual camera exposure latency is **not** measured by
timing a blocking read. DAQ sample times are estimated from task start and the
actual hardware clock rate; USB transport delay and first-sample phase remain
uncertain until a movement calibration. Initial labels are provisional even when
their sample coverage is valid.

For a timing benchmark (no button needed):

```powershell
python record_dataset.py --auto-start --seconds 10 --pose benchmark
```

For the alignment demo, keep one joystick visible and move one axis with several
irregular starts, stops, and reversals for 15–20 seconds. Avoid a repeating rhythm.
DI3 starts/pauses the clip; Ctrl+C finishes it. After measuring the offset, labels
can be regenerated without recording again:

```powershell
python record_dataset.py --relabel datasets/SESSION --camera-latency-ms 40
```

Here `40` is only an example: positive offsets select earlier joystick samples.
Measure it for the actual camera/settings. Alignment remains unverified until
checked against movement. `--camera`, `--backend msmf`, `--width`, and `--height`
are available if needed; defaults request 640×480 at 30 FPS.

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

The NiDAQ and gamepad paths have both been tested to poll well at 100 Hz on Windows with `timeBeginPeriod(1)` enabled by `main.py`. `--rate` is passed directly to the NiDAQ analog hardware sample rate, and the blocking NiDAQ read is used as the sender loop clock.

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
