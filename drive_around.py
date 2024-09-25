# UPD / TCP hybrid connection demo
# handshake with TCP, data transmission with UDP
# drive around with the excavator

from control_modules import NiDAQ_controller, socket_manager
from time import sleep


addr = '192.168.0.136'

port = 5111


# Who am I. Check config for names
identification_number = 2  # 0 excavator, 1 Mevea, 2 Motion Platform, more can be added...
# My (num) inputs I want to receive
inputs = 0
# My (num) outputs im going to send
outputs = 20


# Frequency of the send/receive loop in Hz
# 20Hz ~50ms        As of 17.4.2024, the ISM330DHCX are set to 26Hz max
# 50Hz ~20ms.       PWM controlled servos live in this area
# 60Hz ~17ms        ADCpi max read speed at 14-bit
# 200Hz ~5ms etc.
loop_frequency = 20 # hz

# For saving bandwidth
# 1-byte signed int goes from -128 to 127
int_scale = 127


# init joysticks in simulation mode
motionplatf_output = NiDAQ_controller.NiDAQJoysticks(simulation_mode=False)


# init socket
socket = socket_manager.MasiSocketManager()


# set up Motion Platform as client. set connect_addr if client and TCP
if not socket.setup_socket(addr, port, identification_number, inputs, outputs, socket_type='client'):
    raise Exception("could not setup socket!")

# setup done

# when not communicating with Mevea, you are able to send three extra arguments
# example: send used loop_frequency for safety, int_scale for bandwidth saving and local_datatype for data type (we are sending integers)
handshake_result, extra_args = socket.handshake(extra_arg1=loop_frequency, extra_arg2=int_scale, local_datatype='int')

if not handshake_result:
    raise Exception("could not make handshake!")

# switcheroo
socket.tcp_to_udp()

sleep(10)


def float_to_int(data, scale=int_scale):  # using 1-byte unsigned int, mapped -1 to +1. A bit ghetto but basically works with dinosaur-era networking
    int_data = []  # List to store converted integer values

    for value in data:
        clamped_value = max(-1.0, min(1.0, value))
        int_value = int(clamped_value * scale)
        int_data.append(int_value)

    return int_data


def run():
    while True:
        # read values from joysticks. Combine AI (8) and DI (12) data. 20 values to output in total.
        joystick_data = motionplatf_output.read(combine=True)

        # to save bandwidth, convert -1...1 floating point numbers (4-8 bytes) to -100...100 ints (1 byte)
        # we do the reverse on the receiving end
        # this is a simple way to save bandwidth, but it limits the precision of the values
        int_joystick_data = float_to_int(joystick_data)

        socket.send_data(int_joystick_data)
        print(f"Sent: {int_joystick_data}")


        sleep(1/loop_frequency) # rough polling rate


# TODO: Async for send/receive. UDP client 1 for sending, UDP client 2 for receiving


if __name__ == "__main__":
    run()
