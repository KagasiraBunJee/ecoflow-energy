from __future__ import annotations

from __future__ import annotations

from asyncio import Future
from dataclasses import dataclass
import asyncio
import json
import logging
import ssl
from typing import Any, Awaitable, Callable

from homeassistant.components.mqtt.async_client import AsyncMQTTClient
from homeassistant.core import HomeAssistant, callback

from ..device.command import BaseEntityCommand, BaseEntityCommandResponse

_LOGGER = logging.getLogger(__name__)


COMMAND_TOPIC_SUFFIX = "set"
QUOTA_TOPIC_SUFFIX = "quota"
COMMAND_REPLY_TOPIC_SUFFIX = "set_reply"
STATUS_TOPIC_SUFFIX = "status"

@dataclass
class EcoflowMqttInfo:
    url: str
    port: int
    protocol: str
    username: str
    password: str
    client_id: str | None = None


MessageCallback = Callable[[str, str, dict[str, Any]], Awaitable[None] | None]


class MQTTClient:
    """Handles MQTT communication."""

    def __init__(
        self,
        mqtt_info: EcoflowMqttInfo,
        hass: HomeAssistant,
        message_callback: MessageCallback | None = None,
    ) -> None:
        self.credentials = mqtt_info
        self.__client: AsyncMQTTClient = None
        self.hass = hass
        self.callback_holder = dict[int, Future[Any]]()
        self.device_resub = dict[str, Any]()
        self._message_callback = message_callback

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

    def disconnect(self):
        if self.__client is None:
            return
        try:
            self.__client.loop_stop()
            self.__client.disconnect()
        except Exception as error:
            _LOGGER.debug("MQTT disconnect failed: %s", error)

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
        topics = [
            f"/open/{user_name}/{sn}/{QUOTA_TOPIC_SUFFIX}",
            f"/open/{user_name}/{sn}/{COMMAND_REPLY_TOPIC_SUFFIX}",
            f"/open/{user_name}/{sn}/{STATUS_TOPIC_SUFFIX}",
        ]
        self.device_resub[sn] = 1
        for topic in topics:
            self.__client.subscribe(topic)

    @callback
    def _on_connect(self, client, userdata, flags, rc):
        _LOGGER.info(f"Ecoflow mqtt connected {rc}")
        if rc == 0:
            sn_list = self.device_resub.keys()
            for device_sn in sn_list:
                self.subscribe_to_device(device_sn, "")

    @callback
    def on_connect_fail(self):
        _LOGGER.error("Ecoflow mqtt not connected")

    @callback
    def _on_message(self, client, userdata, message):
        try:
            value_str = message.payload.decode("utf-8", errors="ignore")
            payload = json.loads(value_str)
        except UnicodeDecodeError as error:
            _LOGGER.warning("UnicodeDecodeError: %s. Skipping message.", error)
            return
        except Exception as error:
            _LOGGER.warning("MQTT payload parse failed: %s", error)
            return

        topic_parts = message.topic.split("/")
        if len(topic_parts) < 5:
            _LOGGER.debug("Unexpected MQTT topic: %s", message.topic)
            return

        sn = topic_parts[-2]
        suffix = topic_parts[-1]

        if suffix == COMMAND_REPLY_TOPIC_SUFFIX:
            try:
                response_command = BaseEntityCommandResponse.from_dict(payload)
                if response_command.id in self.callback_holder:
                    future_response = self.callback_holder.pop(response_command.id)
                    if not future_response.done():
                        self.hass.loop.call_soon_threadsafe(
                            future_response.set_result, response_command
                        )
            except Exception as error:
                _LOGGER.debug("Failed to parse command response: %s", error)
            return

        if self._message_callback is None:
            return

        def _dispatch():
            result = self._message_callback(sn, suffix, payload)
            if asyncio.iscoroutine(result):
                self.hass.async_create_task(result)

        self.hass.loop.call_soon_threadsafe(_dispatch)

    @callback
    def _on_disconnect(self, client, userdata, reasonCode):
        _LOGGER.info(f"I _on_disconnect {reasonCode}")
        if reasonCode == 16:
            self.__client.loop_start()

    @callback
    def _on_socket_closed(self, client, userdata, socket):
        _LOGGER.info("I _on_socket_closed")
