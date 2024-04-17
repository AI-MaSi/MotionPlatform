# this code gets the controller inputs from the motionplatform
# simulated values can be used without NiDAQ-devices or -libraries

# arguments
# simulation_mode, True for simulated values, False for values from NiDAQmx-device
# decimals, how accurate output tou want. Use integer(s)

# arguments in the read-function
# combine, make the code return values separated (ai, di) or combined (aidi)

try:
    import nidaqmx
    from nidaqmx.constants import TerminalConfiguration

    NIDAQMX_AVAILABLE = True
except ImportError:
    NIDAQMX_AVAILABLE = False

import random

di_channels = [
    "Dev2/port0/line0",  # right stick rocker up
    "Dev2/port0/line1",  # right stick rocker down
    "Dev2/port0/line2",  # right stick button rear
    "Dev2/port0/line3",  # right stick button bottom
    "Dev2/port0/line4",  # right stick button top
    "Dev2/port0/line5",  # right stick button mid

    "Dev2/port0/line6",  # left stick rocker up
    "Dev2/port0/line7",  # left stick rocker down
    "Dev2/port1/line0",  # left stick button rear
    "Dev2/port1/line1",  # left stick button top
    "Dev2/port1/line2",  # left stick button bottom
    "Dev2/port1/line3"  # left stick button mid
]

ai_channels = [
    ("Dev2/ai0", "ai0"),  # right stick L/R
    ("Dev2/ai1", "ai1"),  # right stick U/D
    ("Dev2/ai2", "ai2"),  # right stick rocker
    ("Dev2/ai3", "ai3"),  # left stick L/R
    ("Dev2/ai4", "ai4"),  # left stick U/D
    ("Dev2/ai5", "ai5"),  # left stick rocker
    ("Dev2/ai6", "ai6"),  # right pedal
    ("Dev2/ai7", "ai7")  # left pedal
]

NUM_AI_CHANNELS = len(ai_channels)
NUM_DI_CHANNELS = len(di_channels)


class DataOutput:
    def __init__(self, simulation_mode=False, decimals=2):
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

            # Prompt the user to confirm they want to proceed
            proceed = input("Send Y to continue!: ")
            if proceed.lower() != 'y':
                raise NiDAQmxInitializationError("Simulation usage not confirmed!")
            else:
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
                    # Convert analog input from 0.5-4.5V to -1 to 1
                    ai_channel_data = self.task_ai.read()
                    raw_di_data = self.task_di.read()  # Read the boolean data
                    di_channel_data = [float(value) for value in raw_di_data]  # Convert boolean to float
                    ai_channel_data = [round((value - 2.5) / 2.0, self.decimals) for value in ai_channel_data]
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
