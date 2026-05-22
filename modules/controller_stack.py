"""
Controller stack for merging NiDAQ joystick and USB gamepad commands.
"""

import json
from pathlib import Path
from typing import Iterable, List, Sequence


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "configuration_files" / "controller_config.json"
AXIS_COUNT = 8
BUTTON_COUNT = 16
GAMEPAD_AXIS_NAMES = [
    "right_stick_x",
    "right_stick_y",
    "right_rocker",
    "left_stick_x",
    "left_stick_y",
    "left_rocker",
    "right_trigger",
    "left_trigger",
]
GAMEPAD_BUTTON_NAMES = [
    "A",
    "B",
    "X",
    "Y",
    "LeftBumper",
    "RightBumper",
    "LeftThumb",
    "RightThumb",
    "Back",
    "Start",
    "UpDPad",
    "DownDPad",
    "LeftDPad",
    "RightDPad",
]


def _clamp_int8(value: float) -> int:
    return max(-128, min(127, int(round(value))))


def _percent_to_fraction(value) -> float:
    try:
        fraction = float(value) / 100.0
    except (TypeError, ValueError):
        fraction = 0.0
    return max(0.0, min(0.999, fraction))


def _axis_deadzones(config: dict, controller_name: str) -> List[float]:
    controller_config = config.get(controller_name, {})
    raw_axes = controller_config.get("axes")
    if isinstance(raw_axes, list) and raw_axes and isinstance(raw_axes[0], dict):
        axes = [0.0] * AXIS_COUNT
        for axis in raw_axes:
            try:
                index = int(axis.get("index"))
            except (TypeError, ValueError):
                continue
            if 0 <= index < AXIS_COUNT:
                axes[index] = axis.get("deadzone_percent", 0.0)
        return [_percent_to_fraction(v) for v in axes]

    legacy_axes = controller_config.get("deadzone_percent", {}).get("axes", [])
    axes = list(legacy_axes)[:AXIS_COUNT] if isinstance(legacy_axes, list) else []
    axes.extend([0.0] * (AXIS_COUNT - len(axes)))
    return [_percent_to_fraction(v) for v in axes]


def _axis_directions(config: dict, controller_name: str) -> List[int]:
    controller_config = config.get(controller_name, {})
    raw_axes = controller_config.get("axes")
    directions = [1] * AXIS_COUNT
    if isinstance(raw_axes, list) and raw_axes and isinstance(raw_axes[0], dict):
        for axis in raw_axes:
            try:
                index = int(axis.get("index"))
            except (TypeError, ValueError):
                continue
            if 0 <= index < AXIS_COUNT and int(axis.get("direction", 1)) < 0:
                directions[index] = -1
    return directions


def _axis_enabled(config: dict, controller_name: str) -> List[bool]:
    controller_config = config.get(controller_name, {})
    raw_axes = controller_config.get("axes")
    enabled = [True] * AXIS_COUNT
    if isinstance(raw_axes, list) and raw_axes and isinstance(raw_axes[0], dict):
        for axis in raw_axes:
            try:
                index = int(axis.get("index"))
            except (TypeError, ValueError):
                continue
            if 0 <= index < AXIS_COUNT:
                enabled[index] = bool(axis.get("enabled", True))
    return enabled


def _gamepad_axis_indices(config: dict) -> dict:
    controller_config = config.get("gamepad", {})
    raw_axes = controller_config.get("axes")
    indices = {}

    if isinstance(raw_axes, list) and raw_axes and isinstance(raw_axes[0], dict):
        for axis in raw_axes:
            if not axis.get("enabled", True):
                continue
            try:
                index = int(axis.get("index"))
            except (TypeError, ValueError):
                continue
            name = axis.get("name")
            if isinstance(name, str) and name.lower() != "none" and 0 <= index < AXIS_COUNT:
                indices[name] = index

    if not indices:
        indices = {name: index for index, name in enumerate(GAMEPAD_AXIS_NAMES)}
    return indices


def _route_nidaq_axes(values: Sequence[int], config: dict) -> List[int]:
    controller_config = config.get("nidaq", {})
    raw_axes = controller_config.get("axes")
    output = [0] * AXIS_COUNT

    if not (isinstance(raw_axes, list) and raw_axes and isinstance(raw_axes[0], dict)):
        for i, value in enumerate(values[:AXIS_COUNT]):
            output[i] = value
        return output

    gamepad_axis_indices = _gamepad_axis_indices(config)
    for axis in raw_axes:
        if not axis.get("enabled", True):
            continue
        try:
            source_index = int(axis.get("index"))
        except (TypeError, ValueError):
            continue
        gamepad_axis = axis.get("gamepad_axis")
        if isinstance(gamepad_axis, str) and gamepad_axis.lower() == "none":
            continue
        output_index = gamepad_axis_indices.get(gamepad_axis)
        if output_index is None:
            continue
        if 0 <= source_index < len(values) and 0 <= output_index < AXIS_COUNT:
            output[output_index] = values[source_index]
    return output


def _button_routes(config: dict, controller_name: str) -> List[dict]:
    controller_config = config.get(controller_name, {})
    raw_routes = controller_config.get("buttons", [])
    if isinstance(raw_routes, list):
        return raw_routes
    return []


def _gamepad_button_index(button_name):
    if isinstance(button_name, str) and button_name.lower() == "none":
        return None
    if isinstance(button_name, str) and button_name in GAMEPAD_BUTTON_NAMES:
        return GAMEPAD_BUTTON_NAMES.index(button_name)
    return None


def _route_nidaq_buttons(di_values: Sequence[bool], config: dict) -> List[bool]:
    routes = _button_routes(config, "nidaq")
    output = [False] * BUTTON_COUNT

    if not routes:
        for i, value in enumerate(di_values[:BUTTON_COUNT]):
            output[i] = bool(value)
        return output

    for route in routes:
        if not route.get("enabled", True):
            continue
        try:
            source_index = int(route.get("index"))
        except (TypeError, ValueError):
            continue
        output_index = _gamepad_button_index(route.get("gamepad_button"))
        if output_index is None:
            continue
        if 0 <= source_index < len(di_values) and 0 <= output_index < BUTTON_COUNT:
            output[output_index] = output[output_index] or bool(di_values[source_index])
    return output


def _route_gamepad_buttons(gp: dict, config: dict) -> List[bool]:
    routes = _button_routes(config, "gamepad")
    output = [False] * BUTTON_COUNT

    if not routes:
        for i, button in enumerate(GAMEPAD_BUTTON_NAMES):
            output[i] = bool(gp.get(button, False))
        return output

    for route in routes:
        if not route.get("enabled", True):
            continue
        button = route.get("name")
        output_index = _gamepad_button_index(button)
        if output_index is None:
            continue
        output[output_index] = output[output_index] or bool(gp.get(button, False))
    return output


def load_controller_config(path=DEFAULT_CONFIG_PATH) -> dict:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Controller config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def apply_deadzone(value: float, deadzone: float) -> float:
    ax = abs(value)
    if ax < deadzone:
        return 0.0
    scaled = (ax - deadzone) / (1.0 - deadzone)
    return scaled if value > 0 else -scaled


def apply_axis_settings(
    values: Sequence[int],
    deadzones: Sequence[float],
    directions: Sequence[int],
) -> List[int]:
    result = []
    for value, deadzone, direction in zip(values, deadzones, directions):
        normalized = max(-1.0, min(1.0, float(value) * direction / 127.0))
        result.append(_clamp_int8(apply_deadzone(normalized, deadzone) * 127.0))
    return result


def apply_axis_deadzones(values: Sequence[int], deadzones: Sequence[float]) -> List[int]:
    return apply_axis_settings(values, deadzones, [1] * AXIS_COUNT)


def apply_axis_enabled(values: Sequence[int], enabled: Sequence[bool]) -> List[int]:
    return [value if is_enabled else 0 for value, is_enabled in zip(values, enabled)]


def apply_axis_source(value: int, source: dict) -> int:
    if not isinstance(source, dict):
        return 0
    try:
        direction = -1 if int(source.get("direction", 1)) < 0 else 1
    except (TypeError, ValueError):
        direction = 1
    deadzone = _percent_to_fraction(source.get("deadzone_percent", 0.0))
    return apply_axis_settings([value], [deadzone], [direction])[0]


def _packet_slots(config: dict, name: str, count: int) -> List[dict]:
    output = [{"index": i, "gamepad": None, "nidaq": None} for i in range(count)]
    raw_slots = config.get(name, [])
    if not isinstance(raw_slots, list):
        return output

    for slot in raw_slots:
        try:
            index = int(slot.get("index"))
        except (AttributeError, TypeError, ValueError):
            continue
        if 0 <= index < count:
            output[index] = slot
    return output


def _route_packet_axes(nidaq_values: Sequence[int], gp_values: Sequence[int], config: dict) -> List[int]:
    gp_by_name = {
        name: gp_values[index]
        for index, name in enumerate(GAMEPAD_AXIS_NAMES)
        if index < len(gp_values)
    }
    output = []

    for slot in _packet_slots(config, "axes", AXIS_COUNT):
        nidaq_source = slot.get("nidaq")
        gp_source = slot.get("gamepad")

        nidaq_value = 0
        if isinstance(nidaq_source, dict):
            try:
                source_index = int(nidaq_source.get("index"))
            except (TypeError, ValueError):
                source_index = -1
            if 0 <= source_index < len(nidaq_values):
                nidaq_value = apply_axis_source(nidaq_values[source_index], nidaq_source)

        gp_value = 0
        if isinstance(gp_source, dict):
            raw_value = gp_by_name.get(gp_source.get("name"), 0)
            gp_value = apply_axis_source(raw_value, gp_source)

        output.append(nidaq_value if abs(nidaq_value) >= abs(gp_value) else gp_value)
    return output


def _route_packet_buttons(nidaq_values: Sequence[bool], gp: dict, config: dict) -> List[bool]:
    output = []

    for slot in _packet_slots(config, "buttons", BUTTON_COUNT):
        pressed = False

        nidaq_source = slot.get("nidaq")
        if isinstance(nidaq_source, dict):
            try:
                source_index = int(nidaq_source.get("index"))
            except (TypeError, ValueError):
                source_index = -1
            if 0 <= source_index < len(nidaq_values):
                pressed = pressed or bool(nidaq_values[source_index])

        gp_source = slot.get("gamepad")
        if isinstance(gp_source, dict):
            button = gp_source.get("name")
            if button in GAMEPAD_BUTTON_NAMES:
                pressed = pressed or bool(gp.get(button, False))

        output.append(pressed)
    return output


def _gp_to_channels(gp: dict):
    """Convert XboxController.read() dict to (ai: List[int8], di: List[bool])."""
    def joy(v):
        return _clamp_int8(float(v) * 127.0)

    def trig(v):
        return max(0, min(127, int(round(float(v) * 127.0))))

    ai = [
        joy(gp["RightJoystickX"]),  # AI0: right_lr
        joy(gp["RightJoystickY"]),  # AI1: right_ud
        0,                          # AI2: right_rocker - unmapped
        joy(gp["LeftJoystickX"]),   # AI3: left_lr
        joy(gp["LeftJoystickY"]),   # AI4: left_ud
        0,                          # AI5: left_rocker - unmapped
        trig(gp["RightTrigger"]),   # AI6: right_paddle
        trig(gp["LeftTrigger"]),    # AI7: left_paddle
    ]
    di = [
        bool(gp["A"]),           # DI0
        bool(gp["B"]),           # DI1
        bool(gp["X"]),           # DI2
        bool(gp["Y"]),           # DI3
        bool(gp["LeftBumper"]),  # DI4
        bool(gp["RightBumper"]), # DI5
        bool(gp["LeftThumb"]),   # DI6
        bool(gp["RightThumb"]),  # DI7
        bool(gp["Back"]),        # DI8
        bool(gp["Start"]),       # DI9
        bool(gp["UpDPad"]),      # DI10
        bool(gp["DownDPad"]),    # DI11
    ]
    return ai, di


def _merge(nidaq_ai, nidaq_di, gp_ai, gp_di):
    """Merge NiDAQ and gamepad inputs: larger |value| wins per axis, OR for buttons."""
    ai = [n if abs(n) >= abs(g) else g for n, g in zip(nidaq_ai, gp_ai)]
    di = [n or g for n, g in zip(nidaq_di, gp_di)]
    return ai, di


def to_mask(di: Iterable[bool]) -> int:
    return sum(1 << i for i, v in enumerate(di) if v)


class ControllerStack:
    def __init__(self, config_path=DEFAULT_CONFIG_PATH):
        from modules.NiDAQ_controller import NiDAQJoysticks, OutputFormat
        from modules.gamepad_module import XboxController

        config = load_controller_config(config_path)
        self.config = config
        self.joy = NiDAQJoysticks(output_format=OutputFormat.INT8, deadzone=0.0, padding=2.5)
        self.gamepad = XboxController()

    def read(self) -> dict:
        nidaq = self.joy.read()
        gp = self.gamepad.read()

        nidaq_di = [v > 0 for v in nidaq.di]
        gp_ai, gp_di = _gp_to_channels(gp)
        ai = _route_packet_axes(nidaq.ai, gp_ai, self.config)
        di = _route_packet_buttons(nidaq_di, gp, self.config)

        return {
            "ai": ai,
            "di": di,
            "mask": to_mask(di),
            "gamepad_connected": self.gamepad.is_connected(),
        }

    def close(self):
        try:
            self.gamepad.stop_monitoring()
        finally:
            self.joy.close()
