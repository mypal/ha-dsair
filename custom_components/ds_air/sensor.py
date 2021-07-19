"""Support for Xiaomi Aqara sensors."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, CONCENTRATION_PARTS_PER_MILLION,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER, DEVICE_CLASS_CO2,
)

from .ds_air_service.dao import Sensor
from .ds_air_service.service import Service

SENSOR_TYPES = {
    "temp": [TEMP_CELSIUS, None, DEVICE_CLASS_TEMPERATURE, 10],
    "humidity": [PERCENTAGE, None, DEVICE_CLASS_HUMIDITY, 10],
    "pm25": [CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, None, None, 1],
    "co2": [CONCENTRATION_PARTS_PER_MILLION, None, DEVICE_CLASS_CO2, 1],
    "tvoc": [CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER, None, DEVICE_CLASS_PRESSURE, 100],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for Xiaomi devices."""
    entities = []
    for device in Service.get_sensors():
        for key in SENSOR_TYPES:
            entities.append(DsSensor(device, key))
    async_add_entities(entities)


class DsSensor(SensorEntity):
    """Representation of a XiaomiSensor."""

    def __init__(self, device, data_key):
        """Initialize the XiaomiSensor."""
        self._data_key = data_key
        self._name = device.name
        self._is_available = False
        self._state = 0
        self.parse_data(device, True)
        Service.register_sensor_hook(self._name, self.parse_data)

    @property
    def name(self):
        return "%s_%s" % (self._data_key, self._name)

    @property
    def unique_id(self):
        return "%s_%s" % (self._data_key, self._name)

    @property
    def device_id(self):
        return "%s_%s" % (self._data_key, self._name)

    @property
    def available(self):
        return self._is_available

    @property
    def should_poll(self):
        return False

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        try:
            return SENSOR_TYPES.get(self._data_key)[1]
        except TypeError:
            return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        try:
            return SENSOR_TYPES.get(self._data_key)[0]
        except TypeError:
            return None

    @property
    def device_class(self):
        """Return the device class of this entity."""
        return (
            SENSOR_TYPES.get(self._data_key)[2]
            if self._data_key in SENSOR_TYPES
            else None
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def parse_data(self, device: Sensor, not_update: bool = False):
        """Parse data sent by gateway."""
        self._is_available = device.connected and device.switch_on_off
        if Sensor.UNINITIALIZED_VALUE != getattr(device, self._data_key):
            self._state = getattr(device, self._data_key) / SENSOR_TYPES.get(self._data_key)[3]
        if not not_update:
            self.schedule_update_ha_state()
        return True
