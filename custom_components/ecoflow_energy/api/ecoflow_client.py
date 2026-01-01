from __future__ import annotations

import logging
import secrets
from typing import Any, Callable, Awaitable

from .http_client import EcoFlowHttpClient
from .ecoflow_mqtt import MQTTClient, EcoflowMqttInfo
from ..device.command import CommandTarget
from ..device.smart_home_panel import SmartHomePanel

_LOGGER = logging.getLogger(__name__)

DEVICE_LIST = "iot-open/sign/device/list"
MQTT_DATA = "iot-open/sign/certification"
QUOTA_ALL = "iot-open/sign/device/quota/all"
QUOTA = "iot-open/sign/device/quota"

MessageCallback = Callable[[str, str, dict[str, Any]], Awaitable[None] | None]


class EcoFlowApiClient:
    def __init__(self, access_key: str, secret: str, hass):
        self.client = EcoFlowHttpClient(access_key, secret)
        self.mqtt_info: EcoflowMqttInfo
        self.mqtt_client: MQTTClient = None
        self.hass = hass

    async def login(self) -> dict:
        resp = await self.client.get_data(MQTT_DATA)
        data = { "client_id": self.__client_id() }
        data.update(resp["data"])
        return data

    def set_mqtt_creds(self, creds):
        creds["port"] = int(creds["port"])
        self.__fill_mqtt_data(creds)

    def start(self, message_callback: MessageCallback | None = None):
        self._init_mqtt(message_callback)

    async def devices_list(self):
        try:
            resp = await self.client.get_data(DEVICE_LIST)
            devices_data = []
            for device in resp["data"]:
                product_name = device.get("productName") or device.get("deviceName")
                if product_name == "Smart Home Panel":
                    devices_data.append(
                        SmartHomePanel(
                            sn=device["sn"],
                            name=product_name,
                            status=device.get("online", 0),
                            api_client=self,
                        )
                    )
                else:
                    _LOGGER.warning("Not supported device: %s", product_name)
            return devices_data
        except Exception as error:
            _LOGGER.error("Error getting devices list %s", error)
            return []

    def _init_mqtt(self, message_callback: MessageCallback | None = None):
        self.mqtt_client = MQTTClient(self.mqtt_info, self.hass, message_callback)
        self.mqtt_client.connect()

    def __send_mqtt_command(self, sn, params) -> bool:
        self.mqtt_client.send_command(sn, params)

    async def __async_send_mqtt_command(self, sn, params) -> bool:
        res = await self.mqtt_client.async_send_command(sn, params)
        return res.data.ack == 0 and res.data.sta == 0

    async def __send_http_command(self, sn, params):
        await self.client.send_request(QUOTA, 'PUT', params)

    async def send_command(self, sn, params, target: CommandTarget = CommandTarget.MQTT) -> bool:
        if target == CommandTarget.MQTT:
            return await self.__async_send_mqtt_command(sn, params)
        if target == CommandTarget.HTTP:
            await self.__send_http_command(sn, params)
        return True

    async def get_device_info(self, sn: str):
        try:
            resp = await self.client.get_data(QUOTA_ALL, {"sn": sn})
            return resp["data"]
        except Exception as error:
            _LOGGER.error("Error getting device %s info: %s", sn, error)
            return None

    def subscribe(self, sn: str):
        if self.mqtt_client is None:
            return
        self.mqtt_client.subscribe_to_device(sn, "quota")

    def shutdown(self):
        if self.mqtt_client is None:
            return
        self.mqtt_client.disconnect()

    def __client_id(self):
        return f"energy_mqttx_{secrets.token_hex(4)}"

    def __fill_mqtt_data(self, data) -> EcoflowMqttInfo:
        url = data["url"]
        port = data["port"]
        protocol = data["protocol"]
        username = data["certificateAccount"]
        password = data["certificatePassword"]
        client_id = data["client_id"]
        self.mqtt_info = EcoflowMqttInfo(url=url,
                                         port=port,
                                         protocol=protocol,
                                         username=username,
                                         password=password,
                                         client_id=client_id)
        return self.mqtt_info
