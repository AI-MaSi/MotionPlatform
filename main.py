import threading
from time import sleep
import motionplatf_client
from config import loop_delay

simulation_mode = True
client = motionplatf_client.MotionPlatformClient(simulation_mode=simulation_mode)

def handle_buttons():
    i = 0
    while True:
        buttons = client.request_data()

        if buttons[11]:
            client.send_start_flag()

        if buttons[12]:
            client.start_recording_flag()

        if buttons[13]:
            client.send_stop_flag()

        if buttons[14]:
            client.send_start_flag()

        if buttons[15]:
            # this would have better stopping
            break

        sleep(0.02)

def main():
    client.clear_file()
    connected = client.run_server()
    sleep(3)

    if connected:
        button_thread = threading.Thread(target=handle_buttons)
        button_thread.start()

        if simulation_mode:
            client.stop_recording_flag()
            client.send_stop_flag()
            while True:
                # do mainloop stuff here
                client.mainloop()
                sleep(1)

        button_thread.join()

if __name__ == "__main__":
    main()
    client.save_remaining_data()
    client.close_server()
    client.read_data_file()
