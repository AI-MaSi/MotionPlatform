import asyncio
import logging
import yaml
import aiohttp
import time
import hashlib
import json
from control_modules import NiDAQ_controller

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MotionPlatformClient:
    def __init__(self, config_path: str = 'configuration_files/motion_platform_config.yaml'):
        self.config = None
        self.load_config(config_path)
        self.http_session = None
        self.controller = NiDAQ_controller.NiDAQJoysticks(
            simulation_mode=self.config['simulation'],
            decimals=3
        )
        self.last_sent_data = None
        self.last_received_timestamp = 0
        self.receive_event = asyncio.Event()
        self.latest_received_data = None

    def load_config(self, config_path: str):
        with open(config_path, 'r') as config_file:
            self.config = yaml.safe_load(config_file)
        logging.getLogger().setLevel(self.config['log_level'])

    @staticmethod
    def calculate_checksum(values, timestamp):
        data = json.dumps(values) + str(timestamp)
        return hashlib.md5(data.encode()).hexdigest()

    async def setup(self):
        logger.info("Setting up Motion Platform Client...")
        self.http_session = aiohttp.ClientSession()

    async def run(self):
        logger.info("Starting Motion Platform Client...")
        try:
            send_task = asyncio.create_task(self.send_loop())
            receive_task = asyncio.create_task(self.receive_loop())
            process_task = asyncio.create_task(self.process_received_data())

            await asyncio.gather(send_task, receive_task, process_task)
        except asyncio.CancelledError:
            logger.info("Asyncio task cancelled. Shutting down...")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
        finally:
            await self.stop()

    async def send_loop(self):
        send_url = f"http://{self.config['server_addr']}:{self.config['server_port']}/send/motion_platform"
        while True:
            await self.send_control_data(send_url)
            await asyncio.sleep(1 / self.config['send_frequency'])

    async def receive_loop(self):
        receive_url = f"http://{self.config['server_addr']}:{self.config['server_port']}/receive/motion_platform"
        while True:
            await self.receive_sensor_data(receive_url)
            await asyncio.sleep(1 / self.config['receive_frequency'])

    async def process_received_data(self):
        while True:
            await self.receive_event.wait()
            self.receive_event.clear()

            if self.latest_received_data:
                # Process the received data here
                logger.debug(f"Processing received data: {self.latest_received_data}")
                # Add your data processing logic here

            # Optional: Add a small delay to prevent tight loop
            await asyncio.sleep(0.001)

    async def send_control_data(self, url):
        try:
            joystick_data = self.controller.read()

            # Skip sending if the data hasn't changed
            if joystick_data == self.last_sent_data:
                logger.debug("Skipping send - no new data")
                return

            timestamp = time.time()
            checksum = self.calculate_checksum(joystick_data, timestamp)

            payload = {
                "values": joystick_data,
                "timestamp": timestamp,
                "checksum": checksum
            }

            async with self.http_session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.debug(f"Sent control data: {joystick_data}")
                    self.last_sent_data = joystick_data
                else:
                    logger.error(f"Failed to send control data. Status: {response.status}")
                    response_text = await response.text()
                    logger.error(f"Response: {response_text}")
        except Exception as e:
            logger.error(f"Error in send_control_data: {e}")

    async def receive_sensor_data(self, url):
        try:
            async with self.http_session.get(url) as response:
                if response.status == 200:
                    sensor_data = await response.json()

                    # Verify timestamp and checksum
                    calculated_checksum = self.calculate_checksum(sensor_data['values'], sensor_data['timestamp'])
                    if calculated_checksum != sensor_data['checksum']:
                        logger.error("Checksum mismatch in received data")
                        return

                    logger.debug(f"Received sensor data: {sensor_data['values']}")
                    self.last_received_timestamp = sensor_data['timestamp']

                    # Store the latest received data and set the event
                    self.latest_received_data = sensor_data['values']
                    self.receive_event.set()
                elif response.status == 204:
                    logger.debug("No new data available")
                    # you could set the event to trigger processing of the last known data
                    # self.receive_event.set()
                else:
                    logger.error(f"Failed to receive sensor data. Status: {response.status}")
        except Exception as e:
            logger.error(f"Error in receive_sensor_data: {e}")

    async def stop(self):
        logger.info("Stopping Motion Platform Client...")
        if self.http_session:
            await self.http_session.close()


async def main():
    client = MotionPlatformClient()
    try:
        await client.setup()
        await client.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down...")
    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())