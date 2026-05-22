"""
Robot control — NiDAQ joystick + optional USB gamepad.

Primary:  NiDAQ physical joystick (AI0–AI7 axes, DI0–DI11 buttons)
Optional: USB gamepad (Xbox/compatible) — larger absolute value wins per axis

UDP output: 8 × int8 axes + 1 × uint16 button bitmask  ('< 8bH')
    Axes sent raw (no inversions) — configure on the robot/server side.

Usage:
    python main.py --ip 192.168.0.132:8080
    python main.py --dry
"""

import argparse
from collections import deque
import ctypes
import sys
import time

from modules.controller_stack import ControllerStack, DEFAULT_CONFIG_PATH
from modules.udp_socket import UDPSocket


def main():
    parser = argparse.ArgumentParser(description="Robot joystick/gamepad sender")
    parser.add_argument("--ip", help="Robot IP:port  e.g. 192.168.0.132:8080")
    parser.add_argument("--id", type=int, default=1, dest="local_id", help="Local device ID")
    parser.add_argument("--rate", type=int, default=50, help="TX rate in Hz (default: 50)")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Controller config JSON path")
    parser.add_argument("--dry", action="store_true", help="Run without connecting to robot")
    args = parser.parse_args()

    if args.rate <= 0:
        parser.error("--rate must be greater than 0")

    if not args.dry and not args.ip:
        parser.error("--ip is required unless --dry is set")

    host = None
    port = None
    if not args.dry:
        host, _, port_str = args.ip.rpartition(':')
        if not host or not port_str:
            parser.error("--ip must be in HOST:PORT format")
        try:
            port = int(port_str)
        except ValueError:
            parser.error("--ip port must be an integer")
        if not (0 < port <= 65535):
            parser.error("--ip port must be in range 1..65535")

    _winmm = None
    if sys.platform == 'win32':
        _winmm = ctypes.WinDLL('winmm')
        _winmm.timeBeginPeriod(1)

    print("Initializing controller stack...")
    tx_period = 1.0 / args.rate

    controllers = ControllerStack(config_path=args.config)

    udp = None
    if not args.dry:
        udp = UDPSocket(local_id=args.local_id, max_age_seconds=0.5, nominal_rate_hz=args.rate)
        udp.setup(host=host, port=port, inputs='', outputs='<8bH', is_server=False)
        print(f"Connecting to {host}:{port}...")
        if not udp.handshake(timeout=10.0):
            print("Handshake failed")
            controllers.close()
            udp.close()
            return

    label = "DRY RUN" if args.dry else f"→ {args.ip}"
    print(f"{label} at {args.rate} Hz — Ctrl+C to stop")

    try:
        next_time = time.monotonic()
        display_period = 1.0 / 20.0
        hz_window_seconds = 1.0
        send_times = deque()
        display_time = time.monotonic()
        status_width = 0
        last_gamepad_connected = None

        while True:
            command = controllers.read()
            ai = command["ai"]
            mask = command["mask"]
            gamepad_connected = command["gamepad_connected"]
            if gamepad_connected != last_gamepad_connected:
                status = "connected" if gamepad_connected else "disconnected"
                print(f"\nGamepad {status}")
                last_gamepad_connected = gamepad_connected

            if udp and not udp.send(ai + [mask]):
                break

            now = time.monotonic()
            send_times.append(now)
            while send_times and now - send_times[0] > hz_window_seconds:
                send_times.popleft()

            if now - display_time >= display_period:
                if len(send_times) >= 2:
                    hz = (len(send_times) - 1) / (send_times[-1] - send_times[0])
                else:
                    hz = 0.0
                gp_str = "GP:OK" if gamepad_connected else "GP:--"
                ax = " ".join(f"A{i}:{v:+4d}" for i, v in enumerate(ai))
                status = f"{hz:5.0f}Hz {gp_str} | {ax} | BTN:{mask:016b}"
                status_width = max(status_width, len(status))
                print(f"\r{status:<{status_width}}", end="", flush=True)
                display_time = now

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
            for _ in range(3):
                udp.send([0] * 8 + [0])
                time.sleep(min(tx_period, 0.02))
            udp.close()
        controllers.close()
        if _winmm:
            _winmm.timeEndPeriod(1)
        print("\nStopped")


if __name__ == "__main__":
    main()
