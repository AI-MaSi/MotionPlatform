"""
ROS2 joystick publisher node — NiDAQ input.

!! NOT TESTED — verify topics, types and timing before use !!

NOTE: For LTE / long-distance teleop this node is NOT the recommended approach.
ROS2 DDS overhead is ~200-500 bytes/msg vs ~10 bytes for the custom UDP protocol,
making it ~30x heavier over the air. Preferred architecture:
    operator PC  →  lean UDP (main.py / komatsu_main.py)  →  LTE  →  robot
    robot side   →  local UDP-to-ROS2 relay node          →  internal ROS2 topics
This node is useful only when the operator machine is on the same LAN as the robot.

Topics published:
    ~/joystick/axes    (std_msgs/Int8MultiArray)  — 8 AI channels, int8 [-128, 127]
    ~/joystick/buttons (std_msgs/Int8MultiArray)  — 12 DI channels, int8 {0, 127}

Parameters:
    deadzone      (float, default 1.5)   — deadzone in %
    padding       (float, default 2.5)   — edge padding in %
    publish_rate  (float, default 100.0) — publish rate in Hz

Usage:
    ros2 run <package> joystick_ros2_node
    ros2 run <package> joystick_ros2_node --ros-args -p publish_rate:=50.0
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int8MultiArray

from modules.NiDAQ_controller import NiDAQJoysticks, OutputFormat


class JoystickPublisher(Node):
    def __init__(self):
        super().__init__('joystick_publisher')

        self.declare_parameter('deadzone', 1.5)
        self.declare_parameter('padding', 2.5)
        self.declare_parameter('publish_rate', 100.0)

        deadzone = self.get_parameter('deadzone').value
        padding = self.get_parameter('padding').value
        rate = self.get_parameter('publish_rate').value

        self.controller = NiDAQJoysticks(
            output_format=OutputFormat.INT8,
            deadzone=deadzone,
            padding=padding,
        )

        self.pub_ai = self.create_publisher(Int8MultiArray, 'joystick/axes', 10)
        self.pub_di = self.create_publisher(Int8MultiArray, 'joystick/buttons', 10)
        self.timer = self.create_timer(1.0 / rate, self._publish)

        self.get_logger().info(
            f'Joystick publisher started at {rate:.0f} Hz '
            f'(deadzone={deadzone}%, padding={padding}%)'
        )

    def _publish(self):
        data = self.controller.read()
        self.pub_ai.publish(Int8MultiArray(data=data.ai))
        self.pub_di.publish(Int8MultiArray(data=data.di))

    def destroy_node(self):
        self.controller.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = JoystickPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
