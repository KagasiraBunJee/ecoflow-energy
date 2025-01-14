from .api.ecoflow_client import EcoFlowApiClient
from homeassistant import config_entries
from .const import DOMAIN  # pylint:disable=unused-import
import voluptuous as vol

import logging

_LOGGER = logging.getLogger(__name__)

class EcoflowEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Example config flow."""
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input):
        data_schema = {
            vol.Required("apikey"): str,
            vol.Required("secret"): str,
        }
        errors = {}

        if user_input is not None:
            apikey = user_input["apikey"]
            secret = user_input["secret"]

            client = EcoFlowApiClient(apikey, secret, None)
            mqtt_info = await client.login()
            if mqtt_info:
                data = { "keys": user_input, "creds": mqtt_info }
                _LOGGER.info("Load from config")
                return self.async_create_entry(title="Ecoflow Energy", data=data)
            else:
                errors["base"] = "Wrong credentials"

        return self.async_show_form(step_id="user", data_schema=vol.Schema(data_schema), errors=errors)