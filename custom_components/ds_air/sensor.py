"""Support for Daikin sensors."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER, SMALL_VAM_SENSOR_TYPES
from .descriptions import SENSOR_DESCRIPTORS, DsSensorEntityDescription
from .ds_air_service import UNINITIALIZED_VALUE, Sensor, Service, Ventilation, VentilationStatus
from .ds_air_service.dao import build_sensor_device_name
from .ds_air_service.display import display

import logging

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
        self._attr_unit_of_measurement = sensor_info[0] if sensor_info else None
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
