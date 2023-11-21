import motionplatf_controls
import universal_socket_manager
from time import sleep, time

simulation_mode = False

# Frequency of the send/receive loop in Hz (e.g., 10 Hz)
loop_frequency = 10

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
        loop_start_time = time()

        try:
            # read values from joysticks
            joystick_data = motionplatf_output.read(combine=True)
            packed_sent_data = manager.send_data(joystick_data)

            # Receive handshake
            keep_alive = manager.receive_data()
            if not keep_alive:
                sleep(2)
                break

            # Calculate actual sleep time
            time_elapsed = time() - loop_start_time
            sleep_time = max(0, (1.0 / loop_frequency) - time_elapsed)
            sleep(sleep_time)
        except Exception:
            manager.close_socket()
            break


if __name__ == "__main__":
    setup()
    run()
