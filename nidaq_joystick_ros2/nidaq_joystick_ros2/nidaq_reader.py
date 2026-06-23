"""National Instruments DAQ joystick reader.

This is a standalone ROS-package copy of the MotionPlatform NiDAQ logic. It
keeps the same voltage normalization, deadzone, padding, and channel defaults
without importing or modifying the original MotionPlatform modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

try:
    import nidaqmx
    from nidaqmx.constants import TerminalConfiguration
    from nidaqmx.errors import DaqError
except ImportError:  # pragma: no cover - depends on host NI driver install.
    nidaqmx = None
    TerminalConfiguration = None

    class DaqError(Exception):
        """Fallback exception used when nidaqmx is not installed."""


DEFAULT_MIN_VOLTAGE = 0.5
DEFAULT_MAX_VOLTAGE = 4.5


def default_ai_channels(device_name: str = "Dev2") -> List[str]:
    return [f"{device_name}/ai{i}" for i in range(8)]


def default_di_channels(device_name: str = "Dev2") -> List[str]:
    return [
        *(f"{device_name}/port0/line{i}" for i in range(8)),
        *(f"{device_name}/port1/line{i}" for i in range(4)),
    ]


@dataclass(frozen=True)
class NiDaqConfig:
    ai_channels: Sequence[str]
    di_channels: Sequence[str]
    min_voltage: float = DEFAULT_MIN_VOLTAGE
    max_voltage: float = DEFAULT_MAX_VOLTAGE
    deadzone_percent: float = 1.5
    padding_percent: float = 2.5

    def validate(self) -> None:
        if nidaqmx is None:
            raise RuntimeError(
                "Python package 'nidaqmx' is not installed. Install NI-DAQmx "
                "and the nidaqmx Python package in the ROS 2 environment."
            )
        if not self.ai_channels:
            raise ValueError("At least one analog input channel is required.")
        if self.max_voltage <= self.min_voltage:
            raise ValueError("max_voltage must be greater than min_voltage.")
        if not 0.0 <= self.deadzone_percent < 100.0:
            raise ValueError("deadzone_percent must be in range [0, 100).")
        if not 0.0 <= self.padding_percent < 100.0:
            raise ValueError("padding_percent must be in range [0, 100).")


class NiDaqJoystickReader:
    """Read and normalize analog axes and digital buttons from NI-DAQ."""

    def __init__(self, config: NiDaqConfig) -> None:
        config.validate()
        self.config = config
        self.deadzone = config.deadzone_percent / 100.0
        self.padding = config.padding_percent / 100.0
        self.task_ai = nidaqmx.Task()
        self.task_di = nidaqmx.Task()
        self._closed = False
        self._init_channels()

    def _init_channels(self) -> None:
        try:
            for channel in self.config.di_channels:
                self.task_di.di_channels.add_di_chan(channel)
            for channel in self.config.ai_channels:
                self.task_ai.ai_channels.add_ai_voltage_chan(
                    channel,
                    min_val=self.config.min_voltage,
                    max_val=self.config.max_voltage,
                    terminal_config=TerminalConfiguration.RSE,
                )
        except DaqError as exc:
            self.close()
            raise RuntimeError(f"Failed to initialize NI-DAQ channels: {exc}") from exc

    def read(self) -> Tuple[List[float], List[int]]:
        """Return normalized analog axes and integer button states."""
        try:
            ai_raw = self.task_ai.read()
            di_raw = self.task_di.read() if self.config.di_channels else []
        except DaqError as exc:
            raise RuntimeError(f"Failed to read from NI-DAQ: {exc}") from exc

        axes = self._normalize_ai(self._as_list(ai_raw))
        buttons = [1 if bool(value) else 0 for value in self._as_list(di_raw)]
        return axes, buttons

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for task in (self.task_ai, self.task_di):
            try:
                task.stop()
                task.close()
            except Exception:
                pass

    def _normalize_ai(self, values: Iterable[float]) -> List[float]:
        voltage_range = self.config.max_voltage - self.config.min_voltage
        normalized = []
        for voltage in values:
            axis = (float(voltage) - self.config.min_voltage) / voltage_range * 2.0 - 1.0
            axis = self._clamp(axis)
            axis = self._apply_deadzone(axis)
            axis = self._apply_padding(axis)
            normalized.append(axis)
        return normalized

    def _apply_deadzone(self, value: float) -> float:
        magnitude = abs(value)
        if magnitude < self.deadzone:
            return 0.0
        scaled = (magnitude - self.deadzone) / (1.0 - self.deadzone)
        return scaled if value > 0.0 else -scaled

    def _apply_padding(self, value: float) -> float:
        if self.padding <= 0.0:
            return value
        return self._clamp(value / (1.0 - self.padding))

    @staticmethod
    def _as_list(values) -> List:
        if isinstance(values, list):
            return values
        if isinstance(values, tuple):
            return list(values)
        return [values]

    @staticmethod
    def _clamp(value: float) -> float:
        return max(-1.0, min(1.0, value))

    def __enter__(self) -> "NiDaqJoystickReader":
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()
