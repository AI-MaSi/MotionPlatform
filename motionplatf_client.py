import socket
import struct
from time import sleep
import datetime
import threading

import motionplatf_controls
import read_bin


delay = 0.05

# Lock needed if using multiple threads in the future
data_save_lock = threading.Lock()

data_buffer = []
BUFFER_SIZE = 100
sequence_number = 0
file_name = "/log/motionplatf_data.bin"

motionplatf_output = motionplatf_controls.DataOutput(simulation_mode=False, decimals=3)


def compute_checksum(data):
    checksum = 0
    for byte in data:
        checksum ^= byte
    return checksum


def send_data(server_socket, values):
    global sequence_number

    try:
        full_data = values

        # Append the sequence number to the beginning of the full data
        sequence_data = struct.pack('<I', sequence_number)  # I is for an unsigned int
        full_data = sequence_data + full_data

        # Compute the checksum and append it to the end
        checksum = compute_checksum(full_data)
        full_data += struct.pack('<B', checksum)  # B is for an unsigned char


        server_socket.send(full_data)

        sequence_number += 1
        return True

    except Exception as e:
        print(f"send data exception: {e}")
        return False


def send_keep_alive(server_socket):
    try:
        server_socket.send(b'\x00')
        return True
    except Exception as e:
        print(f"Failed to send keep-alive signal: {e}")
        return False


def receive_keep_alive(server_socket):
    # just receive the keep alive

    keep_alive = server_socket.recv(1)
    if len(keep_alive) == 1:
        return True, None
    else:
        print("Lost keep-alive signal.")
        return False, None


def receive_data(server_socket, num_outputs, data_type='<d'):
    sequence_bytes = struct.calcsize('<I')
    checksum_bytes = struct.calcsize('<B')

    recv_bytes = sequence_bytes + struct.calcsize(data_type) * num_outputs + checksum_bytes
    full_data = server_socket.recv(recv_bytes)

    if len(full_data) != recv_bytes:
        print(f"Data received is shorter than expected: {len(full_data)} instead of {recv_bytes}.")
        return None

    # Extract and validate sequence number
    sequence_received, = struct.unpack('<I', full_data[:sequence_bytes])

    # sequence check here

    print(f"Received sequence number: {sequence_received}")

    # Extract and validate checksum
    received_checksum, = struct.unpack('<B', full_data[-checksum_bytes:])
    computed_checksum = compute_checksum(full_data[:-checksum_bytes])

    if received_checksum != computed_checksum:
        print("Checksum mismatch!")
        return None

    decoded_values = [round(struct.unpack(data_type, chunk)[0], 2)
                      for chunk in (full_data[sequence_bytes + i:sequence_bytes + i + struct.calcsize(data_type)]
                                    for i in range(0, len(full_data) - sequence_bytes - checksum_bytes,
                                                   struct.calcsize(data_type)))]
    return decoded_values


def request_data():
    # if pack=True, the data is packed with struct. 8+12 doubles
    #print(motionplatf_output.read(combine=True, pack=False))
    return motionplatf_output.read(combine=True, pack=True)


def save_data_with_timestamp(data):
    global data_buffer

    try:
        with data_save_lock:
            current_timestamp = datetime.datetime.now().timestamp()  # get UNIX timestamp including fractional seconds
            # Convert the float timestamp to a format that retains the microsecond precision
            # (e.g. multiply by 1e6 and cast to an integer)
            microsecond_timestamp = int(current_timestamp * 1e6)

            # append the timestamp to the data
            timestamped_data = struct.pack('<Q', microsecond_timestamp) + data  # Q is for an unsigned long
            data_buffer.append(timestamped_data)

            if len(data_buffer) >= BUFFER_SIZE:
                with open(file_name, 'ab') as f:
                    for value in data_buffer:
                        f.write(value)
                print("saved data to file...")
                data_buffer.clear()
                return True
    except Exception as e:
        print(f"Error when saving data: {e}")
        return False


def save_remaining_data(entry_size=20):
    # If there's remaining data in the buffer, save it to file
    if data_buffer:
        with open(file_name, 'ab') as f:
            for value in data_buffer:
                missing_values = entry_size - (len(value) // 8 - 1)  # subtract 1 for the timestamp
                value += struct.pack('<{}d'.format(missing_values), *([0.0] * missing_values)) # 0.0 doubles
                f.write(value)
        data_buffer.clear()
        print("\nSaved remaining data. Printing it in couple seconds...")


# The code loops here
def client_handler(client_socket, addr, num_inputs, num_outputs, is_mevea):
    # is is_mevea needed anymore?
    try:
        while True:
            # Send data to Excavator
            data_for_excavator = request_data()
            if data_for_excavator is None:
                print("No data available for sending!")
                break

            if is_mevea == 0:
                if num_inputs is None:
                    send_success = send_keep_alive(client_socket)
                else:
                    send_success = send_data(client_socket, data_for_excavator)

                save_data_with_timestamp(data_for_excavator)  # Save the inputs data
                if not send_success:
                    break

                # Receive response data from Excavator
                if num_outputs is None:
                    recv_success, received_data = receive_keep_alive(client_socket)
                else:
                    recv_success, received_data = receive_data(client_socket, num_outputs)
                    pass

                sleep(delay)

                if not recv_success:
                    break

    except Exception as e:
        print(f"\nClient handler Error with {addr}: {e}")
        client_socket.close()
    finally:
        save_remaining_data()
        client_socket.close()
        sleep(3)

        # '<Q20d' timestamp integer + 20 input doubles. Little endian

        read_bin.read(file_path=file_name, format_str='<Q20d')
        quit()


def handshake(server_socket, addr):
    try:
        data = server_socket.recv(12)  # 3x4 bytes
        decoded_data = struct.unpack('<3i', data)

        is_mevea = decoded_data[0]
        num_outputs = decoded_data[1]
        num_inputs = decoded_data[2]

        if is_mevea == 0:
            print(f"Handshake received from Excavator ({addr}) with {num_inputs} inputs and {num_outputs} outputs.")


        elif is_mevea == 1:
            print(f"Handshake received from Mevea ({addr}) with {num_inputs} inputs and {num_outputs} outputs.")


        elif is_mevea > 1:
            print(f"Unknown handshake received from {addr} with {num_inputs} inputs and {num_outputs} outputs.")
            server_socket.close()  # Close the socket to end the connection
            return False, None, None, None


        response = struct.pack('<3i', is_mevea, num_inputs, num_outputs)
        server_socket.send(response)
        print(f"Handshake done with Address: {addr}\n")

    except socket.timeout:
        print(f"Handshake timeout with {addr}")
        return False, None, None, None
    except Exception as e:
        print(f"\nHandshake Error with {addr}: {e}")
        return False, None, None, None

    # Convert 0 to None
    if num_outputs == 0:
        num_outputs = None
    if num_inputs == 0:
        num_inputs = None

    return True, num_inputs, num_outputs, is_mevea


def main():
    # this takes the wrong network card
    # host = socket.gethostbyname(socket.gethostname())
    # host = '127.0.0.1'
    host = '10.214.5.110'
    port = 5111

    # Clear the file
    try:
        with open(file_name, 'wb') as file:
            pass
    except Exception as e:
        pass

    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((host, port))

        server_socket.listen(1)  # Only Excavator expected now
        print(f"\nServer listening on {host}:{port}")

        while True:
            client_socket, addr = server_socket.accept()
            print(f"\nConnected to {addr}")

            handshake_success, num_inputs, num_outputs, is_mevea = handshake(client_socket, addr)
            if handshake_success:
                input("send any key to start the simulation loop...")

                client_handler(client_socket, addr, num_inputs, num_outputs, is_mevea)

    except Exception as e:
        print(f"\nSocket connection Error: {e}")


if __name__ == "__main__":
    main()
