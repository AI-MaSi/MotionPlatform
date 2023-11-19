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

try:
    # init socket
    manager = universal_socket_manager.MasiSocketManager()
except Exception as e:
    print("make exceptions!")

def setup_example():
    # these could be set in GUI
    # manager.setup_socket(addr, port, client_type='server')

    setup_result = manager.setup_socket(client_type='server')
    if not setup_result:
        print("could not setup socket!")
        sleep(3)
        return

    print("starting handshake...")
    sleep(2)
    handshake_result = manager.handshake()
    sleep(5)
    if not handshake_result:
        print("could not setup socket!")
        sleep(3)
        return


def run_example():
    # just set flags to True
    manager.set_start_flag(True)
    manager.set_record_flag(True)

    while True:
        data_i_want_to_send = motionplatf_output.read(combine=True)
        manager.send_data(data_i_want_to_send)

        data_i_want_to_receive = manager.receive_data()
        print(f"Received: {data_i_want_to_receive}")

        sleep(1)


if __name__ == "__main__":
    setup_example()
    run_example()