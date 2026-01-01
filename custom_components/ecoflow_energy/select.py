import logging

from .device import BaseDevice, DataValue
from .device.command import BaseEntityCommand, CommandId, CommandSet
from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import DeviceInfo
from .entity import BreakerSelect, BaseCommandEntity
from .const import DOMAIN, ECOFLOW_DOMAIN
from .device.breaker import BreakerMode

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    _LOGGER.info("Init selects")
    entities = []

    for device in hass.data[DOMAIN]["devices"]:
        try:
            device_selects = device.selects()
        except Exception as error:
            _LOGGER.exception("Failed to build selects for %s: %s", device.sn, error)
            continue
        _LOGGER.info(
            "Selects for %s: %s",
            device.sn,
            [type(entity).__name__ for entity in device_selects],
        )
        entities.extend(device_selects)
    _LOGGER.info("Total selects registered: %s", len(entities))
    async_add_entities(entities)

class BreakerModeSelect(BreakerSelect):
    _attr_entity_category = EntityCategory.CONFIG
    cmdSet = CommandSet.COMMAND
    cmdId = CommandId.BREAKER_CTRL
    _mode_map = {
        "Auto": (0, None),
        "Grid": (1, 0),
        "Battery": (1, 1),
        "Off": (1, 2),
    }

    async def async_select_option(self, option: str) -> None:
        params = self.breaker_options.get_action_settings(option)
        params.update({ "ch": self.breaker_index })
        command = BaseEntityCommand(self.device.sn, self.cmdSet, self.cmdId, params)
        res = await self.send_command(command)
        if res:
            return


class BreakerCurrentLimitSelect(BaseCommandEntity, SelectEntity):
    _attr_entity_category = EntityCategory.CONFIG
    cmdSet = CommandSet.COMMAND
    cmdId = CommandId.CURRENT_LIMIT
    _attr_options = ["6", "13", "16", "20", "30"]

    def __init__(self, device: BaseDevice, data_key: str, index: int, current_key: str) -> None:
        self.breaker_index = index
        self.current_key = current_key
        self.mode_key = f"breaker_{index}_mode"
        super().__init__(device, data_key)

        if self.mode_key in self.device.data.entity_visibility:
            visible = self.device.data.entity_visibility[self.mode_key]
            self._attr_entity_registry_visible_default = visible
            self._attr_entity_registry_enabled_default = visible
            self.entity_enabled = visible
        else:
            self._attr_entity_registry_visible_default = True
            self._attr_entity_registry_enabled_default = True
        self._attr_unique_id = f"{device.sn}_{data_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(ECOFLOW_DOMAIN, f"{self.device.name}-{self.device.sn[-4:]}")},
            manufacturer="EcoFlow",
            name=self.device.name,
            model=self.device.name,
            serial_number=self.device.sn
        )

    def set_entity_value(self, value: str):
        self._attr_current_option = value
        sensors = self.device.data.mapped_data.get("sensors", {})
        if self.current_key in sensors and value is not None:
            try:
                sensors[self.current_key].value = int(value)
            except ValueError:
                sensors[self.current_key].value = value

    @property
    def device_info(self) -> DeviceInfo | None:
        return self._attr_device_info

    def get_value_from_db(self) -> DataValue:
        sensors = self.device.data.mapped_data.get("sensors", {})
        value = None
        if self.current_key in sensors:
            current_value = sensors[self.current_key].value
            if current_value is not None:
                value = str(current_value)
        return DataValue(f"Breaker {self.breaker_index + 1} current limit select", value, True)

    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options:
            return
        command = BaseEntityCommand(
            self.device.sn,
            self.cmdSet,
            self.cmdId,
            {"chNum": self.breaker_index, "cur": int(option)},
        )
        res = await self.send_command(command)
        if res:
            return
