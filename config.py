# explain these some day


#local_addr = '10.214.5.160'
#connect_addr = '10.214.3.104'
local_addr = '127.0.0.1'
connect_addr = '127.0.0.1'
port = 5111
identification_number = 2  # 0 excavator, 1 Mevea, 2 Motion Platform, more can be added...
inputs = 0
outputs = 20               # 8 AI-channels + 12 DI-channels


# please don't change these yet

# '<'  Little-endian
endian_specifier = '<'
# 'Q' 8 byte integer (UNIX-timestamp)
unix_format = 'Q'
# 'i' Signed int (handshake) 4 bytes
handshake_format = 'i'
# 'd'  doubles (data) 8 bytes
data_format = 'd'
# 'B'  Unsigned char (checksum) 1 byte
checksum_format = 'B'


BUFFER_SIZE = 100

dir_path = "log/"
base_filename = "motionplatform_recording"


# identification numbers, you can add your own to the list
id_numbers = {
    0: "Excavator",
    1: "Mevea",
    2: "Motion Platform",
    3: "Digicenter"
}