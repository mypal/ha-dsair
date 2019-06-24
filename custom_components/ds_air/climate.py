"""
Demo platform that offers a fake climate device.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_FAN_MODE,
    SUPPORT_OPERATION_MODE, SUPPORT_SWING_MODE,
    SUPPORT_ON_OFF, SUPPORT_TARGET_HUMIDITY_LOW, SUPPORT_TARGET_HUMIDITY_HIGH)
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE

from .ds_air_service.ctrl_enum import EnumControl
from .ds_air_service.dao import AirCon

SUPPORT_FLAGS = SUPPORT_TARGET_HUMIDITY_LOW | SUPPORT_TARGET_HUMIDITY_HIGH


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Demo climate devices."""
    from .ds_air_service.service import Service
    Service.init()
    climates = []
    for aircon in Service.get_new_aircons():
        climates.append(DsAir(aircon))
    add_entities(climates)


class DsAir(ClimateDevice):
    """Representation of a demo climate device."""

    def __init__(self, aircon: AirCon):
        """Initialize the climate device."""
        print(aircon.alias)
        self._name = aircon.alias
        flag = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_OPERATION_MODE | SUPPORT_SWING_MODE | SUPPORT_ON_OFF
        self._support_flags = flag
        status = aircon.status
        self._target_temperature = status.setted_temp/10
        self._target_humidity = None
        self._unit_of_measurement = TEMP_CELSIUS
        self._away = None
        self._hold = None
        self._current_temperature = status.current_temp/10
        self._current_humidity = None
        self._fan_list = ['最弱', '稍弱', '中等', '稍强', '最强', '自动']
        self._current_fan_mode = EnumControl.get_air_flow_name(status.air_flow.value)
        self._operation_list = ['制冷', '制热', '除湿', '送风', '清爽', '贴心睡眠']
        self._on = status.switch.value == EnumControl.Switch.ON
        self._current_operation = EnumControl.get_mode_name(status.mode.value)
        self._aux = None
        self._swing_list = ['0', '1', '2', '3', '4', '5', '6', '7']
        self._current_swing_mode = self._swing_list[status.fan_direction1.value]
        self._target_temperature_high = None
        self._target_temperature_low = None

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        return self._target_temperature_high

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        return self._target_temperature_low

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._current_humidity

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._target_humidity

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._current_operation

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self._away

    @property
    def current_hold_mode(self):
        """Return hold mode setting."""
        return self._hold

    @property
    def is_aux_heat_on(self):
        """Return true if aux heat is on."""
        return self._aux

    @property
    def is_on(self):
        """Return true if the device is on."""
        return self._on

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._current_fan_mode

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return self._fan_list

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if kwargs.get(ATTR_TARGET_TEMP_HIGH) is not None and \
                kwargs.get(ATTR_TARGET_TEMP_LOW) is not None:
            self._target_temperature_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
            self._target_temperature_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        self.schedule_update_ha_state()

    def set_humidity(self, humidity):
        """Set new humidity level."""
        self._target_humidity = humidity
        self.schedule_update_ha_state()

    def set_swing_mode(self, swing_mode):
        """Set new swing mode."""
        self._current_swing_mode = swing_mode
        self.schedule_update_ha_state()

    def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        self._current_fan_mode = fan_mode
        self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        self._current_operation = operation_mode
        self.schedule_update_ha_state()

    @property
    def current_swing_mode(self):
        """Return the swing setting."""
        return self._current_swing_mode

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._swing_list

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._away = True
        self.schedule_update_ha_state()

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._away = False
        self.schedule_update_ha_state()

    def set_hold_mode(self, hold_mode):
        """Update hold_mode on."""
        self._hold = hold_mode
        self.schedule_update_ha_state()

    def turn_aux_heat_on(self):
        """Turn auxiliary heater on."""
        self._aux = True
        self.schedule_update_ha_state()

    def turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        self._aux = False
        self.schedule_update_ha_state()

    def turn_on(self):
        """Turn on."""
        self._on = True
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn off."""
        self._on = False
        self.schedule_update_ha_state()
