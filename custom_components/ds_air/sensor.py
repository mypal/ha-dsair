import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENTRY_TYPE,
    DOMAIN,
    ENTRY_TYPE_POWER,
    MANUFACTURER,
    SMALL_VAM_SENSOR_TYPES,
)
from .coordinator import DsAirPowerCoordinator
from .descriptions import SENSOR_DESCRIPTORS, DsSensorEntityDescription
from .ds_air_service import UNINITIALIZED_VALUE, Sensor, Service, Ventilation, VentilationStatus
from .ds_air_service.dao import build_sensor_device_name
from .ds_air_service.display import display

try:
    from homeassistant.const import UnitOfEnergy
    ENERGY_KWH = UnitOfEnergy.KILO_WATT_HOUR
except ImportError:
    ENERGY_KWH = "kWh"

try:
    STATE_CLASS_TOTAL = SensorStateClass.TOTAL
except (ImportError, AttributeError):
    STATE_CLASS_TOTAL = "total"

try:
    STATE_CLASS_TOTAL_INCREASING = SensorStateClass.TOTAL_INCREASING
except (ImportError, AttributeError):
    STATE_CLASS_TOTAL_INCREASING = "total_increasing"

_LOGGER = logging.getLogger(__name__)


def _log(s: str):
    s = str(s)
    for i in s.split("\n"):
        _LOGGER.debug(i)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Perform the setup for Daikin devices."""
    if config_entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_POWER or CONF_HOST not in config_entry.data:
        coordinator: DsAirPowerCoordinator = hass.data[DOMAIN][config_entry.entry_id]
        async_add_entities([
            DsAirYesterdayPowerSensor(coordinator, config_entry),
            DsAirMonthPowerSensor(coordinator, config_entry),
        ])
        return

    service: Service = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for device in service.get_sensors():
        for key in SENSOR_DESCRIPTORS:
            if config_entry.data.get(key):
                entities.append(
                    DsSensor(service, device, SENSOR_DESCRIPTORS.get(key))
                )
    # 新风传感器
    for vent in service.get_ventilations():
        if vent.is_small_vam:
            for key in SMALL_VAM_SENSOR_TYPES:
                entities.append(DsVentSensor(service, vent, key))
    async_add_entities(entities)


class DsSensor(SensorEntity):
    """Representation of a Daikin Sensor."""

    entity_description: DsSensorEntityDescription

    _attr_should_poll: bool = False

    def __init__(
        self,
        service: Service,
        device: Sensor,
        description: DsSensorEntityDescription,
    ):
        """Initialize the Daikin Sensor."""
        self.entity_description = description
        self._data_key: str = description.key

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            name=build_sensor_device_name(device.alias),
            manufacturer=MANUFACTURER,
            via_device=(DOMAIN, device.gateway_id),
        )

        self._attr_unique_id = f"{self._data_key}_{device.unique_id}"

        self._parse_data(device)
        service.register_sensor_hook(device.unique_id, self._handle_sensor_hook)

    def _parse_data(self, device: Sensor) -> None:
        """Parse data sent by gateway."""
        self._attr_available = device.connected
        if (data := getattr(device, self._data_key)) != UNINITIALIZED_VALUE:
            self._attr_native_value = self.entity_description.value_fn(data)

    def _handle_sensor_hook(self, device: Sensor) -> None:
        self._parse_data(device)
        self.schedule_update_ha_state()


class DsVentSensor(SensorEntity):
    """Representation of a Daikin Ventilation Sensor."""

    _attr_should_poll: bool = False

    def __init__(self, service: Service, device: Ventilation, data_key: str):
        """Initialize the Daikin Ventilation Sensor."""
        self._data_key = data_key
        self._device = device
        self._service = service

        sensor_info = SMALL_VAM_SENSOR_TYPES.get(data_key)
        self._attr_has_entity_name = True
        self._attr_translation_key = sensor_info[1] if sensor_info else data_key
        self._attr_native_unit_of_measurement = sensor_info[0] if sensor_info else None
        self._attr_device_class = sensor_info[2] if sensor_info else None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            name=f"新风 {device.alias}",
            manufacturer=MANUFACTURER,
            via_device=(DOMAIN, device.gateway_id),
        )

        self._attr_unique_id = f"{self._data_key}_{device.unique_id}"

        self._parse_data(device.status)
        service.register_vent_hook(device, self._handle_vent_hook)

    def _parse_data(self, status: VentilationStatus) -> None:
        """Parse data sent by gateway."""
        value = getattr(status, self._data_key, None)
        if value is None or value == UNINITIALIZED_VALUE:
            self._attr_native_value = None
        else:
            sensor_info = SMALL_VAM_SENSOR_TYPES.get(self._data_key)
            if sensor_info:
                divisor = sensor_info[3]
                self._attr_native_value = value / divisor if divisor else value

    def _handle_vent_hook(self, **kwargs) -> None:
        """Handle ventilation status change callback."""
        _log("vent sensor hook:")
        if kwargs.get("status") is not None:
            status: VentilationStatus = kwargs["status"]
            self._parse_data(status)
            _log(display(kwargs["status"]))
        elif kwargs.get("vent") is not None:
            vent: Ventilation = kwargs["vent"]
            self._parse_data(vent.status)
            _log(display(vent.status))
        self.schedule_update_ha_state()


class DsAirYesterdayPowerSensor(CoordinatorEntity[DsAirPowerCoordinator], SensorEntity):
    """大金金制空气昨日用电传感器"""

    _attr_has_entity_name = True
    _attr_translation_key = "yesterday_power"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = ENERGY_KWH
    _attr_state_class = STATE_CLASS_TOTAL

    def __init__(
        self,
        coordinator: DsAirPowerCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the yesterday power sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_name = "昨日用电"
        self._attr_unique_id = f"dsair_power_{coordinator.home_id}_yesterday"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"power_{coordinator.home_id}")},
            name=f"金制空气 ({coordinator.home_name})",
            manufacturer=MANUFACTURER,
            model="金制空气云服务",
        )

    @property
    def native_value(self) -> float | None:
        """Return yesterday's power consumption in kWh."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("yesterday_used")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return {}
        data = self.coordinator.data
        return {
            "home_id": data.get("home_id"),
            "home_name": data.get("home_name"),
            "yesterday_date": data.get("yesterday_date"),
            "yesterday_used": data.get("yesterday_used"),
            "month_total": data.get("total"),
            "price": data.get("price"),
            "estimated_cost": data.get("estimated_cost"),
            "last_updated": data.get("last_updated"),
        }


class DsAirMonthPowerSensor(CoordinatorEntity[DsAirPowerCoordinator], SensorEntity):
    """大金金制空气当月累计用电传感器"""

    _attr_has_entity_name = True
    _attr_translation_key = "month_power"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = ENERGY_KWH
    _attr_state_class = STATE_CLASS_TOTAL_INCREASING

    def __init__(
        self,
        coordinator: DsAirPowerCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the month power sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_name = "当月累计用电"
        self._attr_unique_id = f"dsair_power_{coordinator.home_id}_month"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"power_{coordinator.home_id}")},
            name=f"金制空气 ({coordinator.home_name})",
            manufacturer=MANUFACTURER,
            model="金制空气云服务",
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        self.coordinator.set_month_statistic_id(self.entity_id)
        if self.coordinator.data:
            from datetime import datetime
            self.hass.async_create_task(
                self.coordinator.async_import_month_statistics(
                    self.coordinator.data.get("year", datetime.now().year),
                    self.coordinator.data.get("month", datetime.now().month),
                    self.coordinator.data,
                    statistic_id=self.entity_id,
                )
            )

    @property
    def native_value(self) -> float | None:
        """Return current month's accumulated power consumption in kWh."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("total")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attributes including monthly total, unit price, and daily breakdown."""
        if not self.coordinator.data:
            return {}
        data = self.coordinator.data
        return {
            "home_id": data.get("home_id"),
            "home_name": data.get("home_name"),
            "year": data.get("year"),
            "month": data.get("month"),
            "total": data.get("total"),
            "month_total": data.get("total"),
            "price": data.get("price"),
            "estimated_cost": data.get("estimated_cost"),
            "daily_consumptions": data.get("consumptions", []),
            "last_updated": data.get("last_updated"),
        }


# 保持向下兼容别名
DsAirPowerSensor = DsAirYesterdayPowerSensor

