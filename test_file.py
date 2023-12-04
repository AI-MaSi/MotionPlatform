import motionplatf_controls
import universal_socket_manager
from time import sleep, time

simulation_mode = False

# Frequency of the send/receive loop in Hz
# 20Hz ~50ms
# 60Hz ~17ms
# 200Hz ~5ms
loop_frequency = 20

# init joysticks
motionplatf_output = motionplatf_controls.DataOutput(simulation_mode=simulation_mode, decimals=3)


# init socket
manager = universal_socket_manager.MasiSocketManager()

def setup():
    manager.clear_file()

    setup_result = manager.setup_socket(socket_type='server')
    if not setup_result:
        print("could not setup socket!")
        return
    handshake_result = manager.handshake()


    if not handshake_result:
        print("could not make handshake!")
        return
    return True


def run():
    while True:
        loop_start_time = time()
        # read values from joysticks
        joystick_data = motionplatf_output.read(combine=True)

        try:
            # send joystick data
            packed_sent_data = manager.send_data(joystick_data)

            #add to buffer
            manager.add_data_to_buffer(packed_sent_data)

            # Receive handshake
            keep_alive = manager.receive_data()
            if not keep_alive:
                print("no keep alive received!")
                break

            # Calculate actual sleep time
            time_elapsed = time() - loop_start_time
            sleep_time = max(0, (1.0 / loop_frequency) - time_elapsed)
            sleep(sleep_time)
        except (Exception, KeyboardInterrupt) as e:
            manager.save_remaining_data(num_doubles=20)
            print(e)
            manager.print_bin_file(num_doubles=20)
            manager.close_socket()
            sleep(1)
            break


if __name__ == "__main__":
    if setup():
        run()