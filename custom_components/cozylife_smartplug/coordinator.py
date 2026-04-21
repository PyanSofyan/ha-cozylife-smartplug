"""CozyLife — DataUpdateCoordinator."""

import logging

from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, CONF_IP_ADDRESS, MANUFACTURER
from .cozylife_client import CozyLifeClient

_LOGGER = logging.getLogger(__name__)

class CozyLifeCoordinator(DataUpdateCoordinator):
    """Coordinator to get data and share it to all entities."""
    def __init__(self, hass, ip_address, update_interval=10):
        super().__init__(
            hass,
            _LOGGER,
            name=f"{MANUFACTURER} {ip_address}",
            update_interval=timedelta(seconds=update_interval),
        )
        self.client = CozyLifeClient(ip_address)

    async def _async_update_data(self):
        data = await self.hass.async_add_executor_job(self.client.query_state)
        if data is None:
            raise UpdateFailed("Failed to fetch data from device")
        
        if self.data:
            merged = {**self.data, **data}
            return merged
        return data