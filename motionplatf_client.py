import socket
import struct
import datetime
from time import sleep
import threading
import motionplatf_controls
import os

# using these directly now. Add to __init__ if more flexibility needed
from config import loop_delay, file_path, BUFFER_SIZE, host, port, data_type

# make proper exceptions you lazy man
class MotionPlatformClient:
    def __init__(self, simulation_mode=True):
        # lock needed if using threading in the future...
        self.data_save_lock = threading.Lock()
        self.endian_specifier = data_type[0]  # Little-endian
        self.format_type = data_type[1:]  # Doubles
        self.motionplatf_output = motionplatf_controls.DataOutput(simulation_mode, decimals=3)

        self.server_socket = None
        self.client_socket = None
        self.addr = None
        self.is_mevea = None
        self.num_inputs = None
        self.num_outputs = None
        self.data_buffer = []
        self.sequence_number = 0

    @staticmethod
    def compute_checksum(data):
        checksum = 0
        for byte in data:
            checksum ^= byte
        return checksum

    def setup_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((host, port))
        self.server_socket.listen(1)

    def run_server(self):
        self.setup_server()
        print(f"\nServer listening on {host}:{port}")

        try:
            while True:
                self.client_socket, self.addr = self.server_socket.accept()
                # connected, do the handshake
                if self.handshake():
                    # handshake successful, start the mainloop
                    self.mainloop()
                else:
                    break
        except Exception as e:
            print(f"\nSocket connection Error: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()

    def construct_str_format(self):
        # very simple for now haha
        return self.endian_specifier + self.format_type * self.num_inputs

    def read_data_file(self):
        # '<Q20d' timestamp integer + 20 input doubles. Little endian
        str_format = self.construct_str_format()
        data_size = struct.calcsize(str_format)

        if not os.path.exists(file_path):
            print(f"Error: File '{file_path}' does not exist.")
            return

        with open(file_path, 'rb') as f:
            while True:
                packed_data = f.read(data_size)
                if not packed_data:
                    break

                data = struct.unpack(str_format, packed_data)
                unix_time = data[0]
                values = data[1:]

                print(f"Unix time: {unix_time}, Values: {values}")

    def pack_data(self, data):
        packed_data = struct.pack(self.endian_specifier + self.format_type * len(data), *data)
        return packed_data

    def send_data(self, packed_data):
        try:
            sequence_data = struct.pack('<I', self.sequence_number)
            packed_values = sequence_data + packed_data

            checksum = self.compute_checksum(packed_data)
            packed_values += struct.pack('<B', checksum)

            self.client_socket.send(packed_data)

            self.sequence_number += 1
            return True
        # make better when you have time
        except Exception as e:
            print(f"send data exception: {e}")
            return False

    def send_keep_alive(self):
        try:
            self.client_socket.send(b'\x00')
            return True
        # make better when you have time
        except Exception as e:
            print(f"Failed to send keep-alive signal: {e}")
            return False

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

    def receive_keep_alive(self):
        # just receive the keep alive
        try:
            keep_alive = self.client_socket.recv(1)
            if len(keep_alive) == 1:
                return True, None
            else:
                print("Lost keep-alive signal.")
                return False, None
        except Exception as e:
            print(f"Error receiving keep-alive signal: {e}")
            return False, None

    def receive_data(self):
        sequence_bytes = struct.calcsize('<I')
        checksum_bytes = struct.calcsize('<B')

        recv_bytes = sequence_bytes + struct.calcsize(data_type) * self.num_outputs + checksum_bytes
        full_data = self.client_socket.recv(recv_bytes)

        if len(full_data) != recv_bytes:
            print(f"Data received is shorter than expected: {len(full_data)} instead of {recv_bytes}.")
            return None

        # Extract and validate sequence number
        sequence_received, = struct.unpack('<I', full_data[:sequence_bytes])
        print(f"Received sequence number: {sequence_received}")

        # Extract and validate checksum
        received_checksum, = struct.unpack('<B', full_data[-checksum_bytes:])
        computed_checksum = self.compute_checksum(full_data[:-checksum_bytes])

        if received_checksum != computed_checksum:
            print("Checksum mismatch!")
            return None

        decoded_values = [round(struct.unpack(data_type, chunk)[0], 2)
                          for chunk in (full_data[sequence_bytes + i:sequence_bytes + i + struct.calcsize(data_type)]
                                        for i in range(0, len(full_data) - sequence_bytes - checksum_bytes,
                                                       struct.calcsize(data_type)))]
        return decoded_values

    def request_data(self):
        return self.motionplatf_output.read(combine=True)

    def save_data_with_timestamp(self, data):
        try:
            with self.data_save_lock:
                current_timestamp = datetime.datetime.now().timestamp()
                microsecond_timestamp = int(current_timestamp * 1e6)

                timestamped_data = struct.pack('<Q', microsecond_timestamp) + data
                self.data_buffer.append(timestamped_data)

                if len(self.data_buffer) >= BUFFER_SIZE:
                    with open(file_path, 'ab') as f:
                        for value in self.data_buffer:
                            f.write(value)
                    print("saved data to file...")
                    self.data_buffer.clear()
                    return True
        except Exception as e:
            print(f"Error when saving data: {e}")
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

    def handle_data_transmission(self, packed_controller_data):
        if self.num_inputs is None:
            return self.send_keep_alive()
        else:
            return self.send_data(packed_controller_data)

    def handle_data_reception(self):
        if self.num_outputs is None:
            return self.receive_keep_alive()
        else:
            return self.receive_data()

    def mainloop(self):
        print("Starting mainloop...")
        sleep(3)
        try:
            while True:
                controller_data = self.request_data()
                if controller_data is None:
                    print("No controller data available!")
                    break

                packed_controller_data = self.pack_data(controller_data)
                send_success = self.handle_data_transmission(packed_controller_data)
                if not send_success:
                    break

                recv_success, received_data = self.handle_data_reception()
                if not recv_success:
                    break

                # things could happen here...
                sleep(loop_delay)

        except Exception as e:
            print(f"\nClient handler Error with {self.addr}: {e}")
        finally:
            self.client_socket.close()
            # add other cleanups!!!!!
            sleep(3)
            self.read_data_file()

    def handshake(self):
        try:
            data = self.client_socket.recv(12)  # 3x4 bytes
            decoded_data = struct.unpack('<3i', data)

            self.is_mevea = decoded_data[0]
            self.num_outputs = decoded_data[1]
            self.num_inputs = decoded_data[2]
            # etc etc add self to rest

            if self.is_mevea == 0:
                print(f"Handshake received from Excavator ({self.addr}) with {self.num_inputs} inputs and {self.num_outputs} outputs.")

            elif self.is_mevea == 1:
                print(f"Handshake received from Mevea ({self.addr}) with {self.num_inputs} inputs and {self.num_outputs} outputs.")

            elif self.is_mevea > 1:
                print(f"Unknown handshake received from {self.addr} with {self.num_inputs} inputs and {self.num_outputs} outputs.")
                return False

            response = struct.pack('<3i', self.is_mevea, self.num_inputs, self.num_outputs)
            self.client_socket.send(response)
            print(f"Handshake done with Address: {self.addr}\n")

        except socket.timeout:
            print(f"Handshake timeout with {self.addr}")
            return False
        except Exception as e:
            print(f"\nHandshake Error with {self.addr}: {e}")
            return False

        # Convert 0 to None
        self.num_outputs = None if self.num_outputs == 0 else self.num_outputs
        self.num_inputs = None if self.num_inputs == 0 else self.num_inputs
        return True


if __name__ == "__main__":
    try:
        with open(file_path, 'wb') as file:
            pass
    except Exception as e:
        pass

    client = MotionPlatformClient(simulation_mode=True)
    client.run_server()
