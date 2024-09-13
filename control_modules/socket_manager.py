import asyncio
import struct
from typing import List, Optional, Tuple

class AsyncSocketManager:
    def __init__(self, inputs: Optional[int], outputs: Optional[int]):
        self.num_inputs = inputs or 0
        self.num_outputs = outputs or 0
        self.latest_received_data = [0.0] * self.num_inputs if self.num_inputs > 0 else None
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.protocol: Optional['UDPProtocol'] = None
        self.remote_addr: Optional[Tuple[str, int]] = None

        # Data format
        self.ENDIAN_SPECIFIER = '<'  # Little-endian
        self.DATA_FORMAT = 'f'  # 4-byte float for data
        self.data_size = struct.calcsize(f"{self.ENDIAN_SPECIFIER}{self.DATA_FORMAT}")

    async def setup(self, local_addr: Tuple[str, int], remote_addr: Optional[Tuple[str, int]] = None):
        loop = asyncio.get_running_loop()
        self.transport, self.protocol = await loop.create_datagram_endpoint(
            lambda: UDPProtocol(self),
            local_addr=local_addr,
            remote_addr=remote_addr
        )
        self.remote_addr = remote_addr
        print(f"UDP socket set up on {self.transport.get_extra_info('sockname')}")

    def send_data(self, data: List[float]):
        if len(data) != self.num_outputs:
            raise ValueError(f"Expected {self.num_outputs} values, got {len(data)}")
        packed_data = struct.pack(f"{self.ENDIAN_SPECIFIER}{self.DATA_FORMAT * len(data)}", *data)
        if self.remote_addr:
            self.transport.sendto(packed_data, self.remote_addr)
        else:
            print("No remote address set for sending data")

    def receive_data(self, data: bytes, addr: Tuple[str, int]):
        if len(data) != self.data_size * self.num_inputs:
            print(f"Received data of unexpected size: {len(data)} bytes")
            return
        unpacked_data = struct.unpack(f"{self.ENDIAN_SPECIFIER}{self.DATA_FORMAT * self.num_inputs}", data)
        self.latest_received_data = list(unpacked_data)
        # You can add additional processing or callback here if needed

    def get_latest_data(self) -> Optional[List[float]]:
        return self.latest_received_data

    def close(self):
        if self.transport:
            self.transport.close()

class UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, socket_manager: AsyncSocketManager):
        self.socket_manager = socket_manager

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        self.socket_manager.receive_data(data, addr)

"""
# Example usage
async def main():
    # Control socket (for sending)
    control_socket = AsyncSocketManager(inputs=None, outputs=31)
    await control_socket.setup(local_addr=('0.0.0.0', 5000), remote_addr=('127.0.0.1', 5001))

    # Sensor socket (for receiving)
    sensor_socket = AsyncSocketManager(inputs=20, outputs=None)
    await sensor_socket.setup(local_addr=('0.0.0.0', 5001))

    # Example: Send control data
    control_data = [0.1] * 31  # 31 float values
    control_socket.send_data(control_data)

    # Example: Receive sensor data (non-blocking)
    sensor_data = sensor_socket.get_latest_data()
    if sensor_data:
        print(f"Received sensor data: {sensor_data}")

    # Keep the sockets open for a while
    await asyncio.sleep(10)

    # Close the sockets
    control_socket.close()
    sensor_socket.close()

if __name__ == "__main__":
    asyncio.run(main())
    """