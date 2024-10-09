# this code gets the controller inputs from the motionplatform
# simulated values can be used without NiDAQ-devices or -libraries

import random
import time
import math

try:
    import nidaqmx
    from nidaqmx.constants import TerminalConfiguration
    NIDAQMX_AVAILABLE = True
except ImportError:
    NIDAQMX_AVAILABLE = False

# Remember that Python indexes start from 0, so the first channel is 0, not 1
ai_channels = [
    ("Dev2/ai0", "ai0"),  # 0. right stick L/R
    ("Dev2/ai1", "ai1"),  # 1. right stick U/D
    ("Dev2/ai2", "ai2"),  # 2. right stick rocker
    ("Dev2/ai3", "ai3"),  # 3. left stick L/R
    ("Dev2/ai4", "ai4"),  # 4. left stick U/D
    ("Dev2/ai5", "ai5"),  # 5. left stick rocker
    ("Dev2/ai6", "ai6"),  # 6. right pedal
    ("Dev2/ai7", "ai7")   # 7. left pedal
]

di_channels = [
    "Dev2/port0/line0",  # 8. right stick rocker up
    "Dev2/port0/line1",  # 9. right stick rocker down
    "Dev2/port0/line2",  # 10. right stick button rear
    "Dev2/port0/line3",  # 11. right stick button bottom
    "Dev2/port0/line4",  # 12. right stick button top
    "Dev2/port0/line5",  # 13. right stick button mid
    "Dev2/port0/line6",  # 14. left stick rocker up
    "Dev2/port0/line7",  # 15. left stick rocker down
    "Dev2/port1/line0",  # 16. left stick button rear
    "Dev2/port1/line1",  # 17. left stick button top
    "Dev2/port1/line2",  # 18. left stick button bottom
    "Dev2/port1/line3"   # 19. left stick button mid
]

NUM_AI_CHANNELS = len(ai_channels)
NUM_DI_CHANNELS = len(di_channels)


class NiDAQJoysticks:
    def __init__(self, simulation_mode=False, decimals=2):
        self.simulation_mode = simulation_mode
        self.decimals = decimals
        self.task_di = None
        self.task_ai = None

        if not self.simulation_mode:
            if NIDAQMX_AVAILABLE:
                self._init_nidaqmx()
            else:
                print("NiDAQmx is not available but required for non-simulation mode.")
                return
        elif self.simulation_mode:
            print("Simulated values selected! These are only for testing purposes, do not use as control signal!")
            proceed = input("Input Y to continue!: ")
            if proceed.lower() != 'y':
                print("Simulation usage not confirmed!")
                return
            else:
                print(f"Simulating {NUM_AI_CHANNELS} analog channels and {NUM_DI_CHANNELS} digital channels!")
                self.stub = NiDAQStub()

    def _init_nidaqmx(self):
        try:
            self.task_di = nidaqmx.Task()
            self.task_ai = nidaqmx.Task()

            for channeldi in di_channels:
                self.task_di.di_channels.add_di_chan(channeldi)

            for channelai, name in ai_channels:
                self.task_ai.ai_channels.add_ai_voltage_chan(channelai, terminal_config=TerminalConfiguration.RSE)

            print(f"Initialized Motion Platform joysticks!"
                  f" Ai channels: {NUM_AI_CHANNELS} Di channels: {NUM_DI_CHANNELS}")

        except nidaqmx.errors.DaqError as e:
            print(f"Failed to initialize NiDAQ: {e}")
        except Exception as e:
            print(f"Unknown error. Are NiDAQ drivers installed?: {e}")

    def read(self, combine=True):
        if self.simulation_mode:
            ai_channel_data, di_channel_data = self.stub.read()
        else:
            try:
                ai_channel_data = self.task_ai.read()
                raw_di_data = self.task_di.read()
                di_channel_data = [float(value) for value in raw_di_data]
                ai_channel_data = [round((value - 2.5) / 2.0, self.decimals) for value in ai_channel_data]
            except nidaqmx.errors.DaqError as e:
                print(f"Failed to read data from NiDAQ: {e}")
                return None

        if combine:
            combined_data = ai_channel_data + di_channel_data
            return combined_data
        else:
            return ai_channel_data, di_channel_data

    def __del__(self):
        if not self.simulation_mode:
            if hasattr(self, 'task_ai') and self.task_ai:
                self.task_ai.stop()
                self.task_ai.close()
            if hasattr(self, 'task_di') and self.task_di:
                self.task_di.stop()
                self.task_di.close()
        else:
            print("Simulated tasks closed!")


class NiDAQStub:
    def __init__(self, min_voltage=-1.0, max_voltage=1.0, frequency=0.1):
        self.min_voltage = min_voltage
        self.max_voltage = max_voltage
        self.frequency = frequency
        self.start_time = time.time()

    def generate_wave(self, elapsed_time):
        amplitude = (self.max_voltage - self.min_voltage) / 2
        mid_point = self.min_voltage + amplitude
        return mid_point + amplitude * math.sin(2 * math.pi * self.frequency * elapsed_time)

    def read(self):
        elapsed_time = time.time() - self.start_time
        ai_values = [self.generate_wave(elapsed_time) for _ in range(NUM_AI_CHANNELS)]
        di_values = [random.choice([0.0, 1.0]) for _ in range(NUM_DI_CHANNELS)]
        return ai_values, di_values