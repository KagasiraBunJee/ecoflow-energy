from collections import OrderedDict
from datetime import timedelta
from collections.abc import Mapping
import logging
from typing import Any, Self

from config.custom_components.ecoflow_energy.device.breaker import BreakerMode
from config.custom_components.ecoflow_energy.device.command import BaseEntityCommand, CommandTarget

from ..const import ECOFLOW_DOMAIN
from ..device import BaseDevice, EntityUpdateCoordinator, DataValue

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

_LOGGER = logging.getLogger(__name__)

class BaseEntity(CoordinatorEntity[EntityUpdateCoordinator], Entity):
    def __init__(self, device: BaseDevice, data_key) -> None:
        super().__init__(device.coordinator)
        self.device = device
        self.data_key = data_key

        values = self.get_value_from_db()
        self._attr_name = f"{device.sn} {values.name}"
        self._sensor_id = values.name
        self.set_entity_value(values.value)
        self.entity_enabled = True

        if data_key in self.device.data.entity_visibility:
            visible = self.device.data.entity_visibility[data_key]
            self._attr_entity_registry_visible_default = visible
            self._attr_entity_registry_enabled_default = visible
            self.entity_enabled = visible

    def set_entity_value(self, value):
        pass

    def get_value_from_db(self) -> DataValue:
        return None

    def _handle_coordinator_update(self) -> None:
        values = self.get_value_from_db()
        self.set_entity_value(values.value)
        super()._handle_coordinator_update()

class BaseCommandEntity(BaseEntity):
    def __init__(self, device: BaseDevice, data_key) -> None:
        super().__init__(device, data_key)
        self._last_msg_id = None

    async def send_command(self, command: BaseEntityCommand) -> bool:
        self._last_msg_id = command.id
        return await self.device.api_client.send_command(self.device.sn, command, CommandTarget.MQTT)

class BaseSwitch(BaseCommandEntity, SwitchEntity):
    async def switch(self, status: bool):
        pass

    async def async_turn_on(self, **kwargs: Any):
        if self.entity_enabled:
            await self.switch(True)

    async def async_turn_off(self, **kwargs: Any):
        if self.entity_enabled:
            await self.switch(False)

    @property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={(ECOFLOW_DOMAIN, f"{self.device.name}-{self.device.sn[-4:]}")},
            manufacturer="EcoFlow",
            name=self.device.name,
            model=self.device.name,
            serial_number=self.device.sn
        )

    @property
    def unique_id(self):
        return f"{self.device.sn}_{self._sensor_id}"

    def get_value_from_db(self) -> DataValue:
        return self.device.data.mapped_data["switches"][self.data_key]

    def set_entity_value(self, value):
        self._attr_is_on = value
        values = self.device.data.mapped_data["switches"][self.data_key]
        values.value = value

class BaseSensor(BaseEntity, SensorEntity):
    def __init__(self, device: BaseDevice, data_key) -> None:
        super().__init__(device, data_key)
        self.__attrs = OrderedDict[str, Any]()

        if data_key in self.device.data.mapped_custom_attrs:
            custom_attrs = self.device.data.mapped_custom_attrs[data_key]
            self.__attrs = custom_attrs

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        return self.__attrs

    @property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={(ECOFLOW_DOMAIN, f"{self.device.name}-{self.device.sn[-4:]}")},
            manufacturer="EcoFlow",
            name=self.device.name,
            model=self.device.name,
            serial_number=self.device.sn
        )

    @property
    def unique_id(self):
        return f"{self.device.sn}_{self._sensor_id}"

    def set_entity_value(self, value):
        self._attr_native_value = value

    def get_value_from_db(self) -> DataValue:
        return self.device.data.mapped_data["sensors"][self.data_key]

class BreakerSelect(BaseCommandEntity, SelectEntity):
    def __init__(self, device: BaseDevice, data_key, index: int, mode_key: str, source_key: str) -> None:
        self.breaker_options = BreakerMode()
        self.options = self.breaker_options.options()
        self.mode_key = mode_key
        self.source_key = source_key
        self.breaker_index = index
        super().__init__(device, data_key)

        if mode_key in self.device.data.entity_visibility:
            visible = self.device.data.entity_visibility[mode_key]
            self._attr_entity_registry_visible_default = visible
            self._attr_entity_registry_enabled_default = visible
            self.entity_enabled = visible

    @property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={(ECOFLOW_DOMAIN, f"{self.device.name}-{self.device.sn[-4:]}")},
            manufacturer="EcoFlow",
            name=self.device.name,
            model=self.device.name,
            serial_number=self.device.sn
        )

    @property
    def unique_id(self):
        return f"{self.device.sn}_{self._sensor_id}"

    def set_entity_value(self, value: str):
        self._attr_current_option = value

    def get_value_from_db(self) -> DataValue:
        ctrl = self.device.data.mapped_data["sensors"][self.mode_key].value
        sta = self.device.data.mapped_data["sensors"][self.source_key].value
        new_value = self.breaker_options.get_action_name(ctrl, sta)
        return DataValue(f"Breaker {self.breaker_index + 1} mode select", new_value, True)