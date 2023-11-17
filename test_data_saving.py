# this scripts just reads the data and saves it with struct.
# might be useful for testing


import struct
import datetime
from time import sleep
import threading
import motionplatf_controls
import os

# using these directly now. Add to __init__ if more flexibility needed
from config import file_path, BUFFER_SIZE, data_type


# make proper exceptions you lazy man
class MotionPlatformClient:
    def __init__(self, simulation_mode=True):
        # lock needed if using threading in the future...
        self.data_save_lock = threading.Lock()
        self.endian_specifier = data_type[0]  # Little-endian
        self.format_type = data_type[1:]  # Doubles


        self.num_inputs = 20
        self.num_outputs = 0
        self.data_buffer = []
        self.sequence_number = 0

        # Initializing joysticks
        try:
            self.motionplatf_output = motionplatf_controls.DataOutput(simulation_mode, decimals=3)
        except motionplatf_controls.NiDAQmxInitializationError as e:
            self.motionplatf_output = None
            raise e

    @staticmethod
    def compute_checksum(data):
        checksum = 0
        for byte in data:
            checksum ^= byte
        return checksum

    @staticmethod
    def clear_file():
        # try:
        with open(file_path, 'wb') as file:
            pass
        # except Exception as e:
            # pass

    def construct_format_string(self):
        # '<QI20dB'
        # '<'  Little-endian
        # 'Q' UNIX-timestamp
        # 'I'  Unsigned int (sequence number) 4 bytes
        # '20d'  20 doubles (joystick data) 20*8 bytes
        # 'B'  Unsigned char (checksum) 1 byte
        return self.endian_specifier + 'Q' + 'I' + self.format_type * int(self.num_inputs) + 'B'


    def read_data_file(self):
        format_str = self.construct_format_string()
        data_size = struct.calcsize(format_str)

        if not os.path.exists(file_path):
            print(f"Error: File '{file_path}' does not exist.")
            return

        with open(file_path, 'rb') as f:
            while True:
                packed_data = f.read(data_size)
                if not packed_data:
                    break

                # Unpack the data
                data = struct.unpack(format_str, packed_data)

                # Extract the sequence number, Unix time, checksum, and values
                unix_time = data[0]
                sequence_number = data[1]
                checksum = data[-1]  # Checksum is the last byte
                values = data[2:-1]  # Values are between Unix time and checksum

                print(
                    f"Sequence number: {sequence_number}, Unix time: {unix_time}, "
                    f"Checksum: {checksum}, Values: {values}")

    def pack_data(self, data):
        # packs the values from the joysticks as doubles
        packed_data = struct.pack(self.endian_specifier + self.format_type * len(data), *data)
        return packed_data

    def request_data(self):
        return self.motionplatf_output.read(combine=True)


    def add_checks(self, packed_data):
        # add seq number
        sequence_data = struct.pack((self.endian_specifier + 'I'), self.sequence_number)
        packed_values = sequence_data + packed_data

        # add checksum
        checksum = self.compute_checksum(packed_data)
        packed_values += struct.pack((self.endian_specifier + 'B'), checksum)

        # <I20dB

        self.sequence_number += 1
        return packed_values

    def add_data_to_buffer(self, packed_data):
        # make better error handling
        with self.data_save_lock:
            current_timestamp = datetime.datetime.now().timestamp()
            microsecond_timestamp = int(current_timestamp * 1e6)

            timestamped_data = struct.pack((self.endian_specifier + 'Q'), microsecond_timestamp) + packed_data
            self.data_buffer.append(timestamped_data)

    def save_buffer(self):
        # save data from buffer to file
        try:
            with open(file_path, 'ab') as f:
                for value in self.data_buffer:
                    f.write(value)
            print("saved data to file...")
            self.data_buffer.clear()
            return True
        except Exception:
            print("error save buffer testprint")
            return False

    def save_remaining_data(self):
        # If there's remaining data in the buffer, save it to file
        if self.data_buffer:
            with open(file_path, 'ab') as f:
                for value in self.data_buffer:
                    missing_values = self.num_inputs - (len(value) // 8 - 1)  # subtract 1 for the timestamp
                    value += struct.pack('<{}d'.format(missing_values), *([0.0] * missing_values))  # 0.0 doubles
                    f.write(value)
            self.data_buffer.clear()
            print("\nSaved remaining data.")



    def mainloop(self):
        self.clear_file()
        print(self.construct_format_string())

        for i in range(100):
            controller_data = self.request_data()
            print(controller_data)
            packed_data = self.pack_data(controller_data)
            final_data = self.add_checks(packed_data)
            self.add_data_to_buffer(final_data)

            # check buffer length, and save to file if needed
            if len(self.data_buffer) >= BUFFER_SIZE:
                self.save_buffer()

        self.save_remaining_data()
        sleep(2)
        self.read_data_file()



if __name__ == "__main__":

    test = MotionPlatformClient(simulation_mode=True)
    test.mainloop()