import socket
import struct
import datetime
import threading
import os

from time import sleep

# using these directly now. Add to __init__ if more flexibility needed
# from config import file_path, BUFFER_SIZE, local_addr,\
#    connect_addr, port, endian_specifier, unix_format...

from config import *


# make proper exceptions you lazy man
class MasiSocketManager:
    def __init__(self):
        # lock needed if using threading in the future...
        self.data_save_lock = threading.Lock()
        # self.client_type = client_type # from config.py
        self.sequence_bytes = struct.calcsize((endian_specifier + 'I'))
        self.checksum_bytes = struct.calcsize((endian_specifier + 'B'))

        self.local_socket = None
        self.connected_socket = None
        self.connected_addr = None
        self.recvd_id_number = None
        self.recvd_num_inputs = None
        self.recvd_num_outputs = None
        self.data_buffer = []
        self.sequence_number = 0
        self.start_flag = None
        self.record_flag = None
        self.client_type = None

        # is this needed?
        self.socket_setup_done = None

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

    def setup_socket(self, client_type):
        # add error checking
        self.client_type = client_type
        if not self.local_socket:
            self.local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if self.client_type == 'server':
                self.local_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.local_socket.bind((local_addr, port))
                self.local_socket.listen(1)
                print("Socket configured as a server!")
                print(f"\nSocket listening on {local_addr}:{port}")
                self.connected_socket, self.connected_addr = self.local_socket.accept()
                self.socket_setup_done = True
                return self.socket_setup_done

            elif self.client_type == 'client':
                # TCP_NODELAY is apparently faster
                self.local_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                print("Socket configured as a client!")
                self.local_socket.connect((connect_addr, port))
                self.socket_setup_done = True
                return self.socket_setup_done

            print("Check client type!")
            self.socket_setup_done = False
            return self.socket_setup_done
        else:
            # socket already made, do something?
            print("socket already made!")
            self.socket_setup_done = False
            return self.socket_setup_done

    def close_socket(self):
        if self.local_socket:
            self.local_socket.close()
            print("Socket closed successfully!")
        else:
            print("something wrong has happened somewhere")

    def construct_format_string(self):
        # '<QI20dB'
        # '<'  Little-endian
        # 'Q' 8 byte integer (UNIX-timestamp)
        # 'I'  Unsigned int (sequence number) 4 bytes
        # 'd'  doubles (data) 8 bytes
        # 'B'  Unsigned char (checksum) 1 byte
        return endian_specifier + unix_format + sequence_format + data_format * self.recvd_num_inputs + checksum_format

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
        # packs the values as "format_type" (doubles as of 11/2023)
        return struct.pack(endian_specifier + data_format * len(data), *data)

    def add_checks(self, packed_data):
        # add sequence number
        sequence_data = struct.pack((endian_specifier + 'I'), self.sequence_number)
        packed_values = sequence_data + packed_data

        # add checksum
        checksum = self.compute_checksum(packed_data)
        packed_values += struct.pack((endian_specifier + 'B'), checksum)
        # <I20dB
        self.sequence_number += 1
        return packed_values

    def send_data(self, data):
        # this should return false in some cases??
        # check how many inputs
        if outputs == 0:
            # no outputs, just send keep alive
            self.connected_socket.send(b'\x00')
            return True

        # pack data
        packed_data = self.pack_data(data)
        # add checks to packed data
        final_data = self.add_checks(packed_data)
        # send the data

        # try except socketError
        self.connected_socket.send(final_data)

        # add packed data to buffer if record flag is True
        if self.record_flag:
            self.add_data_to_buffer(final_data)
        return True

    def set_start_flag(self, bool_val):
        # tell the excavator to start running
        # should check if this is bool....
        print(f"set start flag to {bool}!")
        self.start_flag = bool

    def set_record_flag(self, bool_val):
        # start recording the motionplaft outputs
        # should check if this is bool....
        print(f"set record flag to {bool_val}!")
        self.record_flag = bool_val

    def receive_data(self):
        if inputs == 0:
            # just receive the keep alive
            keep_alive = self.connected_socket.recv(1)
            if len(keep_alive) == 1:
                return True
            else:
                print("Lost keep-alive signal.")
                return False

        # recv_bytes calculated in the handshake -method
        full_data = self.connected_socket.recv(self.recv_bytes)

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

        decoded_values = [round(struct.unpack((endian_specifier + data_format), chunk)[0], 2)
                          for chunk in (full_data[self.sequence_bytes + i:self.sequence_bytes + i + struct.calcsize((endian_specifier + data_format))]
                                        for i in range(0, len(full_data) - self.sequence_bytes - self.checksum_bytes,
                                                       struct.calcsize((endian_specifier + data_format))))]
        return decoded_values

    def add_data_to_buffer(self, packed_data):
        # make better error handling
        with self.data_save_lock:
            current_timestamp = datetime.datetime.now().timestamp()
            microsecond_timestamp = int(current_timestamp * 1e6)

            timestamped_data = struct.pack((endian_specifier + 'Q'), microsecond_timestamp) + packed_data
            self.data_buffer.append(timestamped_data)
            print("TESTPRINT: added to buffer")

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
                    missing_values = outputs - (len(value) // 8 - 1)  # subtract 1 for the timestamp
                    value += struct.pack('<{}d'.format(missing_values), *([0.0] * missing_values))  # 0.0 doubles
                    f.write(value)
            self.data_buffer.clear()
            print("\nSaved remaining data.")
        else:
            print("no data in buffer to save!")

    def handshake(self):
        # change to server
        if self.client_type == 'server':
            print("handshake receive")
            # receive handshake from the Excavator or Mevea
            # except AttributeError 'NoneType' object has no attribute 'recv'
            # packed_handshake = self.connected_socket.recv(12)  # 3x4 bytes
            packed_handshake = self.connected_socket.recv(12)  # 3x4 bytes
            self.recvd_id_number, self.recvd_num_outputs, self.recvd_num_inputs = struct.unpack((endian_specifier + 3*handshake_format), packed_handshake)
            # send back the response handshake
            response = struct.pack((endian_specifier + 3*handshake_format), identification_number, inputs, outputs)
            self.connected_socket.send(response)

        elif self.client_type == 'client':
            #self.is_mevea = identification_number
            #self.recvd_num_outputs = outputs
            #self.recvd_num_inputs = inputs

            # send the response handshake
            response = struct.pack((endian_specifier + 3*handshake_format), identification_number, inputs, outputs)
            self.local_socket.send(response)
            print("handshake send!")

            # receive handshake from the Excavator or Mevea
            # except AttributeError 'NoneType' object has no attribute 'recv'
            packed_handshake = self.local_socket.recv(12)  # 3x4 bytes
            recvd_id_number, recvd_inputs, recvd_outputs = struct.unpack((endian_specifier + 3*handshake_format), packed_handshake)

            if recvd_id_number == identification_number:
                print("cannot connect two of the same!")
            if recvd_inputs != outputs:
                print("input / output mismatch")
            if recvd_outputs != inputs:
                print("input / output mismatch")

        """
        if self.recvd_id_number == 0:
            print(f"Handshake received from Excavator ({self.connected_addr}) with {self.num_inputs} inputs and {self.num_outputs} outputs.")
        elif self.recvd_id_number == 1:
            print(f"Handshake received from Mevea ({self.connected_addr}) with {self.num_inputs} inputs and {self.num_outputs} outputs.")
        elif self.recvd_id_number == 2:
            print(f"Handshake received from Motion Platform ({self.connected_addr}) with {self.num_inputs} inputs and {self.num_outputs} outputs.")
        else:
            print(f"Unknown handshake received from {self.connected_addr} with {self.num_inputs} inputs and {self.num_outputs} outputs.")
            return False

        #except socket.timeout:
        # calculate the bytes you are going to receive
    
        if inputs >= 0:
            self.recv_bytes = self.sequence_bytes + struct.calcsize((endian_specifier + data_format)) * inputs + self.checksum_bytes
        else:
            # just wanting keep alive
            self.recv_bytes = self.sequence_bytes + struct.calcsize((endian_specifier + data_format))
        print(f"Handshake done. Bytes receiving: {self.recv_bytes}")
        """
        self.recv_bytes = self.sequence_bytes + struct.calcsize(
            (endian_specifier + data_format)) * inputs + self.checksum_bytes

        return True

