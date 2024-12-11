import asyncio
import time
from control_modules import socket_manager, joystick_module, NiDAQ_controller
import json
from aiohttp import web

# Refined drive demo with Xbox controller input and motion platform mapping
addr = '192.168.0.136'
port = 5111
web_port = 8080  # Port for the web interface

identification_number = 69  # 0 excavator, 1 Mevea, 2 Motion Platform, more can be added...
inputs = 18  # Number of inputs to receive (3 IMUs * 6 values each)
outputs = 20  # Number of outputs to send (joystick data)

control_frequency = 15  # Hz for sending control signals
int_scale = 127

# Initialize Xbox controller
xbox_controller = joystick_module.XboxController()

# Initialize motion platform controller
motion_controller = NiDAQ_controller.NiDAQJoysticks(simulation_mode=False)

# Initialize socket
socket = socket_manager.MasiSocketManager()

# Store latest IMU data
latest_imu_data = []

# Mapping Xbox controller outputs to motion platform joysticks
xbox_to_motion_mapping = {
    'LeftJoystickX': 3,  # left stick L/R
    'LeftJoystickY': 4,  # left stick U/D
    'RightJoystickX': 0,  # right stick L/R
    'RightJoystickY': 1,  # right stick U/D
    'LeftTrigger': 7,  # left pedal
    'RightTrigger': 6,  # right pedal
}

def float_to_int(data, scale=int_scale):
    int_data = []
    for value in data:
        clamped_value = max(-1.0, min(1.0, value))
        int_value = int(clamped_value * scale)
        int_data.append(int_value)
    return int_data

def int_to_float(int_data, decimals=2, scale=int_scale):
    float_data = [round((value / scale), decimals) for value in int_data]
    return float_data

def process_pedal_input(trigger_value, bumper_value):
    # Add 5% deadzone to triggers
    deadzone = 0.05
    if abs(trigger_value) < deadzone:
        return 0.0

    # Convert to 0..1 range and move midpoint to be at the start of the trigger
    pedal_value = (trigger_value + 0.5) / 2

    # Flip the value if the bumper is pressed
    if bumper_value:
        pedal_value = - pedal_value

    return pedal_value

def process_controller_input(controller_value, channel):
    # flip all channels
    controller_value = -controller_value

    # Add 8% deadzone to all controller channels
    deadzone = 0.08
    if abs(controller_value) < deadzone:
        return 0.0

    # Special processing for LeftJoystickX
    if channel == 'LeftJoystickX':
        # Add 25% deadzone
        if abs(controller_value) < 0.25:
            return 0.0

    return controller_value

def format_imu_data(float_data):
    imu_data = []
    for i in range(3):  # 3 IMUs
        base_idx = i * 6
        imu = {
            'name': f'IMU_{i}',
            'accel_x': float_data[base_idx],
            'accel_y': float_data[base_idx + 1],
            'accel_z': float_data[base_idx + 2],
            'gyro_x': float_data[base_idx + 3],
            'gyro_y': float_data[base_idx + 4],
            'gyro_z': float_data[base_idx + 5]
        }
        imu_data.append(imu)
    return imu_data

# Web server routes
async def get_imu_data(request):
    return web.json_response(latest_imu_data)

async def index(request):
    return web.FileResponse('web/index.html')

# Setup web routes
app = web.Application()
app.router.add_get('/', index)
app.router.add_get('/api/imu', get_imu_data)
app.router.add_static('/static/', path='web/static')

async def setup_connection():
    if not socket.setup_socket(addr, port, identification_number, inputs, outputs, socket_type='client'):
        raise Exception("Could not setup socket!")

    handshake_result, extra_args = socket.handshake(extra_arg1=control_frequency, extra_arg2=int_scale,
                                                    local_datatype='int')

    if not handshake_result:
        raise Exception("Could not make handshake!")

    socket.tcp_to_udp()
    await asyncio.sleep(10)

async def process_imu_data():
    global latest_imu_data
    while True:
        imu_data = socket.get_latest_received()
        if imu_data is not None:
            float_data = int_to_float(imu_data)
            latest_imu_data = format_imu_data(float_data)
        await asyncio.sleep(0.2)  # 5Hz update rate

async def send_control_signals():
    interval = 1.0 / control_frequency
    while True:
        start_time = time.time()

        xbox_data = xbox_controller.read()
        motion_data = motion_controller.read()

        combined_data = list(motion_data)

        for xbox_key, motion_index in xbox_to_motion_mapping.items():
            xbox_value = xbox_data.get(xbox_key, 0)

            if xbox_key in ['LeftTrigger', 'RightTrigger']:
                bumper_key = 'LeftBumper' if xbox_key == 'LeftTrigger' else 'RightBumper'
                xbox_value = process_pedal_input(xbox_value, xbox_data.get(bumper_key, 0))
            else:
                xbox_value = process_controller_input(xbox_value, xbox_key)

            motion_value = motion_data[motion_index]

            if abs(xbox_value) > abs(motion_value):
                combined_data[motion_index] = xbox_value

        int_combined_data = float_to_int(combined_data)
        socket.send_data(int_combined_data)

        elapsed_time = time.time() - start_time
        await asyncio.sleep(max(0, interval - elapsed_time))

async def main():
    await setup_connection()
    
    # Create all tasks
    send_task = asyncio.create_task(send_control_signals())
    imu_task = asyncio.create_task(process_imu_data())
    
    # Setup and start web server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', web_port)
    await site.start()
    
    print(f"Web interface running at http://localhost:{web_port}")
    
    # Run everything
    await asyncio.gather(send_task, imu_task)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program terminated by user")
    finally:
        socket.stop_all()
        xbox_controller.stop_monitoring()
