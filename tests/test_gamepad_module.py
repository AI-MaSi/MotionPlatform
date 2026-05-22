import time
from types import SimpleNamespace

from modules.gamepad_module import XboxController


def test_disconnected_read_resets_lingering_values():
    controller = XboxController(autostart=False)

    with controller._state_lock:
        controller._connected = True
        controller.LeftJoystickX = 0.75
        controller.A = 1
        controller._connected = False

    values = controller.read()

    assert values["LeftJoystickX"] == 0
    assert values["A"] == 0
    assert not controller.is_connected()


def test_monitor_error_marks_disconnected_and_clears_values(monkeypatch):
    controller = XboxController(autostart=False)

    with controller._state_lock:
        controller._connected = True
        controller.RightJoystickY = -0.5
        controller.B = 1

    def raise_reader_error():
        raise RuntimeError("reader failed")

    monkeypatch.setattr("modules.gamepad_module.get_gamepad", raise_reader_error)
    controller.start_monitoring()

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and controller.is_connected():
        time.sleep(0.01)

    values = controller.read()
    controller.stop_monitoring()

    assert not controller.is_connected()
    assert values["RightJoystickY"] == 0
    assert values["B"] == 0


def test_dpad_hat_axis_events_set_and_clear_directions():
    controller = XboxController(autostart=False)

    controller._process_event(SimpleNamespace(code="ABS_HAT0X", state=-1))
    controller._process_event(SimpleNamespace(code="ABS_HAT0Y", state=1))

    with controller._state_lock:
        assert controller.LeftDPad == 1
        assert controller.RightDPad == 0
        assert controller.UpDPad == 0
        assert controller.DownDPad == 1

    controller._process_event(SimpleNamespace(code="ABS_HAT0X", state=0))
    controller._process_event(SimpleNamespace(code="ABS_HAT0Y", state=0))

    with controller._state_lock:
        assert controller.LeftDPad == 0
        assert controller.RightDPad == 0
        assert controller.UpDPad == 0
        assert controller.DownDPad == 0
