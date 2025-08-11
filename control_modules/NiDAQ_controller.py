"""
NiDAQ joystick reader.
Reads analog (joystick) and digital (button) inputs from a National Instruments DAQ device.
Optionally returns analog values as 8-bit signed integers (-128 to 127).
"""

import nidaqmx
from nidaqmx.constants import TerminalConfiguration
from nidaqmx.errors import DaqError

# ----- Configuration -----
CENTER_VOLTAGE = 2.5   # Neutral stick voltage
SCALE_FACTOR = 2.0     # Voltage range +/- 2V → normalized to [-1, 1]

AI_CHANNELS = [
    "Dev2/ai0", "Dev2/ai1", "Dev2/ai2", "Dev2/ai3",
    "Dev2/ai4", "Dev2/ai5", "Dev2/ai6", "Dev2/ai7"
]

DI_CHANNELS = [
    "Dev2/port0/line0", "Dev2/port0/line1", "Dev2/port0/line2", "Dev2/port0/line3",
    "Dev2/port0/line4", "Dev2/port0/line5", "Dev2/port0/line6", "Dev2/port0/line7",
    "Dev2/port1/line0", "Dev2/port1/line1", "Dev2/port1/line2", "Dev2/port1/line3"
]


class NiDAQJoysticks:
    def __init__(self, output_format="float"):
        """
        :param output_format: 'float' for normalized [-1, 1], 'int8' for [-128, 127].
        """
        if output_format not in ("float", "int8"):
            raise ValueError("output_format must be 'float' or 'int8'")
        self.output_format = output_format
        self.task_ai = nidaqmx.Task()
        self.task_di = nidaqmx.Task()
        self._init_channels()

    def _init_channels(self):
        """Initialize DAQ tasks for AI and DI channels."""
        try:
            for ch in DI_CHANNELS:
                self.task_di.di_channels.add_di_chan(ch)
            for ch in AI_CHANNELS:
                self.task_ai.ai_channels.add_ai_voltage_chan(
                    ch, terminal_config=TerminalConfiguration.RSE
                )
            print(f"NiDAQ initialized: {len(AI_CHANNELS)} AI channels, {len(DI_CHANNELS)} DI channels.")
        except DaqError as e:
            self.close()
            raise RuntimeError(f"Failed to initialize NiDAQ: {e}")

    def _normalize_ai(self, ai_values):
        """Convert raw voltages to requested format."""
        normalized = [(v - CENTER_VOLTAGE) / SCALE_FACTOR for v in ai_values]
        if self.output_format == "int8":
            return [max(-128, min(127, int(round(v * 127)))) for v in normalized]
        return normalized

    def read(self):
        """
        Read AI and DI channel values.
        :return: (ai_list, di_list)
        """
        try:
            ai_raw = self.task_ai.read()
            di_raw = self.task_di.read()
        except DaqError as e:
            raise RuntimeError(f"Failed to read from NiDAQ: {e}")

        ai_processed = self._normalize_ai(ai_raw)
        di_processed = [float(v) for v in di_raw]

        return ai_processed, di_processed

    def close(self):
        """Stop and close DAQ tasks."""
        for task in (self.task_ai, self.task_di):
            try:
                task.stop()
                task.close()
            except Exception:
                pass

    def __del__(self):
        self.close()
