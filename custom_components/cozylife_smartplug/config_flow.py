"""Set up a supported account device using only its authorization code."""

from functools import partial

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector, SelectSelectorConfig, SelectSelectorMode,
    TextSelector, TextSelectorConfig, TextSelectorType,
)

from .account import CozyLifeAccount, AccountError, InvalidAuthorization
from .const import (
    DOMAIN, CONF_AUTHORIZATION_CODE, CONF_DEVICE_ID, CONF_DEVICE_KEY,
    CONF_DEVICE_NAME, CONF_DEVICE_TYPE, CONF_IP_ADDRESS, CONF_RELAY_HOST,
    CONF_RELAY_PORT, CONF_WSS_DOMAIN, CONF_DEVICE_MODEL, CONF_ENTITY_ID,
)
from .discovery import async_broadcast_targets, discover_devices

AUTH_SCHEMA = vol.Schema({
    vol.Required(CONF_AUTHORIZATION_CODE): TextSelector(
        TextSelectorConfig(type=TextSelectorType.PASSWORD)
    ),
})


class CozyLifeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._devices = []
        self._local_addresses = {}
        self._reconfigure_entry = None

    async def _async_load_devices(self, code):
        account = CozyLifeAccount(async_get_clientsession(self.hass))
        self._devices = await account.async_devices(code)
        try:
            targets = await async_broadcast_targets(self.hass)
            # Known addresses also help upgrades on networks that filter broadcast.
            entries = list(self._async_current_entries())
            if self._reconfigure_entry:
                entries.append(self._reconfigure_entry)
            targets = list(dict.fromkeys(targets + [
                e.data[CONF_IP_ADDRESS] for e in entries if e.data.get(CONF_IP_ADDRESS)
            ]))
            self._local_addresses = await self.hass.async_add_executor_job(
                partial(discover_devices, targets=targets)
            )
        except OSError:
            self._local_addresses = {}

    async def _async_authorize(self, step_id, user_input):
        errors = {}
        if user_input is not None:
            try:
                await self._async_load_devices(user_input[CONF_AUTHORIZATION_CODE])
            except InvalidAuthorization:
                errors["base"] = "invalid_auth"
            except (AccountError, OSError):
                errors["base"] = "cannot_connect"
            else:
                if not self._devices:
                    return self.async_abort(reason="no_devices")
                if self._reconfigure_entry and self._reconfigure_entry.data.get(CONF_DEVICE_ID):
                    did = self._reconfigure_entry.data[CONF_DEVICE_ID]
                    chosen = next((d for d in self._devices if d.device_id == did), None)
                    if chosen is None:
                        return self.async_abort(reason="device_not_found")
                    return await self._async_configure(chosen)
                return await self.async_step_device()
        return self.async_show_form(step_id=step_id, data_schema=AUTH_SCHEMA, errors=errors)

    async def async_step_user(self, user_input=None):
        return await self._async_authorize("user", user_input)

    async def async_step_reconfigure(self, user_input=None):
        self._reconfigure_entry = self._get_reconfigure_entry()
        return await self._async_authorize("reconfigure", user_input)

    async def async_step_device(self, user_input=None):
        if not self._devices:
            return self.async_abort(reason="no_devices")
        errors = {}
        if user_input is not None:
            chosen = next((d for d in self._devices if d.device_id == user_input.get(CONF_DEVICE_ID)), None)
            if chosen is not None:
                return await self._async_configure(chosen)
            errors["base"] = "device_not_found"
        options = [{
            "value": d.device_id,
            "label": (
                f"{d.name} ({d.model}) — {d.device_id} | "
                f"LAN: {self._local_addresses.get(d.device_id, 'not discovered')} | "
                f"Cloud: {d.relay_host}:{d.relay_port}"
            ),
        } for d in self._devices]
        return self.async_show_form(
            step_id="device", errors=errors,
            data_schema=vol.Schema({vol.Required(CONF_DEVICE_ID): SelectSelector(
                SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
            )}),
        )

    async def _async_configure(self, device):
        local_ip = self._local_addresses.get(device.device_id, "")
        entry = self._reconfigure_entry
        for configured in self._async_current_entries():
            if entry and configured.entry_id == entry.entry_id:
                continue
            if (configured.unique_id == device.device_id
                    or configured.data.get(CONF_DEVICE_ID) == device.device_id
                    or (local_ip and configured.data.get(CONF_IP_ADDRESS) == local_ip)):
                return self.async_abort(reason="already_configured")
        await self.async_set_unique_id(device.device_id)
        data = {
            CONF_DEVICE_ID: device.device_id, CONF_DEVICE_KEY: device.device_key,
            CONF_DEVICE_NAME: device.name, CONF_DEVICE_TYPE: device.device_type,
            CONF_IP_ADDRESS: local_ip, CONF_RELAY_HOST: device.relay_host,
            CONF_RELAY_PORT: device.relay_port, CONF_WSS_DOMAIN: device.wss_domain,
            CONF_DEVICE_MODEL: device.model, CONF_ENTITY_ID: device.device_id,
        }
        # Preserve existing entity IDs/statistics when upgrading a local entry.
        if entry:
            data[CONF_ENTITY_ID] = entry.data.get(CONF_ENTITY_ID) or entry.data.get(CONF_IP_ADDRESS) or device.device_id
            data[CONF_IP_ADDRESS] = local_ip or entry.data.get(CONF_IP_ADDRESS, "")
            return self.async_update_reload_and_abort(
                entry, unique_id=device.device_id, data_updates=data, title=device.name,
            )
        self._abort_if_unique_id_configured()
        # Neither authorization code nor broad account token is persisted.
        return self.async_create_entry(title=device.name, data=data)

    async def async_step_import(self, import_config):
        if CONF_AUTHORIZATION_CODE not in import_config:
            return self.async_abort(reason="authorization_required")
        return await self.async_step_user(import_config)
