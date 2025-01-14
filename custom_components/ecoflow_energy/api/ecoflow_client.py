from __future__ import annotations

from enum import StrEnum
import logging
import secrets
from dataclasses import dataclass
from typing import Any

from dacite import from_dict

from .http_client import EcoFlowHttpClient

from ..device.smart_home_panel import SmartHomePanel
from ..device.command import CommandTarget

from .ecoflow_mqtt import MQTTClient, EcoflowMqttInfo

_LOGGER = logging.getLogger(__name__)

DEVICE_LIST = "iot-open/sign/device/list"
MQTT_DATA = "iot-open/sign/certification"
QUOTA_ALL = "iot-open/sign/device/quota/all"
QUOTA = "iot-open/sign/device/quota"

@dataclass
class DeviceData:
    sn: str
    name: str
    device_type: str


class DeviceData:
    mqtt_quota_data: dict[str, Any]
    mqtt_status_data: dict[str, Any]
    mqtt_set_reply_data: dict[str, Any]

    def __init__(self):
        self.mqtt_quota_data = {}
        self.mqtt_status_data = {}
        self.mqtt_set_reply_data = {}


class EcoFlowApiClient:
    def __init__(self, access_key: str, secret: str, hass):
        self.client = EcoFlowHttpClient(access_key, secret)
        self.mqtt_info: EcoflowMqttInfo
        self.mqtt_client: MQTTClient = None
        self.mqtt_data = dict[str, DeviceData]()
        self.hass = hass

    async def login(self) -> EcoflowMqttInfo:
        resp = await self.client.get_data(MQTT_DATA)
        return self.__fill_mqtt_data(resp["data"])

    def set_mqtt_creds(self, creds):
        if isinstance(creds, dict):
            creds["port"] = int(creds["port"])
            self.mqtt_info = from_dict(data_class=EcoflowMqttInfo, data=creds)
        else:
            self.mqtt_info = creds

    def start(self):
        self._init_mqtt()

    async def devices_list(self):
        try:
            resp = await self.client.get_data(DEVICE_LIST)
            devices_data = []
            for device in resp["data"]:
                productName = device["productName"]
                if productName == "Smart Home Panel":
                    devices_data.append(
                        SmartHomePanel(sn=device["sn"], name=productName, status=device["online"], api_client=self)
                    )
                else:
                    _LOGGER.warning(f"Not supported {productName}")
            return devices_data
        except Exception as error:
            _LOGGER.error(f"Error getting devices list {error}")

    def _init_mqtt(self):
        self.mqtt_client = MQTTClient(self.mqtt_info, self.hass)
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
            _LOGGER.error(f"Error getting device {sn} info: {error}")

    def __client_id(self):
        return "historic_mqttx_2f8bc4fa"

    def __fill_mqtt_data(self, data) -> EcoflowMqttInfo:
        url = data["url"]
        port = data["port"]
        protocol = data["protocol"]
        username = data["certificateAccount"]
        password = data["certificatePassword"]
        self.mqtt_info = EcoflowMqttInfo(url=url,
                                         port=port,
                                         protocol=protocol,
                                         username=username,
                                         password=password,
                                         client_id=self.__client_id())
        return self.mqtt_info
