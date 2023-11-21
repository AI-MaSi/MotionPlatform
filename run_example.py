import motionplatf_controls
import universal_socket_manager
from time import sleep

simulation_mode = True

# init joysticks
try:
    motionplatf_output = motionplatf_controls.DataOutput(simulation_mode=simulation_mode, decimals=3)
except motionplatf_controls.NiDAQmxInitializationError as e:
    motionplatf_output = None
    raise e


# init socket
manager = universal_socket_manager.MasiSocketManager()


def setup_example():
    # these could be set in GUI
    # manager.setup_socket(addr, port, client_type='server')

    setup_result = manager.setup_socket(socket_type='server')
    if not setup_result:
        print("could not setup socket!")
        sleep(3)
        return

    handshake_result = manager.handshake()
    sleep(5)

    if not handshake_result:
        print("could not make handshake!")
        sleep(3)
        return


def run_example():
    while True:
        try:
            # read values from joysticks
            data_i_want_to_send = motionplatf_output.read(combine=True)
            print(data_i_want_to_send)
            # send joystick values
            packed_sent_data = manager.send_data(data_i_want_to_send)
            # add joystick values to buffer
            data_i_want_to_save = packed_sent_data
            manager.add_data_to_buffer(data_i_want_to_save)

            # Receive handshake (or data)
            data_i_want_to_receive = manager.receive_data()
            print(f"Received: {data_i_want_to_receive}")

            # do stuff with the data here. For now just print the handshake
            sleep(1)

        except KeyboardInterrupt:
            manager.close_socket()
            return


if __name__ == "__main__":
    setup_example()
    run_example()
