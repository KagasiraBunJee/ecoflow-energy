import logging
from typing import Any

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api.ecoflow_client import EcoFlowApiClient
from .const import DOMAIN

PLATFORMS = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
]

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hello World from a config entry."""

    keys = entry.data["keys"]
    client = EcoFlowApiClient(keys["apikey"], keys["secret"], hass)
    creds = entry.data.get("creds")
    if not creds:
        try:
            creds = await client.login()
            new_data = {"keys": keys, "creds": creds}
            hass.config_entries.async_update_entry(entry, data=new_data)
        except Exception as error:
            raise ConfigEntryNotReady("Timeout while connecting to ecoflow server") from error

    client.set_mqtt_creds(creds)

    devices = await client.devices_list()
    if not devices:
        _LOGGER.warning("No supported devices found.")

    device_map: dict[str, Any] = {device.sn: device for device in devices}

    async def _handle_mqtt(sn: str, suffix: str, payload: dict[str, Any]) -> None:
        device = device_map.get(sn)
        if device is None:
            return
        if suffix == "quota":
            params = payload.get("params", {})
            await device.handle_mqtt_params(params)
        elif suffix == "status":
            device.status = payload.get("params", {}).get("status", device.status)
        device.notify_updated()

    client.start(_handle_mqtt)

    for device in devices:
        device.configure(hass)
        client.subscribe(device.sn)
        try:
            quota_all = await client.get_device_info(device.sn)
            if quota_all:
                await device.apply_quota_all(quota_all)
                device.notify_updated()
        except Exception as error:
            _LOGGER.debug("Quota/all fetch failed for %s: %s", device.sn, error)

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["client"] = client
    hass.data[DOMAIN]["devices"] = devices

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    client = hass.data.get(DOMAIN, {}).get("client")
    if client:
        client.shutdown()
    return unload_ok
