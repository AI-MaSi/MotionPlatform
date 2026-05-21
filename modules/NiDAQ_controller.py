"""
NiDAQ joystick reader.
Reads analog (joystick) and digital (button) inputs from a National Instruments DAQ device.
"""

import nidaqmx
from nidaqmx.constants import TerminalConfiguration
from nidaqmx.errors import DaqError
from enum import Enum, auto
from collections import namedtuple

# ----- Configuration -----
MIN_VOLTAGE = 0.5      # Minimum joystick voltage (maps to -1.0)
MAX_VOLTAGE = 4.5      # Maximum joystick voltage (maps to +1.0)

AI_CHANNELS = [
    "Dev2/ai0", "Dev2/ai1", "Dev2/ai2", "Dev2/ai3",
    "Dev2/ai4", "Dev2/ai5", "Dev2/ai6", "Dev2/ai7"
]

DI_CHANNELS = [
    "Dev2/port0/line0", "Dev2/port0/line1", "Dev2/port0/line2", "Dev2/port0/line3",
    "Dev2/port0/line4", "Dev2/port0/line5", "Dev2/port0/line6", "Dev2/port0/line7",
    "Dev2/port1/line0", "Dev2/port1/line1", "Dev2/port1/line2", "Dev2/port1/line3"
]


class OutputFormat(Enum):
    FLOAT = auto()   # AI: [-1.0, 1.0], DI: {0.0, 1.0}
    INT8 = auto()    # AI: [-128, 127],  DI: {0, 127}


JoystickData = namedtuple("JoystickData", ["ai", "di"])


class NiDAQJoysticks:
    def __init__(self, output_format=OutputFormat.INT8, deadzone=5.0, padding=2.5):
        """
        :param output_format: OutputFormat.FLOAT or OutputFormat.INT8
        :param deadzone: Deadzone in %
        :param padding: Edge padding in %
        """
        if output_format not in OutputFormat:
            raise ValueError("output_format must be an OutputFormat enum value")
        if not (0 <= deadzone < 100):
            raise ValueError("deadzone must be in the range 0...<100%")
        if not (0 <= padding < 100):
            raise ValueError("padding must be in the range 0...<100%")
        self.output_format = output_format
        self.deadzone = deadzone / 100.0
        self.padding = padding / 100.0
        self.task_ai = nidaqmx.Task()
        self.task_di = nidaqmx.Task()
        self._init_channels()

    def _init_channels(self):
        try:
            for ch in DI_CHANNELS:
                self.task_di.di_channels.add_di_chan(ch)
            for ch in AI_CHANNELS:
                self.task_ai.ai_channels.add_ai_voltage_chan(
                    ch,
                    min_val=MIN_VOLTAGE,
                    max_val=MAX_VOLTAGE,
                    terminal_config=TerminalConfiguration.RSE
                )
            print(f"NiDAQ initialized: {len(AI_CHANNELS)} AI channels, {len(DI_CHANNELS)} DI channels.")
            print(f"NiDAQ ready | Deadzone: {self.deadzone*100:.1f}% | Padding: {self.padding*100:.1f}%")
        except DaqError as e:
            self.close()
            raise RuntimeError(f"Failed to initialize NiDAQ: {e}")

    def _apply_deadzone(self, x):
        d = self.deadzone
        ax = abs(x)
        if ax < d:
            return 0.0
        scaled = (ax - d) / (1.0 - d)
        return scaled if x > 0 else -scaled

    def _apply_padding(self, x):
        p = self.padding
        if p <= 0:
            return x
        x = x / (1.0 - p)
        return max(-1.0, min(1.0, x))

    def _normalize_ai(self, ai_values):
        """Normalize voltages to [-1.0, 1.0] with deadzone and edge padding."""
        voltage_range = MAX_VOLTAGE - MIN_VOLTAGE
        processed = []
        for v in ai_values:
            x = (v - MIN_VOLTAGE) / voltage_range * 2 - 1
            x = max(-1.0, min(1.0, x))
            x = self._apply_deadzone(x)
            x = self._apply_padding(x)
            processed.append(x)
        return processed

    def _normalize_di(self, di_values):
        """Convert raw digital readings to float {0.0, 1.0}."""
        return [1.0 if bool(v) else 0.0 for v in di_values]

    def _quantize(self, ai_floats, di_floats):
        """Apply output format and return JoystickData."""
        if self.output_format == OutputFormat.INT8:
            ai = [max(-128, min(127, int(round(v * 127)))) for v in ai_floats]
            di = [127 if v > 0.5 else 0 for v in di_floats]
            return JoystickData(ai=ai, di=di)
        return JoystickData(ai=ai_floats, di=di_floats)

    def read(self):
        """Read channels and return JoystickData(ai, di)."""
        try:
            ai_raw = self.task_ai.read()
            di_raw = self.task_di.read()
        except DaqError as e:
            raise RuntimeError(f"Failed to read from NiDAQ: {e}")
        return self._quantize(self._normalize_ai(ai_raw), self._normalize_di(di_raw))

    def close(self):
        for task in (self.task_ai, self.task_di):
            try:
                task.stop()
                task.close()
            except Exception:
                pass

    def __del__(self):
        self.close()


if __name__ == "__main__":
    """
    Test mode: Print active channels in real-time.
    Useful for identifying which physical input corresponds to which channel.
    """
    import time

    print("NiDAQ Channel Monitor")
    print("=" * 50)
    print("Move joysticks or press buttons to see active channels.")
    print("Press Ctrl+C to exit.\n")

    controller = NiDAQJoysticks(output_format=OutputFormat.FLOAT, deadzone=5.0)

    try:
        while True:
            data = controller.read()

            active_channels = []
            for i, (channel, value) in enumerate(zip(AI_CHANNELS, data.ai)):
                if abs(value) > 0.0:
                    active_channels.append(f"[AI:{i}] {channel}: {value:+.3f}")
            for i, (channel, value) in enumerate(zip(DI_CHANNELS, data.di)):
                if value > 0.5:
                    active_channels.append(f"[DI:{i}] {channel}: PRESSED")

            if active_channels:
                print("\r" + " | ".join(active_channels) + " " * 20, end="", flush=True)
            else:
                print("\r" + "No active channels" + " " * 50, end="", flush=True)

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n\nExiting...")
    finally:
        controller.close()
