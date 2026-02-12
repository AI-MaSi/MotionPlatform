"""
Excavator control — NiDAQ joystick version.

Reads joystick axes and bumper buttons from NiDAQ, sends over UDP to robot.

UDP output (6 signed bytes):
    [0] LeftJoystickY   (-128..127)   ← AI4 (left_ud)
    [1] LeftJoystickX   (-128..127)   ← AI3 (left_lr)
    [2] RightJoystickY  (-128..127)   ← AI1 (right_ud, inverted)
    [3] RightJoystickX  (-128..127)   ← AI0 (right_lr)
    [4] LeftBumper       (0 or 1)     ← DI2
    [5] RightBumper      (0 or 1)     ← DI8

Usage:
    python komatsu_main.py <robot_ip>
    python komatsu_main.py 192.168.1.100
"""

import argparse
import time

from modules.NiDAQ_controller import NiDAQJoysticks
from modules.udp_socket import UDPSocket

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROBOT_PORT = 5050
NUM_INPUTS = 0    # we don't receive from robot
NUM_OUTPUTS = 6   # 4 axes + 2 bumpers
TX_RATE_HZ = 100
TX_PERIOD = 1.0 / TX_RATE_HZ

HMAC_KEY = "changeme_shared_secret"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Excavator joystick sender (NiDAQ)")
    parser.add_argument("robot_ip", help="Robot IP address")
    parser.add_argument("--port", type=int, default=ROBOT_PORT)
    parser.add_argument("--debug", action="store_true", help="Show send rate and channel values")
    args = parser.parse_args()

    # --- NiDAQ Joysticks ---
    print("Initializing NiDAQ joysticks...")
    joy = NiDAQJoysticks(output_format="int8", deadzone=1.5, padding=2.5)

    # --- UDP ---
    udp = UDPSocket(local_id=0, max_age_seconds=0.5, hmac_key=HMAC_KEY)
    udp.setup(host=args.robot_ip, port=args.port,
              num_inputs=NUM_INPUTS, num_outputs=NUM_OUTPUTS,
              is_server=False)

    print(f"Connecting to robot at {args.robot_ip}:{args.port}...")
    if not udp.handshake(timeout=10.0):
        print("Handshake failed")
        joy.close()
        udp.close()
        return

    print(f"Sending at {TX_RATE_HZ} Hz — press Ctrl+C to stop")

    # --- TX loop ---
    try:
        next_time = time.monotonic()
        tx_count = 0
        dbg_time = time.monotonic()
        while True:
            axis, buttons = joy.read()

            # Map NiDAQ channels to match Xbox controller layout
            ly = axis[4]                        # left_ud   → LeftJoystickY
            lx = axis[3]                        # left_lr   → LeftJoystickX
            ry = -axis[1]                       # right_ud  → RightJoystickY (inverted)
            rx = axis[0]                        # right_lr  → RightJoystickX
            lb = 1 if buttons[2] else 0         # DI2       → LeftBumper
            rb = 1 if buttons[8] else 0         # DI8       → RightBumper

            udp.send([ly, lx, ry, rx, lb, rb])
            tx_count += 1

            if args.debug:
                now = time.monotonic()
                if now - dbg_time >= 0.25:
                    hz = tx_count / (now - dbg_time)
                    print(f"\r{hz:5.0f} Hz | LY:{ly:+4d} LX:{lx:+4d} RY:{ry:+4d} RX:{rx:+4d} LB:{lb} RB:{rb}", end="", flush=True)
                    tx_count = 0
                    dbg_time = now

            next_time += TX_PERIOD
            sleep_for = next_time - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                next_time = time.monotonic()

    except KeyboardInterrupt:
        pass
    finally:
        udp.send([0, 0, 0, 0, 0, 0])
        joy.close()
        udp.close()
        print("Stopped")


if __name__ == "__main__":
    main()
