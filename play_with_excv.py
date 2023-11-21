# simple code to drive around with the Excavator

import motionplatf_controls
import universal_socket_manager
from time import sleep

simulation_mode = False

# init joysticks
try:
    motionplatf_output = motionplatf_controls.DataOutput(simulation_mode=simulation_mode, decimals=3)
except motionplatf_controls.NiDAQmxInitializationError as e:
    motionplatf_output = None
    raise e


# init socket
manager = universal_socket_manager.MasiSocketManager()


def setup():
    setup_result = manager.setup_socket(socket_type='server')
    if not setup_result:
        print("could not setup socket!")
        return
    handshake_result = manager.handshake()
    sleep(2)

    if not handshake_result:
        print("could not make handshake!")
        sleep(3)
        return


def run():
    while True:
        try:
            # read values from joysticks
            joystick_data = motionplatf_output.read(combine=True)

            packed_sent_data = manager.send_data(joystick_data)

            # Receive handshake
            keep_alive = manager.receive_data()
            if not keep_alive:
                sleep(2)
                break
            sleep(0.02)
        except Exception:
            manager.close_socket()
            break


if __name__ == "__main__":
    setup()
    run()
