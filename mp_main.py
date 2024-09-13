import asyncio
import logging
import yaml
from control_modules.socket_manager import AsyncSocketManager
from control_modules import NiDAQ_controller

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MotionPlatformClient:
    def __init__(self, config_path: str = 'configuration_files/motion_platform_config.yaml'):
        self.config = None
        self.load_config(config_path)

        self.control_socket = AsyncSocketManager(
            inputs=None,
            outputs=self.config['control_outputs']
        )

        self.controller = NiDAQ_controller.NiDAQJoysticks(
            simulation_mode=self.config['simulation'],
            decimals=3
        )

    def load_config(self, config_path: str):
        with open(config_path, 'r') as config_file:
            self.config = yaml.safe_load(config_file)
        logging.getLogger().setLevel(self.config['log_level'])

    async def setup(self):
        logger.info("Setting up Motion Platform Client...")
        await self.control_socket.setup(
            local_addr=(self.config['addr'], self.config['control_port']),
            remote_addr=(self.config['remote_addr'], self.config['control_port'])
        )

    async def run(self):
        logger.info("Starting Motion Platform Client...")
        try:
            while True:
                await self.send_control_data()
                await asyncio.sleep(1 / self.config['control_frequency'])
        except asyncio.CancelledError:
            logger.info("Asyncio task cancelled. Shutting down...")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
        finally:
            self.stop()

    async def send_control_data(self):
        try:
            joystick_data = self.controller.read()
            self.control_socket.send_data(joystick_data)
            logger.debug(f"Sent control data: {joystick_data}")
        except Exception as e:
            logger.error(f"Error in send_control_data: {e}")

    def stop(self):
        logger.info("Stopping Motion Platform Client...")
        self.control_socket.close()

async def main():
    client = MotionPlatformClient()
    try:
        await client.setup()
        await client.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down...")
    finally:
        client.stop()

if __name__ == "__main__":
    asyncio.run(main())