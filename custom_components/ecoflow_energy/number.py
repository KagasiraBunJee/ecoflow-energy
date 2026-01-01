import logging
from typing import Any, Callable

from homeassistant.components.number import NumberEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .device import BaseDevice, DataValue
from .device.command import BaseEntityCommand, CommandId, CommandSet
from .entity import BaseCommandEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    _LOGGER.info("Init numbers")
    entities = []

    for device in hass.data[DOMAIN]["devices"]:
        entities.extend(device.numbers())
    async_add_entities(entities)


class ConfigNumber(BaseCommandEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        device: BaseDevice,
        data_key: str,
        name: str,
        min_value: float,
        max_value: float,
        step: float,
        unit: str | None,
        cmd_set: CommandSet,
        cmd_id: CommandId,
        param_builder: Callable[[float], dict[str, Any]],
    ) -> None:
        self._number_name = name
        self._min_value = min_value
        self._max_value = max_value
        self._step = step
        self._unit = unit
        self._cmd_set = cmd_set
        self._cmd_id = cmd_id
        self._param_builder = param_builder
        super().__init__(device, data_key)

        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        if unit:
            self._attr_native_unit_of_measurement = unit

    def get_value_from_db(self) -> DataValue:
        numbers = self.device.data.mapped_data.get("numbers", {})
        if self.data_key in numbers:
            return numbers[self.data_key]
        return DataValue(self._number_name, None, True)

    def set_entity_value(self, value):
        self._attr_native_value = value
        values = self.get_value_from_db()
        values.value = value
        self.device.data.mapped_data.setdefault("numbers", {})[self.data_key] = values

    async def async_set_native_value(self, value: float) -> None:
        if not self.entity_enabled:
            return
        params = self._param_builder(value)
        command = BaseEntityCommand(self.device.sn, self._cmd_set, self._cmd_id, params)
        res = await self.send_command(command)
        if res:
            self.set_entity_value(value)
            self.async_write_ha_state()
