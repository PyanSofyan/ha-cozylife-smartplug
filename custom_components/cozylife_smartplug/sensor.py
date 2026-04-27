"""CozyLife Smart Plug — Sensor Platform."""

import logging
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.util import dt as dt_util
from homeassistant.helpers.restore_state import RestoreEntity
from datetime import timezone
from homeassistant.const import (
    UnitOfPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy
)
from .const import (
    DOMAIN,
    CONF_IP_ADDRESS,
    CONF_DEVICE_NAME,
    MANUFACTURER,
    MODEL,
    UPDATE_INTERVAL,
    CURRENT_ID,
    CURRENT_NAME,
    POWER_ID,
    POWER_NAME,
    VOLTAGE_ID,
    VOLTAGE_NAME,
    ENERGY_ID,
    ENERGY_NAME,
    ENERGY_TODAY,
    ENERGY_MONTH
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
        CozyLifeSensor(
            coordinator=coordinator, 
            client=client, 
            ip_address=ip_address, 
            device_name=device_name, 
            sensor_id=CURRENT_ID, 
            sensor_name=CURRENT_NAME,
            sensor_icon="mdi:current-ac",
            sensor_class=SensorDeviceClass.CURRENT,
            sensor_unit=UnitOfElectricCurrent.AMPERE,
            sensor_state_class=SensorStateClass.MEASUREMENT
        ),
        CozyLifeSensor(
            coordinator=coordinator, 
            client=client, 
            ip_address=ip_address, 
            device_name=device_name, 
            sensor_id=POWER_ID, 
            sensor_name=POWER_NAME,            
            sensor_icon="mdi:flash",
            sensor_class=SensorDeviceClass.POWER, 
            sensor_unit=UnitOfPower.WATT,
            sensor_state_class=SensorStateClass.MEASUREMENT
        ),
        CozyLifeSensor(
            coordinator=coordinator, 
            client=client, 
            ip_address=ip_address, 
            device_name=device_name, 
            sensor_id=VOLTAGE_ID, 
            sensor_name=VOLTAGE_NAME,
            sensor_icon="mdi:sine-wave",
            sensor_class=SensorDeviceClass.VOLTAGE,
            sensor_unit=UnitOfElectricPotential.VOLT,
            sensor_state_class=SensorStateClass.MEASUREMENT
        ),
        CozyLifeTotalEnergySensor(
            coordinator=coordinator, 
            client=client, 
            ip_address=ip_address, 
            device_name=device_name
        ),
        CozyLifePeriodEnergySensor(
            coordinator=coordinator,
            ip_address=ip_address, 
            device_name=device_name,
            period="day",
            sensor_name=ENERGY_TODAY
        ),
        CozyLifePeriodEnergySensor(
            coordinator=coordinator,
            ip_address=ip_address, 
            device_name=device_name,
            period="month",
            sensor_name=ENERGY_MONTH
        ),
    ], update_before_add=True)

class CozyLifeSensor(CoordinatorEntity, SensorEntity):
    """CozyLife Smart Plug Sensor Entity."""

    def __init__(
            self, 
            coordinator, 
            client, 
            ip_address, 
            device_name,
            sensor_id, 
            sensor_name, 
            sensor_icon, 
            sensor_class, 
            sensor_unit,
            sensor_state_class
        ):

        super().__init__(coordinator)
        self._client      = client
        self._ip_address  = ip_address
        self._device_name = device_name
        self._sensor_id   = sensor_id
        self._sensor_name = sensor_name
        self._sensor_icon = sensor_icon
        
        self._attr_native_unit_of_measurement = sensor_unit
        self._attr_device_class = sensor_class
        self._attr_state_class = sensor_state_class

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
        return self._sensor_name

    @property
    def icon(self):
        return self._sensor_icon
        
    @property
    def unique_id(self) -> str:
        return f"cozylife_plug_{self._ip_address}_{self._sensor_id}"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get(str(self._sensor_id))
        if self._sensor_id in (CURRENT_ID, ENERGY_ID):
            return float(value) / 1000.0
        return value

class CozyLifeTotalEnergySensor(CoordinatorEntity, SensorEntity, RestoreEntity):
    """Total energy — calculated from daily usage (UTC), never reset, continuously accumulated."""

    def __init__(self, coordinator, client, ip_address, device_name):
        super().__init__(coordinator)
        self._client      = client
        self._ip_address  = ip_address
        self._device_name = device_name

        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

        self._total: float = 0.0
        self._last_raw: float | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state and last_state.attributes:
            try:
                self._total    = float(last_state.attributes.get("total_kwh", 0.0))
                last_raw       = last_state.attributes.get("last_raw")
                self._last_raw = float(last_raw) if last_raw is not None else None
                _LOGGER.debug("Restored total energy: %.3f kWh", self._total)
            except (ValueError, TypeError) as e:
                _LOGGER.warning("Failed restore state: %s", e)

    @property
    def native_value(self) -> float | None:
        if self._last_raw is None:
            return None
        return round(self._total, 3)

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
        return ENERGY_NAME

    @property
    def icon(self):
        return "mdi:lightning-bolt"

    @property
    def unique_id(self) -> str:
        return f"cozylife_plug_{self._ip_address}_{ENERGY_ID}"

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "total_kwh": self._total,
            "last_raw":  self._last_raw,
        }
        

    def _is_utc_midnight_reset(self, current_raw: float, last_raw: float) -> bool:
        """Detect whether the value drop is due to the 00:00 UTC reset."""
        now_utc = dt_util.utcnow()
        
        # Tolerance window: 00:00 - 00:05 UTC
        is_near_midnight = (
            now_utc.hour == 0 and now_utc.minute <= 5
        )
        
        # Reset UTC: value drops significantly AND time is near midnight UTC
        drop = last_raw - current_raw
        is_significant_drop = current_raw < (last_raw * 0.5)  # down more than 50%
        
        return is_near_midnight and is_significant_drop

    def _handle_coordinator_update(self) -> None:
        if not self.coordinator.data:
            super()._handle_coordinator_update()
            return

        raw_value = self.coordinator.data.get(str(ENERGY_ID))
        if raw_value is None:
            super()._handle_coordinator_update()
            return

        current_raw = float(raw_value) / 1000.0

        if self._last_raw is not None:
            if current_raw >= self._last_raw:
                # Normal — add difference
                self._total += current_raw - self._last_raw

            elif self._is_utc_midnight_reset(current_raw, self._last_raw):
                # Reset 00:00 UTC — add current_raw as new consumption
                _LOGGER.debug(
                    "UTC midnight reset: last=%.3f current=%.3f",
                    self._last_raw, current_raw
                )
                self._total += current_raw

            else:
                # Power loss — value drops but not midnight reset
                _LOGGER.debug(
                    "Power loss detected: last=%.3f current=%.3f, skip accumulation",
                    self._last_raw, current_raw
                )

        self._last_raw = current_raw
        super()._handle_coordinator_update()

class CozyLifePeriodEnergySensor(CoordinatorEntity, SensorEntity):
    """Statistic-based Daily & Monthly Energy Sensor."""

    def __init__(self, coordinator, ip_address, device_name, period, sensor_name):
        super().__init__(coordinator)
        self._ip_address      = ip_address
        self._device_name     = device_name
        self._period          = period  # "day" or "month"
        self._sensor_name     = sensor_name
        self._value: float | None = None
        self._source_entity_id:str | None = None

        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

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
        return self._sensor_name

    @property
    def unique_id(self) -> str:
        return f"cozylife_plug_{self._ip_address}_energy_{self._period}"

    @property
    def icon(self):
        return "mdi:lightning-bolt"

    @property
    def native_value(self) -> float | None:
        return self._value

    def _get_period_start(self):
        """Calculate the start of the period based on the HA timezone."""
        now = dt_util.now()
        if self._period == "day":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:  # month
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        entity_registry  = er.async_get(self.hass)
        source_unique_id = f"cozylife_plug_{self._ip_address}_{ENERGY_ID}"
        self._source_entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, source_unique_id
        )

        if not self._source_entity_id:
            _LOGGER.warning("Source entity not found: %s", source_unique_id)

    async def _async_update_value(self) -> None:
        """Get data from recorder statistics."""
        start = self._get_period_start()
        end   = dt_util.now()
        try:
            recorder = get_instance(self.hass)
            if not recorder:
                _LOGGER.debug("Recorder not ready")
                self._value = None
                return

            stats = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period,
                self.hass,
                start,
                end,
                {self._source_entity_id},
                "hour", 
                None,
                {"change"},
            )

            entity_stats = stats.get(self._source_entity_id, [])
            if entity_stats:
                total = sum(
                    s["change"] for s in entity_stats 
                    if s.get("change") is not None
                )
                self._value = round(total, 3)
            else:
                self._value = 0.0

        except Exception as e:
            _LOGGER.debug("Failed get statistics %s: %s", self._source_entity_id, e)
            self._value = None

    def _handle_coordinator_update(self) -> None:
        self.hass.async_create_task(self._async_update_statistics())
        super()._handle_coordinator_update()

    async def _async_update_statistics(self) -> None:
        await self._async_update_value()
        self.async_write_ha_state()