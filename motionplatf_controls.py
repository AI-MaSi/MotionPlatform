# this code gets the controller inputs from the motionplatform
# simulated values can be used without NiDAQ-devices or -libraries

# arguments
# simulation_mode, True for simulated values, False for values from NiDAQmx-device
# decimals, how accurate output tou want. Use integer(s)

# arguments in the read-function
# combine, make the code return values separated (ai, di) or combined (aidi)

import random
from config import NUM_AI_CHANNELS, NUM_DI_CHANNELS, ai_channels, di_channels

try:
    import nidaqmx
    from nidaqmx.constants import TerminalConfiguration

    NIDAQMX_AVAILABLE = True
except ImportError:
    NIDAQMX_AVAILABLE = False


class DataOutput:
    def __init__(self, simulation_mode=False, decimals=3):
        self.simulation_mode = simulation_mode
        self.decimals = decimals
        self.task_di = None
        self.task_ai = None

        if not self.simulation_mode:
            if NIDAQMX_AVAILABLE:
                self.init_nidaqmx()
            else:
                raise NiDAQmxNotAvailableError("NiDAQmx is not available but required for non-simulation mode.")
        elif self.simulation_mode:
            print("Simulated values selected! These are only for testing purposes")
            print(f"Simulating {NUM_AI_CHANNELS} analog channels and {NUM_DI_CHANNELS} digital channels!")

    def init_nidaqmx(self):
        try:
            self.task_di = nidaqmx.Task()
            self.task_ai = nidaqmx.Task()

            # Initialize the digital input channels
            for channeldi in di_channels:
                self.task_di.di_channels.add_di_chan(channeldi)

            # Initialize the analog input channels
            for channelai, name in ai_channels:
                self.task_ai.ai_channels.add_ai_voltage_chan(channelai, terminal_config=TerminalConfiguration.RSE)

            print(f"Initialized Motion Platform joysticks!"
                  f" Ai channels: {NUM_AI_CHANNELS} Di channels: {NUM_DI_CHANNELS}")

        except nidaqmx.errors.DaqError as e:
            raise NiDAQmxInitializationError(f"Failed to initialize NiDAQ: {e}")
        except Exception as e:
            raise NiDAQmxInitializationError(f"Unknown error. Are NiDAQ drivers installed?: {e}")

    def read(self, combine=True):
        ai_channel_data = []
        di_channel_data = []

        if not self.simulation_mode:
            if NIDAQMX_AVAILABLE:
                try:
                    ai_channel_data = self.task_ai.read()
                    raw_di_data = self.task_di.read()  # Read the boolean data
                    di_channel_data = [float(value) for value in raw_di_data]  # Convert boolean to float
                    ai_channel_data = [round((value - 2.5) * 0.5, self.decimals) for value in ai_channel_data]
                except nidaqmx.errors.DaqError as e:
                    raise NiDAQmxReadError(f"Failed to read data from NiDAQ: {e}")
            else:
                raise NiDAQmxNotAvailableError("NiDAQmx is not available but required for non-simulation mode.")

        elif self.simulation_mode:
            ai_channel_data = [round(random.uniform(-1, 1), self.decimals) for _ in range(NUM_AI_CHANNELS)]
            di_channel_data = [float(random.randint(0, 1)) for _ in range(NUM_DI_CHANNELS)]

        if combine:
            combined_data = ai_channel_data + di_channel_data
            return combined_data  # Single unpacked list
        else:
            return ai_channel_data, di_channel_data  # Separate unpacked lists

    def close_tasks(self):
        # Close tasks safely
        if not self.simulation_mode:
            if hasattr(self, 'task_ai') and self.task_ai.is_task_done():
                self.task_ai.stop()
                self.task_ai.close()

            if hasattr(self, 'task_di') and self.task_di.is_task_done():
                self.task_di.stop()
                self.task_di.close()
        else:
            print("Simulated tasks closed!")

    def __del__(self):
        self.close_tasks()
        print("Tasks terminated safely :)")


class NiDAQmxInitializationError(Exception):
    pass


class NiDAQmxReadError(Exception):
    pass


class NiDAQmxNotAvailableError(Exception):
    pass
