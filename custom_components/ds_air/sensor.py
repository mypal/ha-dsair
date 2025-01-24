"""Support for Daikin sensors."""
from typing import Optional

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, SENSOR_TYPES, SMALL_VAM_SENSOR_TYPES
from .ds_air_service.dao import Sensor, UNINITIALIZED_VALUE, Ventilation, VentilationStatus
from .ds_air_service.service import Service


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for Daikin devices."""
    entities = []
    for device in Service.get_sensors():
        for key in SENSOR_TYPES:
            if config_entry.data.get(key):
                entities.append(DsSensor(device, key))

    for vent in Service.get_ventilations():
        if vent.is_small_vam:
            for key in SMALL_VAM_SENSOR_TYPES:
                entities.append(DsVentSensor(vent, key))

    async_add_entities(entities)


class DsSensor(SensorEntity):
    """Representation of a DaikinSensor."""

    def __init__(self, device: Sensor, data_key):
        """Initialize the DaikinSensor."""
        self._data_key = data_key
        self._name = device.alias
        self._unique_id = device.unique_id
        self._is_available = False
        self._state = 0
        self.parse_data(device, True)
        Service.register_sensor_hook(device.unique_id, self.parse_data)

    @property
    def name(self):
        return "%s_%s" % (self._data_key, self._unique_id)

    @property
    def unique_id(self):
        return "%s_%s" % (self._data_key, self._unique_id)

    @property
    def device_info(self) -> Optional[DeviceInfo]:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": "传感器%s" % self._name,
            "manufacturer": "Daikin Industries, Ltd."
        }

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
    def state_class(self):
        """Return the state class of this entity."""
        return SensorStateClass.MEASUREMENT

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def parse_data(self, device: Sensor, not_update: bool = False):
        """Parse data sent by gateway."""
        self._is_available = device.connected
        if UNINITIALIZED_VALUE != getattr(device, self._data_key):
            scaling = SENSOR_TYPES.get(self._data_key)[3]
            if type(scaling) != int and type(scaling) != float:
                self._state = str(getattr(device, self._data_key))
            else:
                self._state = getattr(device, self._data_key) / scaling

        if not not_update:
            self.schedule_update_ha_state()
        return True

class DsVentSensor(SensorEntity):
    """Representation of a sensor from DaikinVentilation."""
    def __init__(self, device: Ventilation, data_key: str):
        """Initialize the sensor from DaikinVentilation."""
        self._data_key = data_key
        self._name = device.alias
        self._unique_id = device.unique_id
        self._is_available = False
        self._state = 0
        self._device = device
        self.parse_data(device.status, True)
        Service.register_vent_hook(device, self.parse_data)

    @property
    def name(self):
        return "%s_%s" % (self._data_key, self._unique_id)

    @property
    def unique_id(self):
        return "%s_%s" % (self._data_key, self._unique_id)
    
    @property
    def device_info(self) -> Optional[DeviceInfo]:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": "新风%s" % self._name,
            "manufacturer": "Daikin Industries, Ltd."
        }

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
            return SMALL_VAM_SENSOR_TYPES.get(self._data_key)[1]
        except TypeError:
            return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        try:
            return SMALL_VAM_SENSOR_TYPES.get(self._data_key)[0]
        except TypeError:
            return None

    @property
    def device_class(self):
        """Return the device class of this entity."""
        return (
            SMALL_VAM_SENSOR_TYPES.get(self._data_key)[2]
            if self._data_key in SMALL_VAM_SENSOR_TYPES
            else None
        )
    
    @property
    def state_class(self):
        """Return the state class of this entity."""
        return SensorStateClass.MEASUREMENT

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def parse_data(self, status: VentilationStatus, not_update: bool = False):
        """Parse data sent by gateway."""
        value = getattr(status, self._data_key)
        if value is not None and UNINITIALIZED_VALUE != value:
            self._is_available = True
            setattr(self._device.status, self._data_key, value)
            if type(SMALL_VAM_SENSOR_TYPES.get(self._data_key)[3]) != int:
                self._state = str(value)
            else:
                self._state = value / SMALL_VAM_SENSOR_TYPES.get(self._data_key)[3]

        if not not_update:
            self.schedule_update_ha_state()
        return True