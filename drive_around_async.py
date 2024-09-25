import asyncio
import time
from control_modules import NiDAQ_controller, socket_manager

addr = '192.168.0.136'
port = 5111

identification_number = 2  # 0 excavator, 1 Mevea, 2 Motion Platform, more can be added...
inputs = 3  # Number of inputs to receive (sensor data)
outputs = 20  # Number of outputs to send (joystick data)

control_frequency = 20  # Hz for sending control signals
sensor_frequency = 5  # Hz for receiving sensor data

int_scale = 127

# Initialize joysticks in simulation mode
motionplatf_output = NiDAQ_controller.NiDAQJoysticks(simulation_mode=False)

# Initialize socket
socket = socket_manager.MasiSocketManager()


def float_to_int(data, scale=int_scale):
    int_data = []
    for value in data:
        clamped_value = max(-1.0, min(1.0, value))
        int_value = int(clamped_value * scale)
        int_data.append(int_value)
    return int_data


def int_to_float(int_data, decimals=2, scale=int_scale):
    float_data = [round((value / scale), decimals) for value in int_data]
    return float_data


async def setup_connection():
    if not socket.setup_socket(addr, port, identification_number, inputs, outputs, socket_type='client'):
        raise Exception("Could not setup socket!")

    handshake_result, extra_args = socket.handshake(extra_arg1=control_frequency, extra_arg2=int_scale,
                                                    local_datatype='int')

    if not handshake_result:
        raise Exception("Could not make handshake!")

    socket.tcp_to_udp()
    await asyncio.sleep(10)


async def send_control_signals():
    interval = 1.0 / control_frequency
    while True:
        start_time = time.time()

        joystick_data = motionplatf_output.read(combine=True)
        int_joystick_data = float_to_int(joystick_data)
        socket.send_data(int_joystick_data)
        print(f"Sent: {int_joystick_data}")

        elapsed_time = time.time() - start_time
        await asyncio.sleep(max(0, interval - elapsed_time))


async def receive_sensor_data():
    interval = 1.0 / sensor_frequency
    while True:
        start_time = time.time()

        sensor_data = socket.get_latest_received()
        if sensor_data is not None:
            float_sensor_data = int_to_float(sensor_data)
            print(f"Received sensor data: {float_sensor_data}")

        elapsed_time = time.time() - start_time
        await asyncio.sleep(max(0, interval - elapsed_time))


async def main():
    await setup_connection()

    send_task = asyncio.create_task(send_control_signals())
    receive_task = asyncio.create_task(receive_sensor_data())

    await asyncio.gather(send_task, receive_task)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program terminated by user")
    finally:
        socket.stop_all()