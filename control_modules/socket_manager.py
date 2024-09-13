"""
Simplified version of the socket manager.
"""

import socket
import struct
import threading
from typing import List, Tuple, Optional, Callable
import selectors
import time

# Constants
endian_specifier = '<'  # Little-endian
data_format = 'h'  # 2-byte short for data (-32768 to 32767)
checksum_format = 'B'  # 1-byte unsigned char for checksum

class SocketManager:
    def __init__(self, inputs: Optional[int], outputs: Optional[int]):
        self.local_num_inputs = inputs if inputs is not None else 0
        self.local_num_outputs = outputs if outputs is not None else 0

        self.data_lock = threading.Lock()
        self.latest_received_data = [0.0] * self.local_num_inputs if self.local_num_inputs > 0 else None

        self.socket: Optional[socket.socket] = None
        self.local_addr: Optional[Tuple[str, int]] = None
        self.remote_addr: Optional[Tuple[str, int]] = None

        self.socket_type: Optional[str] = None
        self.network_protocol: Optional[str] = None

        self.running: bool = False
        self.connected: bool = False
        self.selector = selectors.DefaultSelector()
        self.event_loop_thread: Optional[threading.Thread] = None
        self.reconnect_thread: Optional[threading.Thread] = None

        # Calculate fixed message sizes
        self.data_bytes = struct.calcsize(f"{endian_specifier}{data_format}") * max(self.local_num_inputs, self.local_num_outputs)
        self.checksum_bytes = struct.calcsize(f"{endian_specifier}{checksum_format}")
        self.total_bytes = self.data_bytes + self.checksum_bytes

        # Callbacks
        self.on_connected: Optional[Callable[[], None]] = None
        self.on_disconnected: Optional[Callable[[], None]] = None

    def setup_socket(self, addr: str, port: int, socket_type: str, protocol: str = 'tcp') -> bool:
        if protocol not in ['tcp', 'udp']:
            print("Invalid protocol!")
            return False

        self.network_protocol = protocol
        self.socket_type = socket_type

        if protocol == 'tcp':
            return self._setup_tcp_socket(addr, port)
        else:  # UDP
            return self._setup_udp_socket(addr, port)

    def _setup_tcp_socket(self, addr: str, port: int) -> bool:
        if self.socket_type == 'client':
            self.remote_addr = (addr, port)
            self._connect_client()
        elif self.socket_type == 'server':
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((addr, port))
            self.socket.listen(1)
            self.local_addr = (addr, port)
            print(f"Server listening on {self.local_addr}")
            self.selector.register(self.socket, selectors.EVENT_READ, self._accept_connection)
        else:
            print("Invalid socket type!")
            return False

        print(f"Socket configured as a TCP-{self.socket_type}!")
        return True

    def _setup_udp_socket(self, addr: str, port: int) -> bool:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if self.socket_type == 'server':
            self.socket.bind((addr, port))
            self.local_addr = (addr, port)
            self.connected = True  # UDP server is always considered connected
            if self.on_connected:
                self.on_connected()
        elif self.socket_type == 'client':
            self.remote_addr = (addr, port)
            self.connected = True  # UDP client is always considered connected
            if self.on_connected:
                self.on_connected()
        else:
            print("Invalid socket type!")
            return False

        self.selector.register(self.socket, selectors.EVENT_READ, self.handle_data)
        print(f"Socket configured as a UDP-{self.socket_type}!")
        return True

    def _connect_client(self):
        if self.network_protocol == 'tcp':
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                self.socket.connect(self.remote_addr)
                self.connected = True
                self.selector.register(self.socket, selectors.EVENT_READ, self.handle_data)
                print(f"Connected to server at {self.remote_addr}")
                if self.on_connected:
                    self.on_connected()
            except ConnectionRefusedError:
                print(f"Connection to {self.remote_addr} failed. Will retry...")
                self.connected = False
                if self.on_disconnected:
                    self.on_disconnected()
        else:  # UDP
            if not self.socket:
                self._setup_udp_socket(*self.remote_addr)

    def _accept_connection(self, server_socket):
        client_socket, client_addr = server_socket.accept()
        print(f"Accepted connection from {client_addr}")
        self.selector.register(client_socket, selectors.EVENT_READ, self.handle_data)
        self.connected = True
        if self.on_connected:
            self.on_connected()

    @staticmethod
    def pack_data(data: List[float]) -> bytes:
        """Pack float data into bytes, quantizing to 16-bit integers."""
        int_data = [int(max(-1.0, min(1.0, value)) * 32767) for value in data]
        return struct.pack(f"{endian_specifier}{data_format * len(int_data)}", *int_data)

    @staticmethod
    def unpack_data(packed_data: bytes) -> List[float]:
        """Unpack bytes into float data, de-quantizing from 16-bit integers."""
        int_data = struct.unpack(f"{endian_specifier}{data_format * (len(packed_data) // 2)}", packed_data)
        return [value / 32767.0 for value in int_data]

    @staticmethod
    def add_checksum(packed_data: bytes) -> bytes:
        """Add checksum to packed data."""
        checksum = sum(packed_data) & 0xFF  # Simple 8-bit sum
        return packed_data + struct.pack(f"{endian_specifier}{checksum_format}", checksum)

    def verify_checksum(self, data_with_checksum: bytes) -> Tuple[bool, bytes]:
        """Verify checksum and return data without checksum if valid."""
        data = data_with_checksum[:-self.checksum_bytes]
        received_checksum = struct.unpack(f"{endian_specifier}{checksum_format}",
                                          data_with_checksum[-self.checksum_bytes:])[0]
        calculated_checksum = sum(data) & 0xFF
        return received_checksum == calculated_checksum, data

    def send_data(self, data: List[float]) -> None:
        """Pack, add checksum, and send data."""
        if self.local_num_outputs == 0:
            #print("No outputs configured. Not sending any data.")
            return

        if len(data) != self.local_num_outputs:
            raise ValueError(f"Expected {self.local_num_outputs} values, got {len(data)}")

        packed_data = self.pack_data(data)
        final_data = self.add_checksum(packed_data)

        try:
            if self.network_protocol == 'tcp':
                self.socket.send(final_data)
            else:
                self.socket.sendto(final_data, self.remote_addr)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            print("Connection lost. Attempting to reconnect...")
            self.connected = False
            if self.on_disconnected:
                self.on_disconnected()

    def handle_data(self, sock):
        """Handle incoming data from the socket."""
        if self.local_num_inputs == 0:
            #print("No inputs configured. Not handling any incoming data.")
            return

        try:
            if self.network_protocol == 'tcp':
                data_with_checksum = sock.recv(self.total_bytes)
                if not data_with_checksum:
                    raise ConnectionResetError
            else:  # UDP
                data_with_checksum, addr = sock.recvfrom(self.total_bytes)
                if self.socket_type == 'server':
                    self.remote_addr = addr

            if len(data_with_checksum) != self.total_bytes:
                print(f"Received incomplete data: expected {self.total_bytes} bytes, got {len(data_with_checksum)}")
                return

            is_valid, data = self.verify_checksum(data_with_checksum)
            if not is_valid:
                print("Checksum verification failed")
                return

            unpacked_data = self.unpack_data(data)
            with self.data_lock:
                self.latest_received_data = unpacked_data

        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            print("Connection lost.")
            self.connected = False
            if self.on_disconnected:
                self.on_disconnected()
            if self.network_protocol == 'tcp':
                self.selector.unregister(sock)
                sock.close()
                if self.socket_type == 'client':
                    print("Attempting to reconnect...")
                elif self.socket_type == 'server':
                    print("Waiting for new connection...")

    def get_latest_data(self) -> Optional[List[float]]:
        """Get the latest received data."""
        with self.data_lock:
            return self.latest_received_data.copy() if self.latest_received_data is not None else None


    def start(self):
        """Start the event loop for data reception and reconnection attempts."""
        if self.event_loop_thread is None or not self.event_loop_thread.is_alive():
            self.running = True
            self.event_loop_thread = threading.Thread(target=self.event_loop, daemon=True)
            self.event_loop_thread.start()
            if self.socket_type == 'client' and self.network_protocol == 'tcp':
                self.reconnect_thread = threading.Thread(target=self.reconnect_loop, daemon=True)
                self.reconnect_thread.start()
            print("Started event loop for data reception!")
        else:
            print("Event loop is already running.")

    def stop(self):
        """Stop the event loop for data reception and reconnection attempts."""
        self.running = False
        if self.event_loop_thread is not None:
            self.event_loop_thread.join()
            self.event_loop_thread = None
        if self.reconnect_thread is not None:
            self.reconnect_thread.join()
            self.reconnect_thread = None

    def event_loop(self):
        """Run the event loop for data reception."""
        while self.running:
            events = self.selector.select(timeout=1)
            for key, _ in events:
                callback = key.data
                callback(key.fileobj)

    def reconnect_loop(self):
        """Attempt to reconnect if the connection is lost (client only)."""
        while self.running:
            if not self.connected:
                self._connect_client()
            time.sleep(5)  # Wait 5 seconds between reconnection attempts

    def close(self):
        """Close the socket connection and clean up resources."""
        self.stop()
        if self.socket:
            self.selector.unregister(self.socket)
            self.socket.close()
        self.selector.close()
        print("Socket closed and resources cleaned up successfully!")

    def set_connected_callback(self, callback: Callable[[], None]):
        """Set the callback function to be called when a connection is established."""
        self.on_connected = callback

    def set_disconnected_callback(self, callback: Callable[[], None]):
        """Set the callback function to be called when a connection is lost."""
        self.on_disconnected = callback



"""
Usage example:

def on_connected():
    print("Connection established!")
    # Perform any necessary actions when connected

def on_disconnected():
    print("Connection lost!")
    # Perform any necessary actions when disconnected

socket_manager = SocketManager(inputs=4, outputs=4)
socket_manager.set_connected_callback(on_connected)
socket_manager.set_disconnected_callback(on_disconnected)
socket_manager.setup_socket("localhost", 12345, "client", "tcp")
socket_manager.start()
"""