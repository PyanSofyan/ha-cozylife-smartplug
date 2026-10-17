"""CozyLife Smart Plug Integration."""

import logging
from homeassistant.const import Platform
from .const import DOMAIN, CONF_IP_ADDRESS, CONF_DEVICE_TYPE, DEVICE_TYPE_SMART_PLUG, UPDATE_INTERVAL
from .coordinator import CozyLifeCoordinator

_LOGGER = logging.getLogger(__name__)

COORDINATOR = "coordinator"
PLATFORMS  = [Platform.SWITCH, Platform.SENSOR, Platform.SELECT]

async def async_setup(hass, config):
    return True


async def async_setup_entry(hass, entry):
    """Load integration and setup platform."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = CozyLifeCoordinator(
        hass=hass,
        ip_address=entry.data.get(CONF_IP_ADDRESS, ""),
        update_interval=UPDATE_INTERVAL,
        device_type=entry.data.get(CONF_DEVICE_TYPE, DEVICE_TYPE_SMART_PLUG),
        entry=entry,
    )

    try:
        await coordinator.async_initialize()
        await coordinator.async_config_entry_first_refresh()
    except BaseException:
        await coordinator.async_close()
        raise
    
    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
        "data":    entry.data,
    }
  
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await coordinator.async_close()
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise
    return True


async def async_unload_entry(hass, entry):
    """Unload integration and config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await hass.data[DOMAIN][entry.entry_id][COORDINATOR].async_close()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
