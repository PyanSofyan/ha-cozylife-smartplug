"""Config Flow CozyLife Smart Plug."""

import logging
import voluptuous as vol

from homeassistant import config_entries

from .cozylife_client import CozyLifeClient
from .const import (
    DOMAIN,
    CONF_IP_ADDRESS,
    CONF_DEVICE_NAME
)

_LOGGER = logging.getLogger(__name__)

class CozyLifeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Config flow for CozyLife Smart Plug."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            ip_address  = user_input[CONF_IP_ADDRESS].strip()
            device_name = user_input[CONF_DEVICE_NAME].strip()

            try:
                client = CozyLifeClient(ip_address)
                if await self.hass.async_add_executor_job(client.test_connection):
                    await self.async_set_unique_id(ip_address)
                    self._abort_if_unique_id_configured()
                    
                    return self.async_create_entry(
                    title=device_name,
                    data={
                        CONF_IP_ADDRESS:  ip_address,
                        CONF_DEVICE_NAME: device_name,
                    }
                )
                else:
                    errors["base"] = "cannot_connect"

            except Exception as e:
                _LOGGER.error(f"Error connecting to device: {e}")
                errors["base"] = "cannot_connect"

        schema = vol.Schema({
            vol.Required(CONF_IP_ADDRESS):  str,
            vol.Required(CONF_DEVICE_NAME): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
    
    async def async_step_import(self, import_config):
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_config)