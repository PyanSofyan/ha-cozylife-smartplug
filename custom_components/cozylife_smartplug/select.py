"""CozyLife Smart Plug — Select Platform."""

import logging
from datetime import timedelta

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_IP_ADDRESS,
    CONF_DEVICE_NAME,
    MANUFACTURER,
    MODEL,
    UPDATE_INTERVAL,
    ON_STATE_ID,
    ON_STATE_NAME,
    MODE_ON_STATE,
    ON_STATE_OPTIONS,
)
from . import COORDINATOR

_LOGGER = logging.getLogger(__name__)

ON_STATE_OPTIONS_REVERSE = {v: k for k, v in ON_STATE_OPTIONS.items()}

async def async_setup_entry(hass, config_entry, async_add_entities):
    entry_hass_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator     = entry_hass_data[COORDINATOR]
    config          = entry_hass_data["data"]

    ip_address  = config[CONF_IP_ADDRESS]
    device_name = config[CONF_DEVICE_NAME]

    client = coordinator.client

    async_add_entities([
        CozyLifeSelect(
            coordinator=coordinator, 
            client=client, 
            ip_address=ip_address, 
            device_name=device_name,
            select_name=ON_STATE_NAME,
            select_icon="mdi:power-plug"
        )
    ], update_before_add=True)

class CozyLifeSelect(CoordinatorEntity, SelectEntity):
    """CozyLife Smart Plug Select Entity."""

    def __init__(self, coordinator, client, ip_address, device_name, select_name, select_icon):
        super().__init__(coordinator)
        self._client      = client
        self._ip_address  = ip_address
        self._device_name = device_name
        self._select_name = select_name
        self._select_icon = select_icon
        self._optimistic_option: str | None = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._ip_address)},
            name=self._device_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def name(self) -> str:
        return self._select_name

    @property
    def icon(self):
        return self._select_icon

    @property
    def unique_id(self) -> str:
        return f"cozylife_plug_{self._ip_address}_{MODE_ON_STATE}"
    
    @property
    def options(self) -> list[str]:
        return list(ON_STATE_OPTIONS.keys())

    @property
    def current_option(self) -> str | None:
        if self._optimistic_option is not None:
            return self._optimistic_option

        if self.coordinator.data is None:
            return None

        value = self.coordinator.data.get(str(ON_STATE_ID))
        return ON_STATE_OPTIONS_REVERSE.get(value) 
    
    def _handle_coordinator_update(self) -> None:
        self._optimistic_option = None
        self.async_write_ha_state()
    
    async def async_select_option(self, option: str) -> None:
        value = ON_STATE_OPTIONS.get(option)
        if value is None:
            _LOGGER.warning("Unknown option: %s", option)
            return

        self._optimistic_option = option
        self.async_write_ha_state()

        attr = [ON_STATE_ID]
        data = {str(ON_STATE_ID): value}
        ack = await self.hass.async_add_executor_job(
            self._client.set_state, attr, data
        )
        if ack:
            self.coordinator.data.update(ack)

        self._optimistic_option = None
        self.async_write_ha_state()