"""Support for Daikin sensors."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER, get_gateway_name
from .descriptions import SENSOR_DESCRIPTORS, DsSensorEntityDescription
from .ds_air_service import UNINITIALIZED_VALUE, Sensor, Service
from .ds_air_service.dao import build_prefixed_unique_id


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Perform the setup for Daikin devices."""
    service: Service = hass.data[DOMAIN][config_entry.entry_id]
    gateway_name = get_gateway_name(
        hass.config.language, config_entry.data[CONF_HOST], config_entry.title
    )
    entities = []
    for device in service.get_sensors():
        for key in SENSOR_DESCRIPTORS:
            if config_entry.data.get(key):
                entities.append(
                    DsSensor(service, device, SENSOR_DESCRIPTORS.get(key), gateway_name)
                )
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
        gateway_name: str,
    ):
        """Initialize the Daikin Sensor."""
        self.entity_description = description
        self._data_key: str = description.key

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            name=f"{gateway_name} {device.alias}",
            manufacturer=MANUFACTURER,
            via_device=(DOMAIN, device.gateway_id),
        )

        self._attr_unique_id = build_prefixed_unique_id(
            self._data_key, device.unique_id
        )
        self.entity_id = (
            f"sensor.daikin_{device.gateway_id}_{device.mac}_{self._data_key}"
        )

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
