# this code gets the controller inputs from the motionplatform
# simulated values can be used without NiDAQ-devices or -libraries


# arguments
# simulation_mode, True for simulated values, False for values from NiDAQmx-device
# decimals, how accurate output tou want. Use integer(s)

# arguments in the read-function
# combine, make the code return values separated (ai, di) or combined (aidi)
# pack (MOVED ELSEWHERE), pack the data with struct.

import random

# Constants for channel counts
NUM_AI_CHANNELS = 8
NUM_DI_CHANNELS = 12

format_str = '<d'
endian_specifier = format_str[0]  # Little-endian
format_type = format_str[1:]  # Doubles

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

        # Use the constant NIDAQMX_AVAILABLE to check availability
        if not self.simulation_mode and NIDAQMX_AVAILABLE:
            self.init_nidaqmx()
        elif not self.simulation_mode and not NIDAQMX_AVAILABLE:
            #raise ei ajureita!!!!
            print("No NiDAQ API available!")
        elif self.simulation_mode:
            print("Simulated values selected! These are only for testing purposes")
            print(f"Ai channels: {NUM_AI_CHANNELS} Di channels: {NUM_DI_CHANNELS}")


    def init_nidaqmx(self):
        try:
            self.task_di = nidaqmx.Task()
            self.task_ai = nidaqmx.Task()

            # Initialize the digital input channels
            di_channels = [
                "Dev2/port0/line0",
                "Dev2/port0/line1",
                "Dev2/port0/line2",
                "Dev2/port0/line3",
                "Dev2/port0/line4",
                "Dev2/port0/line5",
                "Dev2/port0/line6",
                "Dev2/port0/line7",
                "Dev2/port1/line0",
                "Dev2/port1/line1",
                "Dev2/port1/line2",
                "Dev2/port1/line3"
            ]
            for channeldi in di_channels:
                self.task_di.di_channels.add_di_chan(channeldi)

            # Initialize the analog input channels
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
            for channelai, name in ai_channels:
                self.task_ai.ai_channels.add_ai_voltage_chan(channelai, terminal_config=TerminalConfiguration.RSE)

            print(f"Initialized Motion Platform joysticks!"
                  f" Ai channels: {NUM_AI_CHANNELS} Di channels: {NUM_DI_CHANNELS}")

            #return NUM_AI_CHANNELS, NUM_DI_CHANNELS


        except nidaqmx.errors.DaqError as e:
            print(f"Failed to initialize NiDAQ: {e}")

        except Exception as e:
            print(f"Unknown error. Are NiDAQ drivers installed?: {e}")

    def read(self, combine=True):
        ai_channel_data = []
        di_channel_data = []

        if self.simulation_mode:
            ai_channel_data = [round(random.uniform(-1, 1), self.decimals) for _ in range(NUM_AI_CHANNELS)]
            di_channel_data = [float(random.randint(0, 1)) for _ in range(NUM_DI_CHANNELS)]

        elif not self.simulation_mode and NIDAQMX_AVAILABLE:
            try:
                ai_channel_data = self.task_ai.read()
                raw_di_data = self.task_di.read()  # Read the boolean data
                di_channel_data = [float(value) for value in raw_di_data]  # Convert boolean to float
                ai_channel_data = [round((value - 2.5) * 0.5, self.decimals) for value in ai_channel_data]
            except nidaqmx.errors.DaqError as e:
                print(f"Failed to read data from NiDAQ: {e}")

        else:  # NIDAQMX not available

            # raise here?

            ai_channel_data = [0.0] * NUM_AI_CHANNELS
            di_channel_data = [0.0] * NUM_DI_CHANNELS  # Default to 0.0 for float

        if combine:
            combined_data = ai_channel_data + di_channel_data
            return combined_data  # Single unpacked list
        else:
            return ai_channel_data, di_channel_data  # Separate unpacked lists

    def close_tasks(self):
        # Close tasks safely
        if hasattr(self, 'task_ai') and self.task_ai.is_task_done():
            self.task_ai.stop()
            self.task_ai.close()


        if hasattr(self, 'task_di') and self.task_di.is_task_done():
            self.task_di.stop()
            self.task_di.close()

    def __del__(self):
        self.close_tasks()
        print("Tasks terminated safely :)")