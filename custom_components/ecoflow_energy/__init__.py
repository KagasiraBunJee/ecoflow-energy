import logging

from homeassistant.exceptions import ConfigEntryNotReady
from .api.ecoflow_client import EcoFlowApiClient
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from .coordinator import EcoflowCoordinatorDataUpdateCoordinator

PLATFORMS = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.SELECT
]

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hello World from a config entry."""

    keys = entry.data["keys"]
    client = EcoFlowApiClient(keys["apikey"], keys["secret"], hass)
    if "creds" not in entry.data:
        try:
            _LOGGER.info("Creds not found fetching new one")
            creds = await client.login()
            entry.data["creds"] = creds
        except Exception as error:
            # ConfigEntryNotReady exception is the one for HA to put it to retry to initiate
            raise ConfigEntryNotReady("Timeout while connecting to ecoflow server") from error
    else:
        creds = entry.data["creds"]
        client.set_mqtt_creds(creds)

    client.start()

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    coordinator = EcoflowCoordinatorDataUpdateCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    _LOGGER.info(f"Devices found: {len(coordinator.data)}")

    for device in coordinator.data:
        await device.update_data()
        device.configure(hass)
        await device.connect_mqtt(hass)


    hass.data[DOMAIN]["coordinator"] = coordinator
    # entry.runtime_data = coordinator
    # This creates each HA object for each platform your device requires.
    # It's done by calling the `async_setup_entry` function in each platform module.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
