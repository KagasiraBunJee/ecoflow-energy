import logging

from .coordinator import EcoflowCoordinatorDataUpdateCoordinator
from .device import BaseDevice
from homeassistant.const import EntityCategory
from .entity import BaseSwitch
from .device.command import BaseEntityCommand, CommandId, CommandSet
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator: EcoflowCoordinatorDataUpdateCoordinator = hass.data[DOMAIN]["coordinator"]
    _LOGGER.info("Init switches")
    entities = []

    for device in coordinator.data:
        entities.extend(device.switches())
    async_add_entities(entities)

class EnableSwitch(BaseSwitch):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, device: BaseDevice, data_key, cmd_set, cmd_id, args_on: dict, args_off: dict) -> None:
        super().__init__(device, data_key)
        _LOGGER.info("init eps switch")
        self.cmd_set = cmd_set
        self.cmd_id = cmd_id
        self.args_on = args_on
        self.args_off = args_off

    async def switch(self, status: bool):
        cmdSet = CommandSet(self.cmd_set)
        cmdId = CommandId(self.cmd_id)
        data = self.args_on if status == True else self.args_off

        command = BaseEntityCommand(self.device.sn, cmdSet, cmdId, data)
        res = await self.send_command(command)
        if res:
            self.set_entity_value(status)
            self.async_write_ha_state()
