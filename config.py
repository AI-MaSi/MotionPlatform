# explain these some day


local_addr = '10.214.5.160'
connect_addr = '10.214.3.104'
port = 5111
identification_number = 2  # 0 excavator, 1 Mevea, 2 Motion Platform, more can be added...
inputs = 0
outputs = 20               # 8 AI-channels + 12 DI-channels


endian_specifier = '<'  # Little-endian

unix_format = 'Q'       # 8 byte integer (UNIX-timestamp)

handshake_format = 'i'  # Signed int (handshake) 4 bytes

data_format = 'd'       # doubles (data) 8 bytes

checksum_format = 'B'   # Unsigned char (checksum) 1 byte


BUFFER_SIZE = 100

dir_path = "log/"
base_filename = "motionplatform_recording"
