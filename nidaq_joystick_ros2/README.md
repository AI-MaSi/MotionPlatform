# nidaq_joystick_ros2

ROS 2 Jazzy Python package that publishes the MotionPlatform National
Instruments DAQ joystick inputs as `sensor_msgs/msg/Joy`.

The package is standalone and does not import or modify the original
MotionPlatform files.

## Published message

Default topic: `/joy`

- `axes[0..7]`: normalized analog channels from `Dev2/ai0` through `Dev2/ai7`
- `buttons[0..11]`: digital channels from `Dev2/port0/line0..7` and
  `Dev2/port1/line0..3`

Analog normalization matches the MotionPlatform controller logic:

- 0.5 V maps to -1.0
- 4.5 V maps to +1.0
- deadzone and edge padding are applied after normalization

## Build

From a ROS 2 Jazzy workspace:

```bash
mkdir -p ~/ros2_ws/src
cp -r /path/to/MotionPlatform/nidaq_joystick_ros2 ~/ros2_ws/src/
cd ~/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --packages-select nidaq_joystick_ros2
source install/setup.bash
```

Install NI dependencies in the same Python environment used by ROS 2:

```bash
python3 -m pip install nidaqmx
```

The NI-DAQmx driver must also be installed on the host.

## Run

```bash
ros2 launch nidaq_joystick_ros2 nidaq_joystick.launch.py
```

Or run the node directly:

```bash
ros2 run nidaq_joystick_ros2 nidaq_joystick_node --ros-args \
  -p device_name:=Dev2 \
  -p publish_rate_hz:=100.0 \
  -p topic_name:=joy
```

## Useful parameters

- `device_name`: default `Dev2`
- `ai_channels`: explicit analog channel list; defaults to `Dev2/ai0..7`
- `di_channels`: explicit digital channel list; defaults to `Dev2/port0/line0..7`
  plus `Dev2/port1/line0..3`
- `min_voltage`: default `0.5`
- `max_voltage`: default `4.5`
- `deadzone_percent`: default `1.5`
- `padding_percent`: default `2.5`
- `publish_rate_hz`: default `100.0`
- `topic_name`: default `joy`
- `frame_id`: default `nidaq_joystick`
- `invert_axes`: boolean list applied per analog axis

The launch file inverts only `axes[1]`, matching the old `right_ud = -axis[1]`
mapping in `main.py` while still publishing every channel.
