import logging

from .coordinator import EcoflowCoordinatorDataUpdateCoordinator
from .device import BaseDevice, DataValue
from .device.command import BaseEntityCommand, CommandId, CommandSet
from homeassistant.const import EntityCategory
from .entity import BreakerSelect
from .const import DOMAIN
from .device.breaker import BreakerMode

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator: EcoflowCoordinatorDataUpdateCoordinator = hass.data[DOMAIN]["coordinator"]
    _LOGGER.info("Init selects")
    entities = []

    for device in coordinator.data:
        entities.extend(device.selects())
    async_add_entities(entities)

class BreakerModeSelect(BreakerSelect):
    _attr_entity_category = EntityCategory.CONFIG
    cmdSet = CommandSet.COMMAND
    cmdId = CommandId.BREAKER_CTRL

    async def async_select_option(self, option: str) -> None:
        params = self.breaker_options.get_action_settings(option)
        params.update({ "ch": self.breaker_index })
        command = BaseEntityCommand(self.device.sn, self.cmdSet, self.cmdId, params)
        res = await self.send_command(command)
        if res:
            self.set_entity_value(option)
            self.async_write_ha_state()