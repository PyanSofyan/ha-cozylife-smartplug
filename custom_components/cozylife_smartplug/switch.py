"""CozyLife Smart Plug — Switch Platform."""

import logging
from datetime import timedelta

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_IP_ADDRESS,
    CONF_DEVICE_NAME,
    MANUFACTURER,
    MODEL,
    UPDATE_INTERVAL,
    SWITCH_ID,
    SWITCH_NAME,
    OVERCURRENT_PROTECT_ID,
    OVERCURRENT_PROTECT_NAME
)
from . import COORDINATOR

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=UPDATE_INTERVAL)


async def async_setup_entry(hass, config_entry, async_add_entities):
    entry_hass_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator     = entry_hass_data[COORDINATOR]
    config          = entry_hass_data["data"]

    ip_address  = config[CONF_IP_ADDRESS]
    device_name = config[CONF_DEVICE_NAME]

    client = coordinator.client

    async_add_entities([
        CozyLifeSwitch(
            coordinator=coordinator, 
            client=client, 
            ip_address=ip_address, 
            device_name=device_name,  
            switch_id=SWITCH_ID, 
            switch_name=SWITCH_NAME, 
            switch_icon="mdi:power"
        ),

        CozyLifeSwitch(
            coordinator=coordinator, 
            client=client, 
            ip_address=ip_address, 
            device_name=device_name,  
            switch_id=OVERCURRENT_PROTECT_ID, 
            switch_name=OVERCURRENT_PROTECT_NAME, 
            switch_icon="mdi:wave-undercurrent"
        ),
    ], update_before_add=True)


class CozyLifeSwitch(CoordinatorEntity, SwitchEntity):
    """CozyLife Smart Plug Switch Entity."""

    def __init__(
            self, 
            coordinator, 
            client, 
            ip_address, 
            device_name,
            switch_id, 
            switch_name, 
            switch_icon
    ):

        super().__init__(coordinator)
        self._client      = client
        self._ip_address  = ip_address
        self._device_name = device_name
        self._switch_id   = switch_id
        self._switch_name = switch_name
        self._switch_icon = switch_icon
        self._optimistic_state: bool | None = None

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
        return self._switch_name

    @property
    def icon(self):
        return self._switch_icon
        
    @property
    def unique_id(self) -> str:
        return f"cozylife_plug_{self._ip_address}_{self._switch_id}"

    @property
    def is_on(self) -> bool:
        if self._optimistic_state is not None:
            return self._optimistic_state
        if self.coordinator.data is None:
            return False
        state = self.coordinator.data.get(str(self._switch_id))
        return state > 0 if state is not None else False
    
    def _handle_coordinator_update(self) -> None:
        self._optimistic_state = None
        self.async_write_ha_state()

    async def _async_set_switch(self, value: int) -> None:
        attr = [self._switch_id]
        data = {str(self._switch_id): value}
        ack = await self.hass.async_add_executor_job(
            self._client.set_state, attr, data
        )
        if ack:
            self.coordinator.data.update(ack)
        
        self._optimistic_state = None
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        self._optimistic_state = True
        self.async_write_ha_state()
        await self._async_set_switch(1)

    async def async_turn_off(self, **kwargs):
        self._optimistic_state = False
        self.async_write_ha_state()
        await self._async_set_switch(0)
        