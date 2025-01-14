import logging
import time

from datetime import timedelta
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

class EntitySensorKey(StrEnum):
    BREAKER = "breaker_"
    SHP_GRID = "shp_grid"
    BATTERIES_COUNT = "batteries_count"
    BATTERY = "battery_"

class EntityUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, device) -> None:
        """Initialize the coordinator."""
        super().__init__(hass,
                         _LOGGER, name="Ecoflow update coordinator",
                         always_update=True,
                        #  update_interval=timedelta(seconds=20),
        )
        self.device = device

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        await self.device.update_data()

    async def _async_update_data(self):
        return self.device.data

@dataclass
class DataValue:
    value: Any
    name: str
    custom_attributes: Any
    default_visible = True

    def __init__(self, name, value, default_visible = True, custom_attributes = None) -> None:
        self.name = name
        self.value = value
        self.custom_attributes = custom_attributes
        self.default_visible = default_visible

    def set_visibility(self, visible):
        self.default_visible = visible

    def set_custom_attr(self, attrs):
        self.custom_attributes = attrs

    def set_value(self, value):
        self.value = value

class DataHolder:
    def __init__(self) -> None:
        self.data_set_reply = {}
        self.response_data = {}

        self.mapped_data = dict[str, dict[str, DataValue]]()
        self.mapped_custom_attrs = dict[str, Any]()
        self.entity_visibility = dict[str, bool]()

        self.last_update = 0

    def current_milli_time() -> float:
        return round(time.time() * 1000)

    def updated(self):
        self.last_update = self.current_milli_time()

class BaseDevice:
    def __init__(self, sn: str, name: str, status: int, api_client) -> None:
        self.sn = sn
        self.name = name
        self.status = status
        from ..api.ecoflow_client import EcoFlowApiClient
        self.api_client: EcoFlowApiClient = api_client
        self.data = DataHolder()
        self.coordinator = None

    def _sensors(self) -> list[SensorEntity]:
        return []

    def switches(self) -> list[SwitchEntity]:
        return []

    def selects(self) -> list[SelectEntity]:
        return []

    async def connect_mqtt(self, hass):
        pass

    def _active_unique_ids(self) -> list[str]:
        return list(
            map(lambda sensor: sensor.unique_id, self._sensors())
        )

    def configure(self, hass):
        self.coordinator = EntityUpdateCoordinator(hass, self)

    def calculate_data(self):
        pass

    async def update_data(self):
        self.data.response_data = await self.api_client.get_device_info(self.sn)
        self.calculate_data()
