"""ROS 2 node that publishes NI-DAQ joystick channels as sensor_msgs/Joy."""

from __future__ import annotations

from typing import List

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from sensor_msgs.msg import Joy

from nidaq_joystick_ros2.nidaq_reader import (
    NiDaqConfig,
    NiDaqJoystickReader,
    default_ai_channels,
    default_di_channels,
)


class NiDaqJoystickNode(Node):
    """Publish all configured NI-DAQ analog and digital channels."""

    def __init__(self) -> None:
        super().__init__("nidaq_joystick_node")

        self.declare_parameter("device_name", "Dev2")
        self.declare_parameter("ai_channels", Parameter.Type.STRING_ARRAY)
        self.declare_parameter("di_channels", Parameter.Type.STRING_ARRAY)
        self.declare_parameter("min_voltage", 0.5)
        self.declare_parameter("max_voltage", 4.5)
        self.declare_parameter("deadzone_percent", 1.5)
        self.declare_parameter("padding_percent", 2.5)
        self.declare_parameter("publish_rate_hz", 100.0)
        self.declare_parameter("frame_id", "nidaq_joystick")
        self.declare_parameter("topic_name", "joy")
        self.declare_parameter("invert_axes", [False, False, False, False, False, False, False, False])

        device_name = self.get_parameter("device_name").value
        ai_channels = self._string_list_parameter("ai_channels")
        di_channels = self._string_list_parameter("di_channels")
        if not ai_channels:
            ai_channels = default_ai_channels(device_name)
        if not di_channels:
            di_channels = default_di_channels(device_name)

        self._invert_axes = self._bool_list_parameter("invert_axes")
        if len(self._invert_axes) < len(ai_channels):
            self._invert_axes.extend([False] * (len(ai_channels) - len(self._invert_axes)))

        config = NiDaqConfig(
            ai_channels=ai_channels,
            di_channels=di_channels,
            min_voltage=float(self.get_parameter("min_voltage").value),
            max_voltage=float(self.get_parameter("max_voltage").value),
            deadzone_percent=float(self.get_parameter("deadzone_percent").value),
            padding_percent=float(self.get_parameter("padding_percent").value),
        )

        topic_name = str(self.get_parameter("topic_name").value)
        rate_hz = float(self.get_parameter("publish_rate_hz").value)
        if rate_hz <= 0.0:
            raise ValueError("publish_rate_hz must be greater than zero.")

        self._frame_id = str(self.get_parameter("frame_id").value)
        self._reader = NiDaqJoystickReader(config)
        self._publisher = self.create_publisher(Joy, topic_name, 10)
        self._timer = self.create_timer(1.0 / rate_hz, self._publish_joy)

        self.get_logger().info(
            f"Publishing {len(ai_channels)} axes and {len(di_channels)} buttons "
            f"from NI-DAQ device '{device_name}' on '{topic_name}' at {rate_hz:g} Hz"
        )

    def _publish_joy(self) -> None:
        try:
            axes, buttons = self._reader.read()
        except RuntimeError as exc:
            self.get_logger().error(str(exc))
            return

        for index, invert in enumerate(self._invert_axes[: len(axes)]):
            if invert:
                axes[index] = -axes[index]

        message = Joy()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = self._frame_id
        message.axes = axes
        message.buttons = buttons
        self._publisher.publish(message)

    def destroy_node(self) -> None:
        self._reader.close()
        super().destroy_node()

    def _string_list_parameter(self, name: str) -> List[str]:
        value = self.get_parameter(name).value
        if value is None:
            return []
        return [str(item) for item in value]

    def _bool_list_parameter(self, name: str) -> List[bool]:
        value = self.get_parameter(name).value
        if value is None:
            return []
        return [bool(item) for item in value]


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = NiDaqJoystickNode()
        rclpy.spin(node)
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
