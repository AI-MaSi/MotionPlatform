import time
import logging
import yaml
from control_modules import socket_manager, NiDAQ_controller

# Setup logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MotionPlatformClient:
    def __init__(self, config_path: str = 'configuration_files/motion_platform_config.yaml'):
        self.config = None
        self.load_config(config_path)

        # Create two socket managers
        self.control_socket = socket_manager.SocketManager(
            inputs=self.config['control_inputs'],
            outputs=self.config['control_outputs']
        )
        self.sensor_socket = socket_manager.SocketManager(
            inputs=self.config['sensor_inputs'],
            outputs=self.config['sensor_outputs']
        )

        self.controller = NiDAQ_controller.NiDAQJoysticks(
            simulation_mode=self.config['simulation'],
            decimals=3
        )

    def load_config(self, config_path: str):
        with open(config_path, 'r') as config_file:
            self.config = yaml.safe_load(config_file)
        logging.getLogger().setLevel(self.config['log_level'])

    def setup(self):
        logger.info("Setting up Motion Platform Client...")
        self.control_socket.setup_socket(
            self.config['addr'],    # use the same address for both control and sensor
            self.config['control_port'],
            socket_type=self.config['socket_type'],
            protocol=self.config['protocol']
        )
        self.sensor_socket.setup_socket(
            self.config['addr'],
            self.config['sensor_port'],
            socket_type=self.config['socket_type'],
            protocol=self.config['protocol']
        )

    def run(self):
        logger.info("Starting Motion Platform Client...")
        try:
            last_sensor_time = 0
            while True:
                self.send_control_data()

                # Check if it's time to receive sensor data
                current_time = time.time()
                if current_time - last_sensor_time >= 1 / self.config['sensor_frequency']:
                    self.receive_sensor_data()
                    last_sensor_time = current_time

                time.sleep(1 / self.config['control_frequency'])
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received. Shutting down...")
        finally:
            self.stop()

    def send_control_data(self):
        try:
            joystick_data = self.controller.read()
            self.control_socket.send_data(joystick_data)
            logger.debug(f"Sent control data: {joystick_data}")
        except Exception as e:
            logger.error(f"Error in send_control_data: {e}")

    def receive_sensor_data(self):
        try:
            sensor_data = self.sensor_socket.get_latest_data()
            if sensor_data:
                logger.info(f"Received sensor data: {sensor_data}")
        except Exception as e:
            logger.error(f"Error in receive_sensor_data: {e}")

    def stop(self):
        logger.info("Stopping Motion Platform Client...")
        self.control_socket.close()
        self.sensor_socket.close()


def main():
    client = MotionPlatformClient()
    client.setup()
    client.run()


if __name__ == "__main__":
    main()