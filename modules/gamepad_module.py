# Base code from: https://github.com/kevinhughes27/TensorKart/blob/master/utils.py

import math
import threading
import time
from inputs import get_gamepad, UnpluggedError


"""
MAPPING (this is the index read() function returns):
0: 'LeftJoystickY'
1: 'LeftJoystickX'
2: 'RightJoystickY'
3: 'RightJoystickX'
4: 'LeftTrigger'
5: 'RightTrigger'
6: 'LeftBumper'
7: 'RightBumper'
8: 'A'
9: 'X'
10: 'Y'
11: 'B'
12: 'LeftThumb'
13: 'RightThumb'
14: 'Back'
15: 'Start'
16: 'LeftDPad'
17: 'RightDPad'
18: 'UpDPad'
19: 'DownDPad'
"""


class XboxController:
    MAX_TRIG_VAL = math.pow(2, 8)
    MAX_JOY_VAL = math.pow(2, 15)

    def __init__(self, autostart=True):
        self._state_lock = threading.Lock()
        self._monitor_thread = None
        self._stop_event = threading.Event()
        self._connected = False
        self.reset_values()
        if autostart:
            self.start_monitoring()

    def reset_values(self):
        with self._state_lock:
            self._reset_values_locked()

    def _reset_values_locked(self):
        self.LeftJoystickY = 0
        self.LeftJoystickX = 0
        self.RightJoystickY = 0
        self.RightJoystickX = 0
        self.LeftTrigger = 0
        self.RightTrigger = 0
        self.LeftBumper = 0
        self.RightBumper = 0
        self.A = 0
        self.X = 0
        self.Y = 0
        self.B = 0
        self.LeftThumb = 0
        self.RightThumb = 0
        self.Back = 0
        self.Start = 0
        self.LeftDPad = 0
        self.RightDPad = 0
        self.UpDPad = 0
        self.DownDPad = 0

    def start_monitoring(self):
        if self._monitor_thread is None or not self._monitor_thread.is_alive():
            self._stop_event.clear()
            self._monitor_thread = threading.Thread(target=self._monitor_controller)
            self._monitor_thread.daemon = True
            self._monitor_thread.start()

    def stop_monitoring(self, timeout=0.2):
        self._stop_event.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=timeout)

    def read(self):
        with self._state_lock:
            if not self._connected:
                #print("[Warning] Controller is not connected! (you might need to press any button to connect)")
                self._reset_values_locked()
            return {
                'LeftJoystickY': self.LeftJoystickY,
                'LeftJoystickX': self.LeftJoystickX,
                'RightJoystickY': self.RightJoystickY,
                'RightJoystickX': self.RightJoystickX,
                'LeftTrigger': self.LeftTrigger,
                'RightTrigger': self.RightTrigger,
                'LeftBumper': self.LeftBumper,
                'RightBumper': self.RightBumper,
                'A': self.A,
                'X': self.X,
                'Y': self.Y,
                'B': self.B,
                'LeftThumb': self.LeftThumb,
                'RightThumb': self.RightThumb,
                'Back': self.Back,
                'Start': self.Start,
                'LeftDPad': self.LeftDPad,
                'RightDPad': self.RightDPad,
                'UpDPad': self.UpDPad,
                'DownDPad': self.DownDPad
            }

    def _monitor_controller(self):
        while not self._stop_event.is_set():
            try:
                events = get_gamepad()
                with self._state_lock:
                    self._connected = True
                    for event in events:
                        self._process_event_locked(event)
            except UnpluggedError:
                self._mark_disconnected()
                self._stop_event.wait(1.0)
            except Exception:
                self._mark_disconnected()
                self._stop_event.wait(1.0)

    def _process_event(self, event):
        with self._state_lock:
            self._process_event_locked(event)

    def _process_event_locked(self, event):
        if event.code == 'ABS_Y':
            self.LeftJoystickY = event.state / self.MAX_JOY_VAL
        elif event.code == 'ABS_X':
            self.LeftJoystickX = event.state / self.MAX_JOY_VAL
        elif event.code == 'ABS_RY':
            self.RightJoystickY = event.state / self.MAX_JOY_VAL
        elif event.code == 'ABS_RX':
            self.RightJoystickX = event.state / self.MAX_JOY_VAL
        elif event.code == 'ABS_Z':
            self.LeftTrigger = event.state / self.MAX_TRIG_VAL
        elif event.code == 'ABS_RZ':
            self.RightTrigger = event.state / self.MAX_TRIG_VAL
        elif event.code == 'BTN_TL':
            self.LeftBumper = event.state
        elif event.code == 'BTN_TR':
            self.RightBumper = event.state
        elif event.code == 'BTN_SOUTH':
            self.A = event.state
        elif event.code == 'BTN_NORTH':
            self.Y = event.state
        elif event.code == 'BTN_WEST':
            self.X = event.state
        elif event.code == 'BTN_EAST':
            self.B = event.state
        elif event.code == 'BTN_THUMBL':
            self.LeftThumb = event.state
        elif event.code == 'BTN_THUMBR':
            self.RightThumb = event.state
        elif event.code == 'BTN_SELECT':
            self.Back = event.state
        elif event.code == 'BTN_START':
            self.Start = event.state
        elif event.code == 'ABS_HAT0X':
            self.LeftDPad = 1 if event.state < 0 else 0
            self.RightDPad = 1 if event.state > 0 else 0
        elif event.code == 'ABS_HAT0Y':
            self.UpDPad = 1 if event.state < 0 else 0
            self.DownDPad = 1 if event.state > 0 else 0
        elif event.code == 'BTN_TRIGGER_HAPPY1':
            self.LeftDPad = event.state
        elif event.code == 'BTN_TRIGGER_HAPPY2':
            self.RightDPad = event.state
        elif event.code == 'BTN_TRIGGER_HAPPY3':
            self.UpDPad = event.state
        elif event.code == 'BTN_TRIGGER_HAPPY4':
            self.DownDPad = event.state

    def _mark_disconnected(self):
        with self._state_lock:
            self._connected = False
            self._reset_values_locked()

    def is_connected(self):
        with self._state_lock:
            return self._connected

    def __del__(self):
        self.stop_monitoring()

if __name__ == "__main__":
    # initialize the controller
    controller = XboxController()

    while True:
        # read values
        print(controller.read())
        # check connection status
        print(f"Connected: {controller.is_connected()}")

        time.sleep(0.1)
