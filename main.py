from modules.NiDAQ_controller import NiDAQJoysticks
from modules.udp_socket import UDPSocket
from time import sleep


joy = NiDAQJoysticks(output_format="int8", deadzone=1.5, padding=2.5)
client = UDPSocket(local_id=1, max_age_seconds=0.5)
client.setup(host="192.168.0.132", port=8080, num_inputs=0, num_outputs=10, is_server=False)

if client.handshake(timeout=30.0):

    while True:
        axis, buttons = joy.read()

        if axis is not None:

            right_lr = axis[0]
            right_ud = -axis[1]
            right_rocker = axis[2]
            left_lr = axis[3]
            left_ud = axis[4]
            left_rocker = axis[5]
            right_paddle = axis[6]
            left_paddle = axis[7]

            button_0 = buttons[9]  # left top red button

            button_1 = buttons[0] # right rocker U/D
            button_2 = buttons[1]

            button_3 = buttons[3] # figure out what this button is haha

            #print(right_lr)

            success = client.send([button_0, button_1, button_2, button_3,
                         left_paddle, right_paddle,
                         left_ud,left_lr,
                         right_ud,right_lr
                         ])

            if not success:
                break

        sleep(0.08) # 125hsim   z ish

