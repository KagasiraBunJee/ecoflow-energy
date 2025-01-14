from __future__ import annotations

from asyncio import Future
from dataclasses import dataclass
from enum import IntEnum
import json
import logging
import ssl
from typing import Any
from ..device.command import BaseEntityCommand, BaseEntityCommandResponse
from homeassistant.components.mqtt.async_client import AsyncMQTTClient


from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send, dispatcher_send

_LOGGER = logging.getLogger(__name__)


COMMAND_TOPIC_SUFFIX = "set"
QUOTA_TOPIC_SUFFIX = "quota"
COMMAND_REPLY_TOPIC_SUFFIX = "set_reply"

@dataclass
class EcoflowMqttInfo:
    url: str
    port: int
    protocol: str
    username: str
    password: str
    client_id: str | None = None


class MQTTClient:
    """Handles MQTT communication."""

    def __init__(self, mqtt_info: EcoflowMqttInfo, hass: HomeAssistant) -> None:
        self.credentials = mqtt_info
        self.__client: AsyncMQTTClient = None
        self.hass = hass
        self.callback_holder = dict[int, Future[Any]]()

    def connect(self):
        """Connect to the MQTT broker."""
        self.__client = AsyncMQTTClient(client_id=self.credentials.client_id, reconnect_on_failure=True, clean_session=True)
        self.__client.setup()
        self.__client.username_pw_set(self.credentials.username, self.credentials.password)
        self.__client.tls_set(certfile=None, keyfile=None, cert_reqs=ssl.CERT_REQUIRED)
        self.__client.tls_insecure_set(False)
        self.__client.on_message = self._on_message
        self.__client.on_connect = self._on_connect
        self.__client.on_connect_fail = self.on_connect_fail
        self.__client.on_disconnect = self._on_disconnect
        self.__client.on_socket_close = self._on_socket_closed
        self.__client.connect(self.credentials.url, int(self.credentials.port), keepalive=15)
        self.__client.loop_start()

    def send_command(self, sn, command: BaseEntityCommand):
        topic = f"/open/{self.credentials.username}/{sn}/{COMMAND_TOPIC_SUFFIX}"
        self.__client.publish(topic, command.to_message())

    async def async_send_command(self, sn, command: BaseEntityCommand) -> BaseEntityCommandResponse:
        topic = f"/open/{self.credentials.username}/{sn}/{COMMAND_TOPIC_SUFFIX}"

        command_future = self.hass.loop.create_future()

        self.callback_holder[command.id] = command_future
        self.__client.publish(topic, command.to_message())

        return await command_future

    def subscribe_to_device(self, sn, topic_key):
        """Subscribe to a specific device's MQTT topic."""
        user_name = self.credentials.username
        topics = [f"/open/{user_name}/{sn}/{QUOTA_TOPIC_SUFFIX}", f"/open/{user_name}/{sn}/{COMMAND_REPLY_TOPIC_SUFFIX}"]

        def message_handler(client, userdata, message):
            dispatcher_send(self.hass, f"device_update_{sn}", message)
            try:
                if message.topic == f"/open/{user_name}/{sn}/{COMMAND_REPLY_TOPIC_SUFFIX}":
                    value_str = message.payload.decode("utf-8", errors='ignore')
                    value = json.loads(value_str)
                    response_command = BaseEntityCommandResponse.from_dict(value)
                    if response_command.id in self.callback_holder:
                        future_response = self.callback_holder.pop(response_command.id)
                        if not future_response.done():
                            self.hass.loop.call_soon_threadsafe(future_response.set_result, response_command)

            except UnicodeDecodeError as error:
                _LOGGER.warning(f"UnicodeDecodeError: {error}. Trying to load json.")
            except Exception as error:
                _LOGGER.warning(f"Exception: {error}. Trying to load json.")

        for topic in topics:
            self.__client.subscribe(topic)
            self.__client.message_callback_add(topic, message_handler)

    @callback
    def _on_connect(self, client, userdata, flags, rc):
        _LOGGER.info("Ecoflow mqtt connected")

    @callback
    def on_connect_fail(self):
        _LOGGER.error("Ecoflow mqtt not connected")

    @callback
    def _on_message(self, client, userdata, message):
        _LOGGER.info("Message receive _on_message")

    @callback
    def _on_disconnect(self, client, userdata, reasonCode):
        _LOGGER.info(f"I _on_disconnect {reasonCode}")

    @callback
    def _on_socket_closed(self, client, userdata, socket):
        _LOGGER.info("I _on_socket_closed")
