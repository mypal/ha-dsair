"""Demo fan platform that has a fake fan."""
from __future__ import annotations

import logging
from operator import truediv
from re import S
from typing import Any,Optional, List

from .ds_air_service.display import display
from .ds_air_service.ctrl_enum import _MODE_VENT_NAME_LIST, EnumControl

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .ds_air_service.dao import Ventilation, VentilationStatus
from .ds_air_service.service import Service

PRESET_MODE_AUTO = "auto"
PRESET_MODE_SMART = "smart"
PRESET_MODE_SLEEP = "sleep"
PRESET_MODE_ON = "on"

FULL_SUPPORT = (
    FanEntityFeature.SET_SPEED | FanEntityFeature.OSCILLATE | FanEntityFeature.DIRECTION
)
LIMITED_SUPPORT = FanEntityFeature.SET_SPEED

SMALL_VAM_SUPPORT = FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE

_LOGGER = logging.getLogger(__name__)

def _log(s: str):
    s = str(s)
    for i in s.split("\n"):
        _LOGGER.debug(i)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entities = []
    for vent in Service.get_ventilations():
        entities.append(DsVent(vent))
    async_add_entities(entities)


class DsVent(FanEntity):
    """A demonstration fan component that uses legacy fan speeds."""

    def __init__(self, vent: Ventilation):
        _log('create ventilation:')
        _log(vent.__dict__)
        _log(vent.status)
        """Initialize the climate device."""
        self._name = vent.alias
        self._device_info = vent
        self._unique_id = vent.unique_id
        if vent.is_small_vam:
            self._attr_speed_count = 4
        else:
            self._attr_speed_count = 2
        Service.register_vent_hook(vent, self._status_change_hook)

    def _status_change_hook(self, **kwargs):
        _log('hook:')
        if kwargs.get('vent') is not None:
            vent: Ventilation = kwargs['vent']
            vent.status = self._device_info.status
            self._device_info = vent
            _log(display(self._device_info))

        if kwargs.get('status') is not None:
            status = self._device_info.status
            new_status: VentilationStatus = kwargs['status']
            if new_status.switch is not None:
                status.switch = new_status.switch
            if new_status.mode is not None:
                status.mode = new_status.mode
            if new_status.air_flow is not None:
                status.air_flow = new_status.air_flow
            _log('new status')
            _log(display(kwargs['status']))
            _log('updated status')
            _log(display(self._device_info.status))
            
        self.schedule_update_ha_state()

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Get entity name."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """No polling needed for a demo fan."""
        return False

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SMALL_VAM_SUPPORT

    
    @property
    def percentage(self) -> int | None:
        vent = self._device_info
        if vent.status.air_flow is None:
            return None
        return vent.status.air_flow.value * self.percentage_step
    
    def set_percentage(self, percentage: int) -> None:
        vent = self._device_info
        new_status = VentilationStatus()
        air_flow = EnumControl.AirFlow(round(percentage / self.percentage_step))
        vent.status.air_flow = air_flow
        if air_flow != EnumControl.AirFlow.SUPER_WEAK:
            new_status.air_flow = air_flow
            Service.control_vent(self._device_info, new_status)
            self.schedule_update_ha_state()

    def set_preset_mode(self, preset_mode: str) -> None:
        vent = self._device_info
        status = vent.status
        new_status = VentilationStatus()
        mode = EnumControl.get_vent_mode_enum(preset_mode)
        status.mode = mode
        new_status.mode = mode
        Service.control_vent(self._device_info, new_status)
    
    @property
    def preset_mode(self) -> str | None:
        if self._device_info.status.mode is None:
            return None
        return EnumControl.get_vent_mode_name(self._device_info.status.mode)

    @property
    def preset_modes(self) -> list[str] | None:
        return _MODE_VENT_NAME_LIST

    @property
    def device_info(self) -> Optional[DeviceInfo]:
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": "新风%s" % self._name,
            "manufacturer": "Daikin Industries, Ltd."
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        if self._device_info.status.switch is None:
            return None
        return self._device_info.status.switch == EnumControl.Switch.ON

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on the fan."""
        vent = self._device_info
        status = vent.status
        new_status = VentilationStatus()
        status.switch = EnumControl.Switch.ON
        new_status.switch = EnumControl.Switch.ON

        Service.control_vent(self._device_info, new_status)
        # self._switch = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        vent = self._device_info
        status = vent.status
        new_status = VentilationStatus()
        status.switch = EnumControl.Switch.OFF
        new_status.switch = EnumControl.Switch.OFF
        Service.control_vent(self._device_info, new_status)
        self.schedule_update_ha_state()
