# UPD / TCP hybrid connection demo
# handshake with TCP, data transmission with UDP

import motionplatf_controls
import universal_connection_manager
from time import sleep


addr = '127.0.0.1'
port = 5111


# Who am I. Check config for names
identification_number = 2  # 0 excavator, 1 Mevea, 2 Motion Platform, more can be added...
# My (num) inputs I want to receive
inputs = 0
# My (num) outputs im going to send
outputs = 20


# Frequency of the send/receive loop in Hz
# 20Hz ~50ms
# 60Hz ~17ms
# 200Hz ~5ms etc.
loop_frequency = 1


# init joysticks in simulation mode
motionplatf_output = motionplatf_controls.DataOutput(simulation_mode=True)


# init socket
masi_manager = universal_connection_manager.MasiSocketManager(identification_number, inputs, outputs)


# set up Motion Platform as client. set connect_addr if client and TCP
if not masi_manager.setup_socket(addr, port, socket_type='client'):
    raise Exception("could not setup socket!")

# setup done

# when not communicating with Mevea, you are able to send three extra arguments
# example: send used loop_frequency
handshake_result, extra_args = masi_manager.handshake(extra_arg1=loop_frequency)

if not handshake_result:
    raise Exception("could not make handshake!")

# switcheroo
masi_manager.tcp_to_udp()

# handshake is done, just wait a while before starting as the Excavator is currently printing debug prints
#sleep(5)


def run():


    while True:
        # read values from joysticks. Combine AI (8) and DI (12) data. 20 values to output in total.
        joystick_data = motionplatf_output.read(combine=True)

        masi_manager.send_data(joystick_data)
        print(f"Sent: {joystick_data}")

        sleep(1/loop_frequency)


if __name__ == "__main__":
    run()
