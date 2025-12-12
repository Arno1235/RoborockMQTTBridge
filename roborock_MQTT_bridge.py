import os
import asyncio
import json
import time

from roborock import RoborockException
from roborock.web_api import RoborockApiClient
from roborock.cli import RoborockContext, _discover
from roborock.containers import DeviceData, LoginData
from roborock.version_1_apis.roborock_mqtt_client_v1 import RoborockMqttClientV1
from roborock import RoborockCommand

import paho.mqtt.client as mqtt


# config
RR_EMAIL = os.getenv("RR_EMAIL")
RR_PASSWORD = os.getenv("RR_PASSWORD")
RR_DEVICE_ID = os.getenv("RR_DEVICE_ID")
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "roborock")
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", "60"))
DEVICE_UPDATE_INTERVAL = int(os.getenv("DEVICE_UPDATE_INTERVAL", "86400"))
PUSH_TO_HOMEASSISTANT = bool(os.getenv("PUSH_TO_HOMEASSISTANT", "False"))

print("Starting with:")
print(f"RR_EMAIL = {RR_EMAIL}")
print(f"RR_PASSWORD = {RR_PASSWORD}")
print(f"RR_DEVICE_ID = {RR_DEVICE_ID}")
print(f"MQTT_BROKER = {MQTT_BROKER}")
print(f"MQTT_PORT = {MQTT_PORT}")
print(f"MQTT_TOPIC_PREFIX = {MQTT_TOPIC_PREFIX}")
print(f"MQTT_USER = {MQTT_USER}")
print(f"MQTT_PASSWORD = {MQTT_PASSWORD}")
print(f"POLLING_INTERVAL = {POLLING_INTERVAL}")
print(f"DEVICE_UPDATE_INTERVAL = {DEVICE_UPDATE_INTERVAL}")
print(f"PUSH_TO_HOMEASSISTANT = {PUSH_TO_HOMEASSISTANT}")
print()


class CtxObj:
    def __init__(self, ctx):
        self.obj = ctx

class RoborockMQTTBridge:
    def __init__(self, rr_email, rr_password, rr_device_id, mqtt_broker, mqtt_port, mqtt_topic_prefix, mqtt_user, mqtt_password, polling_interval, device_update_interval, homeassistant):
        self.rr_email = rr_email
        self.rr_password = rr_password
        self.rr_device_id = rr_device_id

        self.mqtt_client = mqtt.Client(client_id='rr2mqtt')
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_topic_prefix = mqtt_topic_prefix
        self.mqtt_user = mqtt_user
        self.mqtt_password = mqtt_password
        
        self.polling_interval = polling_interval
        self.device_update_interval = device_update_interval
        self.homeassistant = homeassistant
    
    async def setup(self):

        self.connect_mqtt()

        await self.login_rr()

        self.devices = {}
        await self.update_devices()

        if self.homeassistant:
            await self.push_config_to_homeassistant()

        return

    def connect_mqtt(self):
        # Connect to local MQTT broker
        self.mqtt_client.username_pw_set(self.mqtt_user, self.mqtt_password)
        self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
        self.mqtt_client.loop_start()
        print(f"Connected to MQTT broker at {self.mqtt_broker}:{self.mqtt_port}")

        self.publish_to_mqtt(
            parent_topic='rr2mqtt',
            data={
                'rr_email': self.rr_email,
                'rr_device_id': self.rr_device_id,
                'mqtt_broker': self.mqtt_broker,
                'mqtt_port': self.mqtt_port,
                'mqtt_topic_prefix': self.mqtt_topic_prefix,
                'mqtt_user': self.mqtt_user,
                'polling_interval': self.polling_interval,
                'device_update_interval': self.device_update_interval,
            },
            retain=True,
        )

    async def login_rr(self):
        self.ctx = CtxObj(RoborockContext())

        context: RoborockContext = self.ctx.obj
        try:
            context.validate()
            print("Already logged in")
            return
        except RoborockException:
            pass

        client = RoborockApiClient(self.rr_email)
        self.user_data = None

        try:
            print("Trying to login using password")
            self.user_data = await client.pass_login(self.rr_password)
            context.update(LoginData(user_data=self.user_data, email=self.rr_email))
            return
        except:
            pass

        try:
            print("Trying to login using code")
            await client.request_code()
            code = input("code:")
            self.user_data = await client.code_login(code)
            context.update(LoginData(user_data=self.user_data, email=self.rr_email))
            return
        except:
            pass

        print("roborock login failed")
        return
    
    async def update_devices(self):
        print("Updating device list")

        for device in self.devices.values():
            device['device_mqtt_client'].__del__()
        self.devices = {}

        context: RoborockContext = self.ctx.obj
        login_data = context.login_data()
        if not login_data.home_data:
            await _discover(self.ctx)
            login_data = context.login_data()
        home_data = login_data.home_data

        devices = home_data.devices + home_data.received_devices

        print("Devices found:")
        print(", ".join([f"{device.name}: {device.duid}" for device in devices]))

        for device in devices:
            if device.duid != self.rr_device_id:
                print(f'Skipping device as it does not have the correct id: {device.duid}')
                continue

            model = next(
                (product.model for product in home_data.products if device is not None and product.id == device.product_id),
                None,
            )

            if model is None:
                print(f"Could not find model for device {device.name}")
                continue

            device_info = DeviceData(device=device, model=model)
            device_mqtt_client = RoborockMqttClientV1(login_data.user_data, device_info)

            self.devices[device.duid] = {
                'device': device,
                'device_info': device_info,
                'device_mqtt_client': device_mqtt_client,
            }

            self.publish_to_mqtt("device_info", device, retain=True)
        
        return

    def publish_to_mqtt(self, parent_topic, data, retain=False):
        """Publish data to MQTT"""
        parent_topic = f"{self.mqtt_topic_prefix}/{parent_topic}"
        
        # Convert data to dict if it's not already
        if hasattr(data, '__dict__'):
            payload_dict = {k: v for k, v in data.__dict__.items() if not k.startswith('_')}
        else:
            payload_dict = data
        
        for k, v in payload_dict.items():
            payload = json.dumps(v, default=str)
            self.mqtt_client.publish(f"{parent_topic}/{k}", payload, retain=retain)
        
        return payload_dict

    async def rr_command(self, device, cmd, params=None):
        try:
            device_mqtt_client = device['device_mqtt_client']

            if params is None:
                response = await device_mqtt_client.send_command(cmd)
            else:
                response = await device_mqtt_client.send_command(cmd, json.loads(params))

            return response
        except:
            return None

    def cleanup(self):
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        print("mqtt disconnected")

        for device in self.devices.values():
            device['device_mqtt_client'].__del__()
            print(f"Device cleaned up {device['device'].name}")

    async def device_poll(self, device):
        UDT = {}
        r = await self.rr_command(device, RoborockCommand.GET_STATUS)
        if r is not None:
            UDT['status'] = self.publish_to_mqtt("status", r)

        r = await self.rr_command(device, RoborockCommand.GET_CONSUMABLE)
        if r is not None:
            UDT['consumable'] = self.publish_to_mqtt("consumable", r)

        r = await self.rr_command(device, RoborockCommand.GET_CLEAN_SUMMARY)
        if r is not None:
            UDT['clean_summary'] = self.publish_to_mqtt("clean_summary", r)

        r = await self.rr_command(device, RoborockCommand.GET_NETWORK_INFO)
        if r is not None:
            UDT['network_info'] = self.publish_to_mqtt("network_info", r)
        
        return UDT
    
    async def poll_all_devices(self):

        print(f"Starting polling every {self.polling_interval}s and updating device list every {self.device_update_interval}s")
        
        device_update_time = time.time()
    
        while True:
            try:
                if time.time() - device_update_time > self.device_update_interval:
                    await self.update_devices()
                
                for device in self.devices.values():
                    if device['device'].duid != self.rr_device_id:
                        continue
                    await self.device_poll(device)
                
            except Exception as e:
                print(f"Error during polling: {e}\n")
            
            await asyncio.sleep(self.polling_interval)

    async def push_config_to_homeassistant(self):
        UDT = await self.device_poll(self.devices[self.rr_device_id])

        payload = {
            "dev": {
                "name": "robot_vacuum",
                "model": "Q Revo",
                "manufacturer": "Roborock",
                "model_id": self.rr_device_id,
                "identifiers": [self.rr_device_id]
            },
            "o": {
                "name": "robot_vacuum"
            },
            "cmps": {}
        }

        index = 0
        for cmd, r in UDT.items():
            for k, v in r.items():
                payload["cmps"][k] = {
                    "platform": "sensor",
                    "name": k,
                    "state_topic": f"{self.mqtt_topic_prefix}/{cmd}/{k}",
                    "unique_id": f"{self.rr_device_id}_{k}",
                    "qos": 0
                }
                index += 1

        self.mqtt_client.publish(f"homeassistant/device/{self.rr_device_id}/config", json.dumps(payload, default=str), retain=True)

async def main():

    bridge = RoborockMQTTBridge(
        rr_email=RR_EMAIL,
        rr_password=RR_PASSWORD,
        rr_device_id=RR_DEVICE_ID,
        mqtt_broker=MQTT_BROKER,
        mqtt_port=MQTT_PORT,
        mqtt_topic_prefix=MQTT_TOPIC_PREFIX,
        mqtt_user=MQTT_USER,
        mqtt_password=MQTT_PASSWORD,
        polling_interval=POLLING_INTERVAL,
        device_update_interval=DEVICE_UPDATE_INTERVAL,
        homeassistant=PUSH_TO_HOMEASSISTANT,
    )

    try:
        await bridge.setup()
        await bridge.poll_all_devices()

    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print(f"\nFatal error: {e}")

    finally:
        bridge.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
