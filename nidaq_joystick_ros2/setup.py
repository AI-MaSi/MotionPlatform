from glob import glob
from setuptools import find_packages, setup

package_name = "nidaq_joystick_ros2"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="MotionPlatform",
    maintainer_email="user@example.com",
    description="ROS 2 Jazzy node for publishing National Instruments DAQ joystick channels.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "nidaq_joystick_node = nidaq_joystick_ros2.nidaq_joystick_node:main",
        ],
    },
)
