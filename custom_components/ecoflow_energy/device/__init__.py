import logging

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
    GRID_STATUS = "grid_status"

class EntityUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, device) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Ecoflow update coordinator",
            update_interval=None,
        )
        self.device = device

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

    def notify_updated(self):
        if self.coordinator is None:
            return
        self.coordinator.async_set_updated_data(self.data)

    async def apply_quota_all(self, data: dict[str, Any]):
        self.data.response_data = data
        self.calculate_data()

    async def handle_mqtt_params(self, params: dict[str, Any]):
        pass
