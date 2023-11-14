# this thing reads the .BIN-file
# UNIX timestamp + x amount of values

import struct
import os


def read(file_path, format_str):
    data_size = struct.calcsize(format_str)

    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist.")
        return

    with open(file_path, 'rb') as f:
        while True:
            packed_data = f.read(data_size)
            if not packed_data:
                break

            data = struct.unpack(format_str, packed_data)
            unix_time = data[0]
            values = data[1:]

            print(f"Unix time: {unix_time}, Values: {values}")
