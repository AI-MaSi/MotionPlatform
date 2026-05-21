from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            Node(
                package="nidaq_joystick_ros2",
                executable="nidaq_joystick_node",
                name="nidaq_joystick_node",
                output="screen",
                parameters=[
                    {
                        "device_name": "Dev2",
                        "publish_rate_hz": 100.0,
                        "deadzone_percent": 1.5,
                        "padding_percent": 2.5,
                        "min_voltage": 0.5,
                        "max_voltage": 4.5,
                        "frame_id": "nidaq_joystick",
                        "topic_name": "joy",
                        "invert_axes": [
                            False,
                            True,
                            False,
                            False,
                            False,
                            False,
                            False,
                            False,
                        ],
                    }
                ],
            )
        ]
    )
