"""
Robot control — NiDAQ joystick + optional USB gamepad.

Primary:  NiDAQ physical joystick (AI0–AI7 axes, DI0–DI11 buttons)
Optional: USB gamepad (Xbox/compatible) — larger absolute value wins per axis

UDP output: 8 × int8 axes + 1 × uint16 button bitmask  ('< 8bH')
    Axes sent raw (no inversions) — configure on the robot/server side.

Usage:
    python main.py --ip 192.168.0.132:8080
    python main.py --ip 192.168.0.132:8080 --id 2 --debug
    python main.py --dry
"""

import argparse
import time

from modules.NiDAQ_controller import NiDAQJoysticks, OutputFormat
from modules.udp_socket import UDPSocket
from modules.gamepad_module import XboxController


def _gp_to_channels(gp: dict):
    """Convert XboxController.read() dict to (ai: List[int8], di: List[bool])."""
    def joy(v):  return max(-128, min(127, int(round(v * 127.0))))
    def trig(v): return max(0,    min(127, int(round(v * 127.0))))
    ai = [
        joy(gp['RightJoystickX']),  # AI0: right_lr
        joy(gp['RightJoystickY']),  # AI1: right_ud
        0,                           # AI2: right_rocker — unmapped
        joy(gp['LeftJoystickX']),   # AI3: left_lr
        joy(gp['LeftJoystickY']),   # AI4: left_ud
        0,                           # AI5: left_rocker  — unmapped
        trig(gp['RightTrigger']),   # AI6: right_paddle
        trig(gp['LeftTrigger']),    # AI7: left_paddle
    ]
    di = [
        bool(gp['A']),           # DI0
        bool(gp['B']),           # DI1
        bool(gp['X']),           # DI2
        bool(gp['Y']),           # DI3
        bool(gp['LeftBumper']),  # DI4
        bool(gp['RightBumper']), # DI5
        bool(gp['LeftThumb']),   # DI6
        bool(gp['RightThumb']),  # DI7
        bool(gp['Back']),        # DI8
        bool(gp['Start']),       # DI9
        bool(gp['UpDPad']),      # DI10
        bool(gp['DownDPad']),    # DI11
    ]
    return ai, di


def _merge(nidaq_ai, nidaq_di, gp_ai, gp_di):
    """Merge NiDAQ and gamepad inputs: larger |value| wins per axis, OR for buttons."""
    ai = [n if abs(n) >= abs(g) else g for n, g in zip(nidaq_ai, gp_ai)]
    di = [n or g for n, g in zip(nidaq_di, gp_di)]
    return ai, di


def _to_mask(di):
    return sum(1 << i for i, v in enumerate(di) if v)


def main():
    parser = argparse.ArgumentParser(description="Robot joystick/gamepad sender")
    parser.add_argument("--ip", help="Robot IP:port  e.g. 192.168.0.132:8080")
    parser.add_argument("--id", type=int, default=1, dest="local_id", help="Local device ID")
    parser.add_argument("--rate", type=int, default=50, help="TX rate in Hz (default: 50)")
    parser.add_argument("--dry", action="store_true", help="Run without connecting — prints values")
    parser.add_argument("--debug", action="store_true", help="Show live values while connected")
    args = parser.parse_args()

    if not args.dry and not args.ip:
        parser.error("--ip is required unless --dry is set")

    print("Initializing NiDAQ joysticks...")
    tx_period = 1.0 / args.rate

    joy = NiDAQJoysticks(output_format=OutputFormat.INT8, deadzone=1.5, padding=2.5)
    gamepad = XboxController()

    udp = None
    if not args.dry:
        host, _, port_str = args.ip.rpartition(':')
        port = int(port_str)
        udp = UDPSocket(local_id=args.local_id, max_age_seconds=0.5, nominal_rate_hz=args.rate)
        udp.setup(host=host, port=port, inputs='', outputs='<8bH', is_server=False)
        print(f"Connecting to {host}:{port}...")
        if not udp.handshake(timeout=10.0):
            print("Handshake failed")
            joy.close()
            udp.close()
            return

    label = "DRY RUN" if args.dry else f"→ {args.ip}"
    print(f"{label} at {args.rate} Hz — Ctrl+C to stop")

    try:
        next_time = time.monotonic()
        tx_count = 0
        dbg_time = time.monotonic()

        while True:
            nidaq = joy.read()
            gp = gamepad.read()
            gp_ai, gp_di = _gp_to_channels(gp)

            nidaq_di = [v > 0 for v in nidaq.di]
            ai, di = _merge(nidaq.ai, nidaq_di, gp_ai, gp_di)
            mask = _to_mask(di)

            if udp and not udp.send(ai + [mask]):
                break

            tx_count += 1

            if args.dry or args.debug:
                now = time.monotonic()
                if now - dbg_time >= 0.1:
                    hz = tx_count / (now - dbg_time)
                    gp_str = "GP:OK" if gamepad.is_connected() else "GP:--"
                    ax = " ".join(f"A{i}:{v:+4d}" for i, v in enumerate(ai))
                    print(f"\r{hz:5.0f}Hz {gp_str} | {ax} | BTN:{mask:012b}", end="", flush=True)
                    tx_count = 0
                    dbg_time = now

            next_time += tx_period
            sleep_for = next_time - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                next_time = time.monotonic()

    except KeyboardInterrupt:
        pass
    finally:
        if udp:
            udp.send([0] * 8 + [0])
            udp.close()
        joy.close()
        print("\nStopped")


if __name__ == "__main__":
    main()
