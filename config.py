# explain these some day

NUM_AI_CHANNELS = 8
NUM_DI_CHANNELS = 12

local_addr = '127.0.0.1'
connect_addr = '127.0.0.1'
port = 5111
identification_number = 2 # 0 excavator, 1 Mevea, 2 Motion Platform
inputs = 0
outputs = NUM_AI_CHANNELS + NUM_DI_CHANNELS


file_path = "log/example_data.bin"
BUFFER_SIZE = 100


endian_specifier = '<' # Little-endian

unix_format = 'Q' # 8 byte integer (UNIX-timestamp)

handshake_format = 'i' # Signed int (handshake) 4 bytes

data_format = 'd' # doubles (data) 8 bytes

checksum_format = 'B' # Unsigned char (checksum) 1 byte


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


