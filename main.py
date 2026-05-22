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
from datetime import datetime
import queue
import sys
import threading
import time

from modules.controller_stack import ControllerStack, DEFAULT_CONFIG_PATH
from modules.udp_socket import UDPSocket


def _ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


class AsyncConsole:
    """Best-effort console output that cannot block the control loop."""

    def __init__(self, max_queue=8):
        self._queue = queue.Queue(maxsize=max_queue)
        self._status_written = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def log(self, message):
        self._push(("log", f"[{_ts()}] {message}"))

    def status(self, message, width):
        self._push(("status", message, width))

    def stop(self):
        self._push(None)
        self._thread.join(timeout=0.05)

    def _push(self, item):
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(item)
            except queue.Full:
                pass

    def _run(self):
        while True:
            item = self._queue.get()
            if item is None:
                return

            try:
                if item[0] == "log":
                    if self._status_written:
                        sys.stdout.write("\n")
                        self._status_written = False
                    sys.stdout.write(item[1] + "\n")
                else:
                    _, message, width = item
                    sys.stdout.write(f"\r{message:<{width}}")
                    self._status_written = True
                sys.stdout.flush()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Robot joystick/gamepad sender")
    parser.add_argument("--ip", help="Robot IP:port  e.g. 192.168.0.132:8080")
    parser.add_argument("--id", type=int, default=1, dest="local_id", help="Local device ID")
    parser.add_argument("--rate", type=int, default=100, help="NiDAQ/TX rate in Hz (default: 100)")
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
        # Disable QuickEdit: clicking the console window otherwise freezes the
        # process (Windows pauses output in selection mode), which is dangerous
        # in a real-time control loop.
        _kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        _stdin = _kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        _mode = ctypes.c_ulong()
        if _kernel32.GetConsoleMode(_stdin, ctypes.byref(_mode)):
            ENABLE_QUICK_EDIT = 0x0040
            ENABLE_EXTENDED_FLAGS = 0x0080
            _mode.value = (_mode.value & ~ENABLE_QUICK_EDIT) | ENABLE_EXTENDED_FLAGS
            _kernel32.SetConsoleMode(_stdin, _mode)

    console = AsyncConsole()
    console.log("Initializing controller stack...")
    tx_period = 1.0 / args.rate

    controllers = ControllerStack(config_path=args.config, nidaq_sample_rate=args.rate)

    udp = None
    if not args.dry:
        udp = UDPSocket(local_id=args.local_id, max_age_seconds=0.5, nominal_rate_hz=args.rate)
        udp.setup(host=host, port=port, inputs='', outputs='<8bH', is_server=False)
        console.log(f"Connecting to {host}:{port}...")
        if not udp.handshake(timeout=120.0):
            console.log("Handshake failed")
            controllers.close()
            udp.close()
            console.stop()
            return
        udp.set_nonblocking_send(True)

    label = "DRY RUN" if args.dry else f"→ {args.ip}"
    console.log(f"{label} at {args.rate} Hz - Ctrl+C to stop")

    try:
        display_period = 1.0 / 20.0
        hz_window_seconds = 1.0
        send_times = deque()
        loop_times = deque()
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
                console.log(f"Gamepad {status}")
                last_gamepad_connected = gamepad_connected

            now = time.monotonic()
            loop_times.append(now)
            while loop_times and now - loop_times[0] > hz_window_seconds:
                loop_times.popleft()

            if udp:
                if not udp.send(ai + [mask]):
                    break
                sent_at = time.monotonic()
                send_times.append(sent_at)
                while send_times and sent_at - send_times[0] > hz_window_seconds:
                    send_times.popleft()

            if now - display_time >= display_period:
                rate_times = send_times if udp else loop_times
                rate_label = "TX" if udp else "LOOP"
                if len(rate_times) >= 2:
                    hz = (len(rate_times) - 1) / (rate_times[-1] - rate_times[0])
                else:
                    hz = 0.0
                gp_str = "GP:OK" if gamepad_connected else "GP:--"
                ax = " ".join(f"A{i}:{v:+4d}" for i, v in enumerate(ai))
                status = f"[{_ts()}] {rate_label}:{hz:5.0f}Hz {gp_str} | {ax} | BTN:{mask:016b}"
                status_width = max(status_width, len(status))
                console.status(status, status_width)
                display_time = now

            # NiDAQ's hardware-timed read is the loop clock. A second software
            # sleep here fights DAQ timing and can make TX rate less stable.

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
        console.log("Stopped")
        console.stop()


if __name__ == "__main__":
    main()
