import logging
from .device import BaseDevice
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)

class EcoflowCoordinatorDataUpdateCoordinator(DataUpdateCoordinator[list[BaseDevice]]):
    def __init__(self, hass, api_client):
        super().__init__(
            hass,
            _LOGGER,
            name="Ecoflow Historic integration",
            # update_interval=timedelta(seconds=30),  # Poll every 30 seconds
        )
        self.api_client = api_client

    async def _async_update_data(self):
        try:
            devices = await self.api_client.devices_list()
            return devices
        except Exception as err:
            raise UpdateFailed(f"Error updating data: {err}")