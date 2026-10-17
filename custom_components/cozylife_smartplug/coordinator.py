"""Unchanged local TCP transport, LAN relocation, and safe WSS fallback."""

import asyncio
from datetime import timedelta
from functools import partial
import logging
import time

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .cloud_client import CozyLifeCloudClient, CloudError
from .cozylife_client import CozyLifeClient
from .discovery import async_broadcast_targets, discover_devices
from .const import (
    CONF_DEVICE_ID, CONF_DEVICE_KEY, CONF_DEVICE_MODEL,
    CONF_ENTITY_ID, CONF_IP_ADDRESS, CONF_RELAY_HOST, CONF_WSS_DOMAIN,
    DEVICE_TYPE_SMART_PLUG, MANUFACTURER, MODEL, CLOUD_REFRESH_INTERVAL,
    DISCOVERY_INTERVAL, LOCAL_FAILURE_THRESHOLD, LOCAL_RETRY_INTERVAL,
    SWITCH_ID, ON_STATE_ID, CURRENT_ID, POWER_ID, VOLTAGE_ID,
    OVERCURRENT_PROTECT_ID, ENERGY_ID,
)

_LOGGER = logging.getLogger(__name__)


class CozyLifeCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, ip_address, update_interval=10, device_type=None, *, entry=None):
        super().__init__(
            hass, _LOGGER, name=f"{MANUFACTURER} {ip_address}",
            update_interval=timedelta(seconds=update_interval), config_entry=entry,
        )
        config = entry.data if entry else {}
        self._entry = entry
        self.device_id = config.get(CONF_DEVICE_ID)
        self.entity_key = config.get(CONF_ENTITY_ID) or self.device_id or ip_address
        self.model = config.get(CONF_DEVICE_MODEL, MODEL)
        self.device_type = device_type or DEVICE_TYPE_SMART_PLUG
        self.client = CozyLifeClient(ip_address, device_type=self.device_type)
        self._io_lock = asyncio.Lock()
        self._last_discovery = None
        self._targets = ["255.255.255.255"]
        self._local_failures = 0
        self._next_local_probe = 0
        self._last_cloud_query = None
        self._cloud_data = {}
        self.connection_path = None
        self.cloud = None
        if self.device_id and config.get(CONF_DEVICE_KEY) and config.get(CONF_WSS_DOMAIN):
            self.cloud = CozyLifeCloudClient(
                async_get_clientsession(hass), self.device_id, config[CONF_DEVICE_KEY],
                config[CONF_WSS_DOMAIN], self._on_cloud_data, self._on_cloud_disconnect,
            )

    @property
    def transport_attributes(self):
        return {"connection_path": self.connection_path, "local_ip": self.client.ip or None,
                "cloud_host": self._entry.data.get(CONF_RELAY_HOST) if self._entry else None}

    @property
    def _query_attrs(self):
        if self.device_type != DEVICE_TYPE_SMART_PLUG:
            return [SWITCH_ID, ON_STATE_ID]
        return [SWITCH_ID, ON_STATE_ID, CURRENT_ID, POWER_ID, VOLTAGE_ID,
                OVERCURRENT_PROTECT_ID, ENERGY_ID]

    async def async_initialize(self):
        if self.device_id:
            try:
                self._targets = await async_broadcast_targets(self.hass)
            except OSError:
                self._targets = ["255.255.255.255"]
            await self._async_rediscover()
        if self.cloud:
            self.cloud.async_start()

    async def async_close(self):
        if self.cloud:
            await self.cloud.async_close()

    def _set_path(self, path):
        if self.connection_path != path:
            _LOGGER.info("CozyLife connection path changed to %s", path)
        self.connection_path = path

    def _merge(self, data):
        return {**(self.data or {}), **data}

    def _on_cloud_data(self, data):
        self._cloud_data.update(data)
        if self.data is not None:
            # Do not reset the coordinator's polling timer on every push:
            # local recovery probes must still run even with frequent reports.
            self.data = self._merge(data)
            self.last_update_success = True
            self.last_exception = None
            self.async_update_listeners()

    def _on_cloud_disconnect(self):
        self._cloud_data.clear()
        self._last_cloud_query = None
        if self.connection_path == "cloud":
            self.async_set_update_error(UpdateFailed("Cloud status stream unavailable"))

    async def _async_rediscover(self):
        if not self.device_id:
            return False
        now = time.monotonic()
        if self._last_discovery is not None and now - self._last_discovery < DISCOVERY_INTERVAL:
            return False
        self._last_discovery = now
        try:
            targets = list(dict.fromkeys(self._targets + ([self.client.ip] if self.client.ip else [])))
            found = await self.hass.async_add_executor_job(partial(discover_devices, targets=targets))
        except OSError:
            return False
        address = found.get(self.device_id)
        # Do not keep controlling an IP that discovery identifies as another device.
        if not address and self.client.ip in found.values():
            address = ""
        if address is None or address == self.client.ip:
            return False
        self.client = CozyLifeClient(address, device_type=self.device_type)
        self._local_failures = 0
        self._next_local_probe = 0
        if self._entry:
            self.hass.config_entries.async_update_entry(
                self._entry, data={**self._entry.data, CONF_IP_ADDRESS: address},
            )
        return True

    def _local_failed(self):
        self._local_failures += 1
        if self.cloud and self._local_failures >= LOCAL_FAILURE_THRESHOLD:
            self._next_local_probe = time.monotonic() + LOCAL_RETRY_INTERVAL

    async def _async_local_state(self):
        if not self.client.ip or time.monotonic() < self._next_local_probe:
            return None
        data = await self.hass.async_add_executor_job(self.client.query_state)
        if data is None:
            self._local_failed()
            if await self._async_rediscover() and self.client.ip:
                data = await self.hass.async_add_executor_job(self.client.query_state)
        if data is not None:
            self._local_failures = 0
            self._next_local_probe = 0
        return data

    async def _async_cloud_state(self, *, force=False):
        if not self.cloud:
            raise CloudError("Cloud is not configured")
        if (not force and self.cloud.connected and self._last_cloud_query is not None
                and time.monotonic() - self._last_cloud_query < CLOUD_REFRESH_INTERVAL
                and all(str(attr) in self._cloud_data for attr in self._query_attrs)):
            return dict(self._cloud_data)
        data = await self.cloud.async_query_state(self._query_attrs)
        self._cloud_data.update(data)
        self._last_cloud_query = time.monotonic()
        return dict(self._cloud_data)

    async def _async_update_data(self):
        async with self._io_lock:
            await self._async_rediscover()
            data = await self._async_local_state()
            if data is not None:
                self._set_path("local")
                return self._merge(data)
            try:
                data = await self._async_cloud_state()
            except CloudError:
                raise UpdateFailed("Local and cloud paths are unavailable") from None
            self._set_path("cloud")
            return self._merge(data)

    async def async_set_state(self, attr, data):
        """Choose a path before writing; never replay an ambiguous local write."""
        async with self._io_lock:
            await self._async_rediscover()
            if not self.cloud:
                result = await self.hass.async_add_executor_job(self.client.set_state, attr, data)
                if result is None:
                    raise HomeAssistantError("Local command failed")
                self._set_path("local")
                self.async_set_updated_data(self._merge(result))
                return result
            # The unchanged TCP client does not distinguish connection failure
            # from lost ACK. A read-only preflight makes safe fallback possible.
            local = await self._async_local_state()
            if local is None:
                try:
                    result = await self.cloud.async_set_state(attr, data)
                except CloudError:
                    raise HomeAssistantError("Cloud command failed; it was not retried") from None
                self._set_path("cloud")
            else:
                result = await self.hass.async_add_executor_job(self.client.set_state, attr, data)
                self._last_cloud_query = None
                if result is None:
                    self._local_failed()
                    # Read-only reconciliation, never a second write.
                    result = await self._async_local_state()
                    if result is None or not all(result.get(k) == v for k, v in data.items()):
                        try:
                            result = await self._async_cloud_state(force=True)
                        except CloudError:
                            result = None
                    if result is None or not all(result.get(k) == v for k, v in data.items()):
                        raise HomeAssistantError("Cannot confirm local command; it was not repeated through cloud")
                self._set_path("local")
            self.async_set_updated_data(self._merge(result))
            return result
