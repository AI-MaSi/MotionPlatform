from time import sleep
import motionplatf_client
from config import loop_delay

client = motionplatf_client.MotionPlatformClient(simulation_mode=True)

def main():
    # clears the .bin file
    client.clear_file()

    # sets up the server, and makes the handshake with the client
    connected = client.run_server()
    if connected:
        # server has connected, you could do stuff here
        """"
        while True:
            # joystick buttons for starting / stopping etc.
            buttons = client.request_data()
            print(buttons)
            sleep(1)
        """
        # starts the send / recv loop
        while True:
            try:
                client.mainloop()
                sleep(loop_delay)
            except KeyboardInterrupt:
                break





if __name__ == "__main__":
    main()
    # finally?
    client.save_remaining_data()
    client.close_server()
    client.read_data_file()
