"""
Demo platform that offers a fake climate device.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import copy

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_FAN_MODE,
    SUPPORT_OPERATION_MODE, SUPPORT_SWING_MODE,
    SUPPORT_ON_OFF, STATE_COOL, STATE_HEAT, STATE_DRY,
    STATE_FAN_ONLY, STATE_AUTO, STATE_ECO)
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE

from .ds_air_service.ctrl_enum import EnumControl
from .ds_air_service.dao import AirCon, Device

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_OPERATION_MODE \
                | SUPPORT_SWING_MODE | SUPPORT_ON_OFF
OPERATION_LIST = [STATE_COOL, STATE_HEAT, STATE_DRY, STATE_FAN_ONLY, STATE_AUTO, STATE_ECO]
FAN_LIST = ['最弱', '稍弱', '中等', '稍强', '最强', '自动']
SWING_LIST = ['➡️', '↘️', '⬇️', '↙️', '⬅️', '↔️', '🔄']


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
        self._name = aircon.alias
        self._device_info = Device()
        self._device_info.room_id = aircon.room_id
        self._device_info.unit_id = aircon.unit_id
        self._device_info.id = aircon.id
        self._device_info.name = aircon.name
        self._device_info.alias = aircon.alias
        self._support_flags = SUPPORT_FLAGS
        self._status = aircon.status

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return 16

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return 32

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

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
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._status.current_temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._status.setted_temp

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        return None

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        return None

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return None

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return None

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return EnumControl.get_mode_name(self._status.mode.value)

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return OPERATION_LIST

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return None

    @property
    def current_hold_mode(self):
        """Return hold mode setting."""
        return None

    @property
    def is_aux_heat_on(self):
        """Return true if aux heat is on."""
        return None

    @property
    def is_on(self):
        """Return true if the device is on."""
        return self._status.switch.value == EnumControl.Switch.ON

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return EnumControl.get_air_flow_name(self._status.air_flow.value)

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return FAN_LIST

    @property
    def current_swing_mode(self):
        """Return the swing setting."""
        return EnumControl.get_fan_direction_name(self._status.fan_direction1.value)

    @property
    def swing_list(self):
        """List of available swing modes."""
        return SWING_LIST

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            new_status = copy.deepcopy(self._status)
            new_status.setted_temp = kwargs.get(ATTR_TEMPERATURE)*10
            from .ds_air_service.service import Service
            Service.control(self._device_info, new_status)

    def set_humidity(self, humidity):
        """Set new humidity level."""
        raise NotImplementedError

    def set_swing_mode(self, swing_mode):
        """Set new swing mode."""
        new_status = copy.deepcopy(self._status)
        new_status.fan_direction1 = EnumControl.get_fan_direction_enum(swing_mode)
        from .ds_air_service.service import Service
        Service.control(self._device_info, new_status)

    def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        new_status = copy.deepcopy(self._status)
        new_status.air_flow = EnumControl.get_air_flow_enum(fan_mode)
        from .ds_air_service.service import Service
        Service.control(self._device_info, new_status)

    def set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        new_status = copy.deepcopy(self._status)
        new_status.mode = EnumControl.get_mode_enum(operation_mode)
        from .ds_air_service.service import Service
        Service.control(self._device_info, new_status)

    def turn_away_mode_on(self):
        """Turn away mode on."""
        raise NotImplementedError

    def turn_away_mode_off(self):
        """Turn away mode off."""
        raise NotImplementedError

    def set_hold_mode(self, hold_mode):
        """Update hold_mode on."""
        raise NotImplementedError

    def turn_aux_heat_on(self):
        """Turn auxiliary heater on."""
        raise NotImplementedError

    def turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        raise NotImplementedError

    def turn_on(self):
        """Turn on."""
        new_status = copy.deepcopy(self._status)
        new_status.switch = EnumControl.Switch.ON
        from .ds_air_service.service import Service
        Service.control(self._device_info, new_status)

    def turn_off(self):
        """Turn off."""
        new_status = copy.deepcopy(self._status)
        new_status.switch = EnumControl.Switch.OFF
        from .ds_air_service.service import Service
        Service.control(self._device_info, new_status)
