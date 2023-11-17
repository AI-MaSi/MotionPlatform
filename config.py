# explain these some day

# <=Little-endian, d=doubles
# this is just for the joystick data!
data_type = '<d'

NUM_AI_CHANNELS = 8
NUM_DI_CHANNELS = 12

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

loop_delay = 2

file_path = "log/motionplatf_data.bin"

BUFFER_SIZE = 10

# host = '10.214.5.110'
# host = '10.214.3.13'
host = '127.0.0.1'
port = 5111