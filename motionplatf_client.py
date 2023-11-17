import socket
import struct
import datetime
import threading
import motionplatf_controls
import os

# using these directly now. Add to __init__ if more flexibility needed
from config import file_path, BUFFER_SIZE, host, port, data_type

# make proper exceptions you lazy man
class MotionPlatformClient:
    def __init__(self, simulation_mode=True):
        # lock needed if using threading in the future...
        self.data_save_lock = threading.Lock()
        self.endian_specifier = data_type[0]  # Little-endian
        self.format_type = data_type[1:]  # doubles
        self.sequence_bytes = struct.calcsize((self.endian_specifier + 'I'))
        self.checksum_bytes = struct.calcsize((self.endian_specifier + 'B'))

        self.server_socket = None
        self.client_socket = None
        self.addr = None
        self.is_mevea = None
        self.num_inputs = None
        self.num_outputs = None
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

    def setup_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((host, port))
        self.server_socket.listen(1)

    def run_server(self):
        # error checking?
        self.setup_server()
        print(f"\nServer listening on {host}:{port}")

        self.client_socket, self.addr = self.server_socket.accept()
        # connected, do the handshake
        return self.handshake()

    def close_server(self):
        if self.server_socket:
            self.server_socket.close()
            print("Socket closed successfully!")
        else:
            print("something wrong has happened somewhere")

    def construct_format_string(self):
        # '<QI20dB'
        # '<'  Little-endian
        # 'Q' 8 byte integer (UNIX-timestamp)
        # 'I'  Unsigned int (sequence number) 4 bytes
        # '20d'  20 doubles (joystick data) 20*8 bytes
        # 'B'  Unsigned char (checksum) 1 byte
        return self.endian_specifier + 'Q' + 'I' + self.format_type * self.num_inputs + 'B'

    def read_data_file(self):
        format_str = self.construct_format_string()
        data_size = struct.calcsize(format_str)

        if not os.path.exists(file_path):
            print(f"Error: File '{file_path}' does not exist.")
            # raise or create file
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

                # do stuff with them. For now just print them
                print(
                    f"Sequence number: {sequence_number}, Unix time: {unix_time}, "
                    f"Checksum: {checksum}, Values: {values}")

    def pack_data(self, data):
        # packs the values from the joysticks as "format_type" (doubles)
        return struct.pack(self.endian_specifier + self.format_type * len(data), *data)

    def add_checks(self, packed_data):
        # add sequence number
        sequence_data = struct.pack((self.endian_specifier + 'I'), self.sequence_number)
        packed_values = sequence_data + packed_data

        # add checksum
        checksum = self.compute_checksum(packed_data)
        packed_values += struct.pack((self.endian_specifier + 'B'), checksum)
        # <I20dB
        self.sequence_number += 1
        return packed_values

    def send_data(self, data):
        # this should return false in some cases??
        # check how many inputs
        if self.num_inputs == 0:
            # no outputs, just send keep alive
            self.client_socket.send(b'\x00')
            return True

        # pack data
        packed_data = self.pack_data(data)
        # add checks to packed data
        final_data = self.add_checks(packed_data)
        # send the data
        # <I20dB
        # try except
        self.client_socket.send(final_data)
        # add packed data to buffer
        self.add_data_to_buffer(final_data)
        # socketError
        return True

    def send_handshake(self, packed_handshake):
        # only send the handshake without adding anything
        self.client_socket.send(packed_handshake)

    """
    WIP
    def send_start_flag(self):
        # tell the excavator to start running
        pass

    def send_stop_flag(self):
        # tell the excavator to stop running
        pass

    def start_data_recording(self):
        # start recording the motionplaft outputs
        pass

    def stop_data_recording(self):
        # stop recording the motionplatf outputs
        self.save_remaining_data()
        pass
    WIP
    """

    def receive_handshake(self):
        handshake = self.client_socket.recv(12)  # 3x4 bytes
        return struct.unpack((self.endian_specifier + '3i'), handshake)

    def receive_data(self):
        if self.num_outputs == 0:
            # just receive the keep alive
            keep_alive = self.client_socket.recv(1)
            if len(keep_alive) == 1:
                return True
            else:
                print("Lost keep-alive signal.")
                return False

        # recv_bytes calculated in the handshake -method
        full_data = self.client_socket.recv(self.recv_bytes)

        if len(full_data) != self.recv_bytes:
            print(f"Data received is shorter than expected: {len(full_data)} instead of {self.recv_bytes}.")
            # raise???
            return False

        # Extract and validate sequence number
        sequence_received, = struct.unpack('<I', full_data[:self.sequence_bytes])
        print(f"Received sequence number: {sequence_received}")

        # Extract and validate checksum
        received_checksum, = struct.unpack('<B', full_data[-self.checksum_bytes:])
        computed_checksum = self.compute_checksum(full_data[:-self.checksum_bytes])

        if received_checksum != computed_checksum:
            print("Checksum mismatch!")
            #raise???
            return False

        decoded_values = [round(struct.unpack(data_type, chunk)[0], 2)
                          for chunk in (full_data[self.sequence_bytes + i:self.sequence_bytes + i + struct.calcsize(data_type)]
                                        for i in range(0, len(full_data) - self.sequence_bytes - self.checksum_bytes,
                                                       struct.calcsize(data_type)))]
        return decoded_values

    def request_data(self):
        return self.motionplatf_output.read(combine=True)

    def add_data_to_buffer(self, packed_data):
        # make better error handling
        with self.data_save_lock:
            current_timestamp = datetime.datetime.now().timestamp()
            microsecond_timestamp = int(current_timestamp * 1e6)

            timestamped_data = struct.pack((self.endian_specifier + 'Q'), microsecond_timestamp) + packed_data
            self.data_buffer.append(timestamped_data)

    def save_buffer(self):
        # save data from buffer to file
        with open(file_path, 'ab') as f:
            for value in self.data_buffer:
                f.write(value)
        print("saved data to file...")
        self.data_buffer.clear()
        return True

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
        else:
            print("no overflow(?) data for saving!")

    def mainloop(self):
        # get controller data
        controller_data = self.request_data()
        if controller_data is None:
            # this shouldn't happen as the controller has error checking!
            print("No controller data available!")
            return False

        # handle, pack and send the data
        # currently only returns true
        send_success = self.send_data(controller_data)

        # check buffer length, and save to file if needed
        if len(self.data_buffer) >= BUFFER_SIZE:
            self.save_buffer()

        # receive data from the excavator. Only "keep alive" for now
        # data(successful), True(keep alive), False(failed)
        return self.receive_data()

    def handshake(self):
        try:
            # receive handshake from the Excavator or Mevea
            decoded_handshake = self.receive_handshake()

            self.is_mevea = decoded_handshake[0]
            self.num_outputs = decoded_handshake[1]
            self.num_inputs = decoded_handshake[2]

            if self.is_mevea == 0:
                print(f"Handshake received from Excavator ({self.addr}) with {self.num_inputs} inputs and {self.num_outputs} outputs.")

            elif self.is_mevea == 1:
                print(f"Handshake received from Mevea ({self.addr}) with {self.num_inputs} inputs and {self.num_outputs} outputs.")

            elif self.is_mevea > 1:
                print(f"Unknown handshake received from {self.addr} with {self.num_inputs} inputs and {self.num_outputs} outputs.")
                return False

            # send back the response handshake
            response = struct.pack((self.endian_specifier + '3i'), self.is_mevea, self.num_inputs, self.num_outputs)
            self.send_handshake(response)
            print(f"Handshake done with Address: {self.addr}\n")

        except socket.timeout:
            print(f"Handshake timeout with {self.addr}")
            return False
        # add more exceptions

        # Convert 0 to None
        # self.num_outputs = None if self.num_outputs == 0 else self.num_outputs
        # self.num_inputs = None if self.num_inputs == 0 else self.num_inputs

        # calculate the bytes you are going to receive
        self.recv_bytes = self.sequence_bytes + struct.calcsize(data_type) * self.num_outputs + self.checksum_bytes

        return True

